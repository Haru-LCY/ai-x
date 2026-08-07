#!/usr/bin/env python3

"""Execute and record a small training-style NCCL collective schedule."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import platform
import socket
import sys
import time

import torch
import torch.distributed as dist

from trace_schema import TRACE_SCHEMA, write_json


def parse_mib_list(value):
    try:
        result = [float(item) for item in value.split(",")]
    except ValueError as error:
        raise argparse.ArgumentTypeError("sizes must be comma-separated MiB values") from error
    if not result or any(item <= 0 for item in result):
        raise argparse.ArgumentTypeError("all sizes must be positive")
    return result


def bytes_to_elements(byte_count, element_size):
    return max(1, (byte_count + element_size - 1) // element_size)


def execute_collective(operation, tensor, root):
    if operation == "all_reduce":
        dist.all_reduce(tensor, op=dist.ReduceOp.SUM)
    elif operation == "broadcast":
        dist.broadcast(tensor, src=root)
    else:
        raise ValueError(f"unsupported capture operation: {operation}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--warmup-iterations", type=int, default=2)
    parser.add_argument("--measurement-iterations", type=int, default=5)
    parser.add_argument("--cooldown-iterations", type=int, default=1)
    parser.add_argument("--all-reduce-mib", type=parse_mib_list,
                        default=parse_mib_list("1,4,16"))
    parser.add_argument("--broadcast-mib", type=parse_mib_list,
                        default=parse_mib_list("1,4,16"))
    parser.add_argument("--root", type=int, default=0)
    parser.add_argument("--seed", type=int, default=20260807)
    args = parser.parse_args()
    if min(args.warmup_iterations, args.measurement_iterations,
           args.cooldown_iterations) < 0:
        parser.error("iteration counts must be non-negative")
    if args.measurement_iterations < 1:
        parser.error("at least one measurement iteration is required")

    local_rank = int(os.environ.get("LOCAL_RANK", 0))
    torch.cuda.set_device(local_rank)
    device = torch.device("cuda", local_rank)
    dist.init_process_group(backend="nccl", device_id=device)
    rank = dist.get_rank()
    world_size = dist.get_world_size()
    if not 0 <= args.root < world_size:
        parser.error("--root must name a participating rank")
    torch.manual_seed(args.seed + rank)
    participants = list(range(world_size))
    dtype = torch.float32
    element_size = torch.empty((), dtype=dtype).element_size()

    sizes = {
        "all_reduce": [round(value * 1024 * 1024) for value in args.all_reduce_mib],
        "broadcast": [round(value * 1024 * 1024) for value in args.broadcast_mib],
    }
    tensors = {
        (operation, byte_count): torch.full(
            (bytes_to_elements(byte_count, element_size),),
            float(rank + 1), dtype=dtype, device=device,
        )
        for operation, byte_counts in sizes.items()
        for byte_count in byte_counts
    }
    torch.cuda.synchronize(device)
    dist.barrier()
    capture_epoch = time.monotonic_ns()
    events = []
    sequence = 0
    phases = [
        ("warmup", args.warmup_iterations),
        ("measurement", args.measurement_iterations),
        ("cooldown", args.cooldown_iterations),
    ]
    global_iteration = 0
    for phase, count in phases:
        for _ in range(count):
            # Gradient aggregation followed by root-to-all parameter/result
            # distribution is a compact training-style communication schedule.
            for operation in ("all_reduce", "broadcast"):
                for requested_bytes in sizes[operation]:
                    tensor = tensors[(operation, requested_bytes)]
                    tensor.fill_(float(rank + 1))
                    dist.barrier()
                    torch.cuda.synchronize(device)
                    start = time.monotonic_ns()
                    execute_collective(operation, tensor, args.root)
                    torch.cuda.synchronize(device)
                    end = time.monotonic_ns()
                    if rank == 0:
                        actual_bytes = tensor.numel() * tensor.element_size()
                        events.append({
                            "id": f"event-{sequence:06d}",
                            "sequence": sequence,
                            "iteration": global_iteration,
                            "phase": phase,
                            "op": operation,
                            "participants": participants,
                            "root": args.root if operation == "broadcast" else None,
                            "tensor_bytes": actual_bytes,
                            "requested_bytes": requested_bytes,
                            "start_ns": start - capture_epoch,
                            "duration_ns": end - start,
                        })
                        sequence += 1
            global_iteration += 1

    gathered_names = [None for _ in participants]
    dist.all_gather_object(gathered_names, torch.cuda.get_device_name(local_rank))
    if rank == 0:
        nccl_version = torch.cuda.nccl.version()
        trace = {
            "schema": TRACE_SCHEMA,
            "clock": "monotonic_ns",
            "world_size": world_size,
            "metadata": {
                "capture_kind": "executed_training_style_collective_microbenchmark",
                "hostname": socket.gethostname(),
                "platform": platform.platform(),
                "python": sys.version.split()[0],
                "pytorch": torch.__version__,
                "cuda": torch.version.cuda,
                "nccl": ".".join(str(item) for item in nccl_version),
                "gpu_names": gathered_names,
                "dtype": str(dtype).removeprefix("torch."),
                "seed": args.seed,
                "root": args.root,
                "warmup_iterations": args.warmup_iterations,
                "measurement_iterations": args.measurement_iterations,
                "cooldown_iterations": args.cooldown_iterations,
                "note": (
                    "Collectives were executed on real GPUs. This is a controlled "
                    "training-style communication microbenchmark, not a full-model trace."
                ),
            },
            "events": events,
        }
        write_json(args.output, trace)
        print(f"wrote {len(events)} executed collective events to {args.output}")
    dist.barrier()
    dist.destroy_process_group()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
