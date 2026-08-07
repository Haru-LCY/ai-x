#!/usr/bin/env python3

"""Validation helpers for the Lab4 collective trace formats."""

from __future__ import annotations

import json
from pathlib import Path


TRACE_SCHEMA = "lab4.ai_collective_trace.v1"
REPLAY_SCHEMA = "lab4.garnet_collective_replay.v1"
SUPPORTED_OPERATIONS = {
    "all_gather",
    "all_reduce",
    "broadcast",
    "reduce",
    "reduce_scatter",
}


class TraceValidationError(ValueError):
    """Raised when a trace violates the versioned input contract."""


def _require(condition, message):
    if not condition:
        raise TraceValidationError(message)


def validate_trace(trace):
    """Validate and return a normalized high-level collective trace."""

    _require(isinstance(trace, dict), "trace root must be an object")
    _require(trace.get("schema") == TRACE_SCHEMA, f"schema must be {TRACE_SCHEMA}")
    world_size = trace.get("world_size")
    _require(isinstance(world_size, int) and world_size > 1,
             "world_size must be an integer greater than one")
    _require(trace.get("clock") == "monotonic_ns",
             "clock must be monotonic_ns")
    events = trace.get("events")
    _require(isinstance(events, list) and events, "events must be a nonempty list")

    normalized = []
    identifiers = set()
    previous_start = -1
    for index, raw in enumerate(events):
        prefix = f"event[{index}]"
        _require(isinstance(raw, dict), f"{prefix} must be an object")
        event_id = raw.get("id")
        _require(isinstance(event_id, str) and event_id,
                 f"{prefix}.id must be a nonempty string")
        _require(event_id not in identifiers, f"duplicate event id {event_id}")
        identifiers.add(event_id)
        operation = raw.get("op")
        _require(operation in SUPPORTED_OPERATIONS,
                 f"{prefix}.op is unsupported: {operation}")
        participants = raw.get("participants")
        _require(isinstance(participants, list) and participants,
                 f"{prefix}.participants must be a nonempty list")
        _require(all(isinstance(rank, int) for rank in participants),
                 f"{prefix}.participants must contain integers")
        _require(participants == sorted(set(participants)),
                 f"{prefix}.participants must be sorted and unique")
        _require(participants[0] >= 0 and participants[-1] < world_size,
                 f"{prefix}.participants contains an invalid rank")
        root = raw.get("root")
        if operation in {"broadcast", "reduce"}:
            _require(root in participants,
                     f"{prefix}.root must name a participating rank")
        else:
            _require(root is None, f"{prefix}.root must be null for {operation}")
        tensor_bytes = raw.get("tensor_bytes")
        _require(isinstance(tensor_bytes, int) and tensor_bytes > 0,
                 f"{prefix}.tensor_bytes must be positive")
        start_ns = raw.get("start_ns")
        duration_ns = raw.get("duration_ns")
        _require(isinstance(start_ns, int) and start_ns >= 0,
                 f"{prefix}.start_ns must be non-negative")
        _require(isinstance(duration_ns, int) and duration_ns >= 0,
                 f"{prefix}.duration_ns must be non-negative")
        _require(start_ns >= previous_start,
                 f"{prefix}.start_ns is earlier than the preceding event")
        previous_start = start_ns
        iteration = raw.get("iteration")
        _require(isinstance(iteration, int) and iteration >= 0,
                 f"{prefix}.iteration must be non-negative")
        phase = raw.get("phase")
        _require(phase in {"warmup", "measurement", "cooldown"},
                 f"{prefix}.phase is invalid")
        normalized.append(dict(raw))

    result = dict(trace)
    result["events"] = normalized
    return result


def load_trace(path):
    with Path(path).open(encoding="utf-8") as handle:
        return validate_trace(json.load(handle))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
    temporary.replace(path)
