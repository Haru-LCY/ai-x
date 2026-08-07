#!/usr/bin/env python3

"""Compile broadcast events into deterministic Garnet multicast requests."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from trace_schema import REPLAY_SCHEMA, load_trace, write_json


def parse_rank_map(value, world_size):
    if value is None:
        return list(range(world_size))
    try:
        mapping = [int(item) for item in value.split(",")]
    except ValueError as error:
        raise ValueError("rank map must contain comma-separated Router ids") from error
    if len(mapping) != world_size:
        raise ValueError(f"rank map requires exactly {world_size} Router ids")
    if len(set(mapping)) != len(mapping) or min(mapping) < 0:
        raise ValueError("rank map must contain distinct non-negative Router ids")
    return mapping


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rank-map")
    parser.add_argument("--network-clock-ghz", type=float, default=1.0)
    parser.add_argument("--flit-bytes", type=int, default=16)
    parser.add_argument("--chunk-bytes", type=int, default=4096)
    parser.add_argument(
        "--byte-scale", type=float, default=1.0,
        help="explicit payload scaling factor in (0, 1] for tractable simulation",
    )
    parser.add_argument(
        "--time-scale", type=float, default=1.0,
        help="explicit inter-event time scaling factor in (0, 1]",
    )
    parser.add_argument("--phases", default="measurement",
                        help="comma-separated warmup,measurement,cooldown selection")
    args = parser.parse_args()
    if args.network_clock_ghz <= 0:
        parser.error("--network-clock-ghz must be positive")
    if args.flit_bytes < 1 or args.chunk_bytes < 1:
        parser.error("flit and chunk sizes must be positive")
    if not 0 < args.byte_scale <= 1:
        parser.error("--byte-scale must be in (0, 1]")
    if not 0 < args.time_scale <= 1:
        parser.error("--time-scale must be in (0, 1]")
    if args.chunk_bytes % args.flit_bytes:
        parser.error("--chunk-bytes must be a multiple of --flit-bytes")
    selected_phases = set(args.phases.split(","))
    if not selected_phases or not selected_phases <= {
        "warmup", "measurement", "cooldown"
    }:
        parser.error("--phases contains an invalid phase")

    trace = load_trace(args.trace)
    try:
        rank_map = parse_rank_map(args.rank_map, trace["world_size"])
    except ValueError as error:
        parser.error(str(error))
    candidates = [
        event for event in trace["events"]
        if event["phase"] in selected_phases and event["op"] == "broadcast"
    ]
    if not candidates:
        parser.error("selected trace phases contain no broadcast events")
    origin_ns = min(event["start_ns"] for event in candidates)
    requests = []
    for event in candidates:
        source = rank_map[event["root"]]
        destinations = sorted(
            rank_map[rank] for rank in event["participants"] if rank != event["root"]
        )
        scaled_event_bytes = max(1, math.ceil(
            event["tensor_bytes"] * args.byte_scale
        ))
        remaining = scaled_event_bytes
        chunk_index = 0
        release_cycle = round(
            (event["start_ns"] - origin_ns) * args.network_clock_ghz *
            args.time_scale
        )
        while remaining:
            payload_bytes = min(remaining, args.chunk_bytes)
            requests.append({
                "id": f"{event['id']}-chunk-{chunk_index:06d}",
                "trace_event_id": event["id"],
                "iteration": event["iteration"],
                "phase": event["phase"],
                "operation": "broadcast",
                "source_router": source,
                "destination_routers": destinations,
                "release_cycle": release_cycle,
                "payload_bytes": payload_bytes,
                "source_tensor_bytes": event["tensor_bytes"],
                "scaled_event_bytes": scaled_event_bytes,
                "packet_flits": math.ceil(payload_bytes / args.flit_bytes),
            })
            remaining -= payload_bytes
            chunk_index += 1

    replay = {
        "schema": REPLAY_SCHEMA,
        "source_trace_schema": trace["schema"],
        "world_size": trace["world_size"],
        "rank_to_router": rank_map,
        "network_clock_ghz": args.network_clock_ghz,
        "flit_bytes": args.flit_bytes,
        "chunk_bytes": args.chunk_bytes,
        "byte_scale": args.byte_scale,
        "time_scale": args.time_scale,
        "selected_phases": sorted(selected_phases),
        "lowering": {
            "broadcast": "one multicast request per payload chunk",
            "payload_scaling": (
                "ceil(source tensor bytes * byte_scale), with a one-byte minimum"
            ),
            "time_scaling": "source relative time * time_scale",
            "unsupported_operations": "retained only in the source trace and not replayed",
        },
        "source_event_count": len(trace["events"]),
        "selected_broadcast_event_count": len(candidates),
        "request_count": len(requests),
        "requests": requests,
    }
    write_json(args.output, replay)
    print(
        f"PASS: compiled {len(candidates)} broadcast events into "
        f"{len(requests)} Garnet multicast requests at {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
