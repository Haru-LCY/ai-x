#!/usr/bin/env python3

"""Validate a compiled Lab4 Garnet replay request stream."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from trace_schema import (
    ALLREDUCE_REPLAY_SCHEMA,
    REPLAY_SCHEMA,
    TENSOR_ALLREDUCE_REPLAY_SCHEMA,
)


class ReplayValidationError(ValueError):
    pass


def _require(condition, message):
    if not condition:
        raise ReplayValidationError(message)


def validate_replay(replay):
    _require(isinstance(replay, dict), "replay root must be an object")
    _require(replay.get("schema") == REPLAY_SCHEMA,
             f"schema must be {REPLAY_SCHEMA}")
    world_size = replay.get("world_size")
    _require(isinstance(world_size, int) and world_size > 1,
             "world_size must be an integer greater than one")
    flit_bytes = replay.get("flit_bytes")
    _require(isinstance(flit_bytes, int) and flit_bytes > 0,
             "flit_bytes must be positive")
    for field in ("byte_scale", "time_scale"):
        value = replay.get(field)
        _require(isinstance(value, (int, float)) and 0 < value <= 1,
                 f"{field} must be in (0, 1]")
    rank_map = replay.get("rank_to_router")
    _require(isinstance(rank_map, list) and len(rank_map) == world_size,
             "rank_to_router must contain one entry per rank")
    _require(all(isinstance(router, int) and router >= 0 for router in rank_map),
             "rank_to_router must contain non-negative integers")
    _require(len(set(rank_map)) == len(rank_map),
             "rank_to_router must contain distinct Router ids")

    requests = replay.get("requests")
    _require(isinstance(requests, list), "requests must be a list")
    expected_count = replay.get("request_count")
    _require(expected_count == len(requests),
             "request_count does not match requests length")
    identifiers = set()
    previous_release = -1
    total_flits = 0
    for index, request in enumerate(requests):
        prefix = f"request[{index}]"
        _require(isinstance(request, dict), f"{prefix} must be an object")
        identifier = request.get("id")
        _require(isinstance(identifier, str) and identifier,
                 f"{prefix}.id must be nonempty")
        _require(identifier not in identifiers, f"duplicate request id {identifier}")
        identifiers.add(identifier)
        release = request.get("release_cycle")
        _require(isinstance(release, int) and release >= 0,
                 f"{prefix}.release_cycle must be non-negative")
        _require(release >= previous_release,
                 f"{prefix}.release_cycle is not monotonic")
        previous_release = release
        source = request.get("source_router")
        destinations = request.get("destination_routers")
        _require(isinstance(source, int) and source >= 0,
                 f"{prefix}.source_router must be non-negative")
        _require(source not in destinations if isinstance(destinations, list) else False,
                 f"{prefix} source must not be a destination")
        _require(isinstance(destinations, list) and destinations,
                 f"{prefix}.destination_routers must be nonempty")
        _require(destinations == sorted(set(destinations)),
                 f"{prefix}.destination_routers must be sorted and unique")
        _require(all(isinstance(dest, int) and dest >= 0 for dest in destinations),
                 f"{prefix}.destination_routers must contain Router ids")
        payload = request.get("payload_bytes")
        packet_flits = request.get("packet_flits")
        _require(isinstance(payload, int) and payload > 0,
                 f"{prefix}.payload_bytes must be positive")
        _require(packet_flits == math.ceil(payload / flit_bytes),
                 f"{prefix}.packet_flits does not match payload_bytes")
        total_flits += packet_flits

    _require(replay.get("total_packet_flits", total_flits) == total_flits,
             "total_packet_flits does not match requests")
    result = dict(replay)
    result["total_packet_flits"] = total_flits
    return result


def validate_allreduce_replay(replay):
    _require(isinstance(replay, dict), "replay root must be an object")
    _require(replay.get("schema") == ALLREDUCE_REPLAY_SCHEMA,
             f"schema must be {ALLREDUCE_REPLAY_SCHEMA}")
    world_size = replay.get("world_size")
    _require(isinstance(world_size, int) and world_size > 1,
             "world_size must be an integer greater than one")
    flit_bytes = replay.get("flit_bytes")
    _require(isinstance(flit_bytes, int) and flit_bytes > 0,
             "flit_bytes must be positive")
    for field in ("byte_scale", "time_scale"):
        value = replay.get(field)
        _require(isinstance(value, (int, float)) and 0 < value <= 1,
                 f"{field} must be in (0, 1]")
    rank_map = replay.get("rank_to_router")
    _require(isinstance(rank_map, list) and len(rank_map) == world_size,
             "rank_to_router must contain one entry per rank")
    _require(all(isinstance(router, int) and router >= 0 for router in rank_map),
             "rank_to_router must contain non-negative integers")
    _require(len(set(rank_map)) == world_size,
             "rank_to_router must contain distinct Router ids")
    root = replay.get("reduction_root_router")
    _require(root in rank_map, "reduction_root_router must be a mapped Router")
    requests = replay.get("requests")
    _require(isinstance(requests, list) and requests,
             "requests must be a nonempty list")
    _require(replay.get("request_count") == len(requests),
             "request_count does not match requests length")
    identifiers = set()
    previous_release = -1
    total_lanes = 0
    expected_participants = sorted(rank_map)
    for index, request in enumerate(requests):
        prefix = f"request[{index}]"
        identifier = request.get("id")
        _require(isinstance(identifier, str) and identifier,
                 f"{prefix}.id must be nonempty")
        _require(identifier not in identifiers, f"duplicate request id {identifier}")
        identifiers.add(identifier)
        _require(request.get("operation") == "all_reduce",
                 f"{prefix}.operation must be all_reduce")
        _require(request.get("participant_routers") == expected_participants,
                 f"{prefix}.participant_routers must contain the full mapped world")
        _require(request.get("reduction_root_router") == root,
                 f"{prefix}.reduction_root_router differs from replay root")
        release = request.get("release_cycle")
        _require(isinstance(release, int) and release >= previous_release,
                 f"{prefix}.release_cycle must be non-negative and monotonic")
        previous_release = release
        scaled_bytes = request.get("scaled_event_bytes")
        lanes = request.get("lane_rounds")
        _require(isinstance(scaled_bytes, int) and scaled_bytes > 0,
                 f"{prefix}.scaled_event_bytes must be positive")
        _require(lanes == math.ceil(scaled_bytes / flit_bytes),
                 f"{prefix}.lane_rounds does not match scaled bytes")
        total_lanes += lanes
    _require(replay.get("total_lane_rounds") == total_lanes,
             "total_lane_rounds does not match requests")
    _require(replay.get("total_contribution_flits") == total_lanes * world_size,
             "total_contribution_flits does not match lanes * world_size")
    return dict(replay)


def validate_tensor_allreduce_replay(replay):
    """Validate the tensor (multi-flit) all-reduce replay contract.

    A logical all-reduce event is one request carrying tensor_flits lanes,
    split into chunks. Each flit is one 64-bit reduction lane, so every chunk
    payload must be a whole number of flits. Chunks must exactly tile the
    tensor (contiguous lane_start, payloads summing to scaled_event_bytes).
    """

    _require(isinstance(replay, dict), "replay root must be an object")
    _require(
        replay.get("schema") == TENSOR_ALLREDUCE_REPLAY_SCHEMA,
        f"schema must be {TENSOR_ALLREDUCE_REPLAY_SCHEMA}",
    )
    world_size = replay.get("world_size")
    _require(isinstance(world_size, int) and world_size > 1,
             "world_size must be an integer greater than one")
    flit_bytes = replay.get("flit_bytes")
    _require(isinstance(flit_bytes, int) and flit_bytes > 0,
             "flit_bytes must be positive")
    chunk_bytes = replay.get("chunk_bytes")
    _require(isinstance(chunk_bytes, int) and chunk_bytes > 0,
             "chunk_bytes must be positive")
    _require(chunk_bytes % flit_bytes == 0,
             "chunk_bytes must be a multiple of flit_bytes")
    for field in ("byte_scale", "time_scale"):
        value = replay.get(field)
        _require(isinstance(value, (int, float)) and 0 < value <= 1,
                 f"{field} must be in (0, 1]")
    rank_map = replay.get("rank_to_router")
    _require(isinstance(rank_map, list) and len(rank_map) == world_size,
             "rank_to_router must contain one entry per rank")
    _require(all(isinstance(router, int) and router >= 0 for router in rank_map),
             "rank_to_router must contain non-negative integers")
    _require(len(set(rank_map)) == len(rank_map),
             "rank_to_router must contain distinct Router ids")
    root = replay.get("reduction_root_router")
    _require(root in rank_map, "reduction_root_router must be a mapped Router")
    requests = replay.get("requests")
    _require(isinstance(requests, list) and requests,
             "requests must be a nonempty list")
    _require(replay.get("request_count") == len(requests),
             "request_count does not match requests length")

    identifiers = set()
    chunk_ids = set()
    previous_release = -1
    total_bytes = 0
    total_flits = 0
    total_chunks = 0
    expected_participants = sorted(rank_map)
    for index, request in enumerate(requests):
        prefix = f"request[{index}]"
        identifier = request.get("id")
        _require(isinstance(identifier, str) and identifier,
                 f"{prefix}.id must be nonempty")
        _require(identifier not in identifiers, f"duplicate request id {identifier}")
        identifiers.add(identifier)
        _require(request.get("operation") == "all_reduce",
                 f"{prefix}.operation must be all_reduce")
        _require(request.get("participant_routers") == expected_participants,
                 f"{prefix}.participant_routers must contain the full mapped world")
        _require(request.get("reduction_root_router") == root,
                 f"{prefix}.reduction_root_router differs from replay root")
        release = request.get("release_cycle")
        _require(isinstance(release, int) and release >= previous_release,
                 f"{prefix}.release_cycle must be non-negative and monotonic")
        previous_release = release
        scaled_bytes = request.get("scaled_event_bytes")
        tensor_flits = request.get("tensor_flits")
        _require(isinstance(scaled_bytes, int) and scaled_bytes > 0,
                 f"{prefix}.scaled_event_bytes must be positive")
        _require(scaled_bytes % flit_bytes == 0,
                 f"{prefix}.scaled_event_bytes must be a whole number of flits")
        _require(tensor_flits == scaled_bytes // flit_bytes,
                 f"{prefix}.tensor_flits does not match scaled bytes")
        chunks = request.get("chunks")
        _require(isinstance(chunks, list) and chunks,
                 f"{prefix}.chunks must be a nonempty list")
        expected_lane_start = 0
        chunk_bytes_sum = 0
        chunk_lanes = 0
        for chunk_index, chunk in enumerate(chunks):
            chunk_prefix = f"{prefix}.chunks[{chunk_index}]"
            chunk_id = chunk.get("chunk_id")
            _require(isinstance(chunk_id, str) and chunk_id,
                     f"{chunk_prefix}.chunk_id must be nonempty")
            _require(chunk_id not in chunk_ids,
                     f"duplicate chunk id {chunk_id}")
            chunk_ids.add(chunk_id)
            payload = chunk.get("payload_bytes")
            packet_flits = chunk.get("packet_flits")
            lane_start = chunk.get("lane_start")
            lane_count = chunk.get("lane_count")
            _require(isinstance(payload, int) and payload > 0,
                     f"{chunk_prefix}.payload_bytes must be positive")
            _require(payload % flit_bytes == 0,
                     f"{chunk_prefix}.payload_bytes is not a whole number of flits")
            _require(payload <= chunk_bytes,
                     f"{chunk_prefix}.payload_bytes exceeds chunk_bytes")
            _require(packet_flits == payload // flit_bytes,
                     f"{chunk_prefix}.packet_flits does not match payload_bytes")
            _require(isinstance(lane_start, int) and lane_start >= 0,
                     f"{chunk_prefix}.lane_start must be non-negative")
            _require(lane_start == expected_lane_start,
                     f"{chunk_prefix}.lane_start is not contiguous")
            _require(lane_count == packet_flits,
                     f"{chunk_prefix}.lane_count must equal packet_flits")
            expected_lane_start += lane_count
            chunk_bytes_sum += payload
            chunk_lanes += lane_count
        _require(chunk_bytes_sum == scaled_bytes,
                 f"{prefix}.chunks do not cover scaled_event_bytes")
        _require(chunk_lanes == tensor_flits,
                 f"{prefix}.chunk lanes do not match tensor_flits")
        total_bytes += scaled_bytes
        total_flits += tensor_flits
        total_chunks += len(chunks)

    _require(replay.get("total_tensor_bytes") == total_bytes,
             "total_tensor_bytes does not match requests")
    _require(replay.get("total_tensor_flits") == total_flits,
             "total_tensor_flits does not match requests")
    _require(replay.get("total_chunk_count") == total_chunks,
             "total_chunk_count does not match requests")
    _require(
        replay.get("total_contribution_flits") == total_flits * world_size,
        "total_contribution_flits does not match tensor_flits * world_size",
    )
    return dict(replay)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("replay", type=Path)
    args = parser.parse_args()
    try:
        with args.replay.open(encoding="utf-8") as handle:
            raw = json.load(handle)
            if raw.get("schema") == TENSOR_ALLREDUCE_REPLAY_SCHEMA:
                replay = validate_tensor_allreduce_replay(raw)
            elif raw.get("schema") == ALLREDUCE_REPLAY_SCHEMA:
                replay = validate_allreduce_replay(raw)
            else:
                replay = validate_replay(raw)
    except (OSError, json.JSONDecodeError, ReplayValidationError) as error:
        print(f"FAIL: {error}")
        return 1
    print(
        f"PASS: schema={replay['schema']} world_size={replay['world_size']} "
        f"requests={len(replay['requests'])} total_work_flits="
        f"{replay.get('total_packet_flits', replay.get('total_contribution_flits'))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
