#!/usr/bin/env python3

"""Compile all-reduce events into scalar in-network reduction lanes."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from compile_replay import parse_rank_map
from trace_schema import ALLREDUCE_REPLAY_SCHEMA, load_trace, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rank-map")
    parser.add_argument("--reduction-root-rank", type=int, default=0)
    parser.add_argument("--network-clock-ghz", type=float, default=1.0)
    parser.add_argument("--flit-bytes", type=int, default=16)
    parser.add_argument("--byte-scale", type=float, default=1.0)
    parser.add_argument("--time-scale", type=float, default=1.0)
    parser.add_argument("--phases", default="measurement")
    args = parser.parse_args()
    if args.network_clock_ghz <= 0 or args.flit_bytes < 1:
        parser.error("network clock and flit size must be positive")
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
    for event in candidates:
        scaled_bytes = max(1, math.ceil(event["tensor_bytes"] * args.byte_scale))
        lane_rounds = math.ceil(scaled_bytes / args.flit_bytes)
        requests.append({
            "id": event["id"],
            "trace_event_id": event["id"],
            "iteration": event["iteration"],
            "phase": event["phase"],
            "operation": "all_reduce",
            "participant_routers": participants,
            "reduction_root_router": root_router,
            "release_cycle": round(
                (event["start_ns"] - origin_ns) * args.network_clock_ghz *
                args.time_scale
            ),
            "source_tensor_bytes": event["tensor_bytes"],
            "scaled_event_bytes": scaled_bytes,
            "lane_rounds": lane_rounds,
        })

    total_lanes = sum(request["lane_rounds"] for request in requests)
    replay = {
        "schema": ALLREDUCE_REPLAY_SCHEMA,
        "source_trace_schema": trace["schema"],
        "world_size": trace["world_size"],
        "rank_to_router": rank_map,
        "network_clock_ghz": args.network_clock_ghz,
        "flit_bytes": args.flit_bytes,
        "byte_scale": args.byte_scale,
        "time_scale": args.time_scale,
        "selected_phases": sorted(selected_phases),
        "reduction_root_rank": args.reduction_root_rank,
        "reduction_root_router": root_router,
        "lowering": {
            "all_reduce": (
                "ceil(scaled event bytes / flit bytes) independent scalar "
                "lanes; each lane executes router-side reduce then broadcast"
            ),
            "serialization": (
                "lanes retain event release eligibility but execute serially "
                "because the scalar reduction datapath has one active lane"
            ),
            "payload_scaling": "ceil(source tensor bytes * byte_scale)",
            "time_scaling": "source relative time * time_scale",
        },
        "source_event_count": len(trace["events"]),
        "selected_all_reduce_event_count": len(candidates),
        "request_count": len(requests),
        "total_lane_rounds": total_lanes,
        "total_contribution_flits": total_lanes * trace["world_size"],
        "requests": requests,
    }
    write_json(args.output, replay)
    print(
        f"PASS: compiled {len(candidates)} all_reduce events into "
        f"{total_lanes} scalar reduction lanes at {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
