#!/usr/bin/env python3

"""Validate and summarize a Lab4 AI collective trace."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path

from trace_schema import TraceValidationError, load_trace


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    args = parser.parse_args()
    try:
        trace = load_trace(args.trace)
    except (OSError, ValueError, TraceValidationError) as error:
        print(f"FAIL: {error}")
        return 1
    counts = Counter(event["op"] for event in trace["events"])
    measured = [event for event in trace["events"] if event["phase"] == "measurement"]
    byte_totals = defaultdict(int)
    durations = defaultdict(int)
    for event in measured:
        byte_totals[event["op"]] += event["tensor_bytes"]
        durations[event["op"]] += event["duration_ns"]
    print(
        f"PASS: schema={trace['schema']} world_size={trace['world_size']} "
        f"events={len(trace['events'])} measurement_events={len(measured)}"
    )
    for operation in sorted(counts):
        measured_count = sum(event["op"] == operation for event in measured)
        print(
            f"  {operation}: total_events={counts[operation]} "
            f"measured_events={measured_count} "
            f"measured_tensor_bytes={byte_totals[operation]} "
            f"measured_duration_ns={durations[operation]}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
