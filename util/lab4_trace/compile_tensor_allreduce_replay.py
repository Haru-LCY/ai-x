#!/usr/bin/env python3

"""Compile all-reduce events into tensor (multi-flit) all-reduce requests.

Unlike the scalar-lane compiler (compile_allreduce_replay.py), which lowers
every scaled event into independent scalar lanes, this compiler preserves each
logical all-reduce event as one multi-flit request. The tensor is split into
chunks (bounded by --chunk-bytes), each chunk becomes a packet of flits, and
one flit is one 64-bit reduction lane.

The output schema is lab4.garnet_tensor_allreduce_replay.v1.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from compile_replay import parse_rank_map
from trace_schema import TENSOR_ALLREDUCE_REPLAY_SCHEMA, load_trace, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rank-map")
    parser.add_argument("--reduction-root-rank", type=int, default=0)
    parser.add_argument("--network-clock-ghz", type=float, default=1.0)
    parser.add_argument("--flit-bytes", type=int, default=16)
    parser.add_argument("--chunk-bytes", type=int, default=4096)
    parser.add_argument("--byte-scale", type=float, default=1.0)
    parser.add_argument("--time-scale", type=float, default=1.0)
    parser.add_argument("--phases", default="measurement")
    args = parser.parse_args()

    if args.network_clock_ghz <= 0 or args.flit_bytes < 1:
        parser.error("network clock and flit size must be positive")
    if args.chunk_bytes < 1 or args.chunk_bytes % args.flit_bytes:
        parser.error("--chunk-bytes must be a positive multiple of --flit-bytes")
    if not 0 < args.byte_scale <= 1 or not 0 < args.time_scale <= 1:
        parser.error("byte and time scales must be in (0, 1]")
    selected_phases = set(args.phases.split(","))
    if not selected_phases or not selected_phases <= {
        "warmup", "measurement", "cooldown"
    }:
        parser.error("--phases contains an invalid phase")

    trace = load_trace(args.trace)
    if not 0 <= args.reduction_root_rank < trace["world_size"]:
        parser.error("--reduction-root-rank lies outside the trace world")
    try:
        rank_map = parse_rank_map(args.rank_map, trace["world_size"])
    except ValueError as error:
        parser.error(str(error))

    candidates = [
        event for event in trace["events"]
        if event["phase"] in selected_phases and event["op"] == "all_reduce"
    ]
    if not candidates:
        parser.error("selected trace phases contain no all_reduce events")

    origin_ns = min(event["start_ns"] for event in candidates)
    participants = sorted(rank_map)
    root_router = rank_map[args.reduction_root_rank]

    requests = []
    total_bytes = 0
    total_flits = 0
    total_chunks = 0
    for event in candidates:
        raw_scaled = max(1, math.ceil(event["tensor_bytes"] * args.byte_scale))
        # Pad to a whole number of flits (each flit is one reduction lane).
        scaled_event_bytes = (
            math.ceil(raw_scaled / args.flit_bytes) * args.flit_bytes
        )
        tensor_flits = scaled_event_bytes // args.flit_bytes
        release_cycle = round(
            (event["start_ns"] - origin_ns) * args.network_clock_ghz *
            args.time_scale
        )

        chunks = []
        remaining = scaled_event_bytes
        lane_start = 0
        chunk_index = 0
        while remaining:
            payload_bytes = min(remaining, args.chunk_bytes)
            packet_flits = payload_bytes // args.flit_bytes
            chunks.append({
                "chunk_id": f"{event['id']}-chunk-{chunk_index:06d}",
                "payload_bytes": payload_bytes,
                "packet_flits": packet_flits,
                "lane_start": lane_start,
                "lane_count": packet_flits,
            })
            lane_start += packet_flits
            remaining -= payload_bytes
            chunk_index += 1

        requests.append({
            "id": event["id"],
            "trace_event_id": event["id"],
            "iteration": event["iteration"],
            "phase": event["phase"],
            "operation": "all_reduce",
            "participant_routers": participants,
            "reduction_root_router": root_router,
            "release_cycle": release_cycle,
            "source_tensor_bytes": event["tensor_bytes"],
            "scaled_event_bytes": scaled_event_bytes,
            "tensor_flits": tensor_flits,
            "chunks": chunks,
        })
        total_bytes += scaled_event_bytes
        total_flits += tensor_flits
        total_chunks += len(chunks)

    replay = {
        "schema": TENSOR_ALLREDUCE_REPLAY_SCHEMA,
        "source_trace_schema": trace["schema"],
        "world_size": trace["world_size"],
        "rank_to_router": rank_map,
        "network_clock_ghz": args.network_clock_ghz,
        "flit_bytes": args.flit_bytes,
        "chunk_bytes": args.chunk_bytes,
        "byte_scale": args.byte_scale,
        "time_scale": args.time_scale,
        "selected_phases": sorted(selected_phases),
        "reduction_root_rank": args.reduction_root_rank,
        "reduction_root_router": root_router,
        "lowering": {
            "all_reduce": (
                "per logical event, one tensor request; the tensor is split "
                "into chunks, each chunk is a packet of flits, and each flit "
                "is one 64-bit reduction lane that is reduced along the "
                "convergence tree and then broadcast from the root"
            ),
            "serialization": (
                "chunks of a request are released together; lane state must "
                "be tracked per (request, chunk, lane) by the datapath"
            ),
            "payload_scaling": (
                "ceil(source tensor bytes * byte_scale), padded to a whole "
                "number of flits"
            ),
            "time_scaling": "source relative time * time_scale",
        },
        "source_event_count": len(trace["events"]),
        "selected_all_reduce_event_count": len(candidates),
        "request_count": len(requests),
        "total_tensor_bytes": total_bytes,
        "total_tensor_flits": total_flits,
        "total_chunk_count": total_chunks,
        "total_contribution_flits": total_flits * trace["world_size"],
        "requests": requests,
    }
    write_json(args.output, replay)
    print(
        f"PASS: compiled {len(candidates)} all_reduce events into "
        f"{total_flits} tensor flits per rank ({total_chunks} chunks, "
        f"{replay['total_contribution_flits']} contribution flits) at "
        f"{args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
