"""Run and validate the Lab4 tensor (multi-flit) all-reduce matrix.

H2 gate: 2x2 Mesh with roots 0 and 3, packet sizes 1/4/16/64 flits; plus two
scale sanity cases (3x3 root 4 size 16, 4x4 root 5 size 64).

Each rank contributes value(rank, lane) = (rank + 1) * 1000 + lane, so the
expected broadcast result for lane L is 1000 * N * (N+1) / 2 + N * L. The
network interfaces assert this per delivered lane; any wrong value fails the
run. The runner additionally checks exact source/merge/delivery/router-flit
counts and a completion-driven exit.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG = REPO_ROOT / "configs/example/garnet_synth_traffic.py"


def cases():
    """(name, cpus, dirs, rows, root, packet_flits)"""
    matrix = []
    for root in (0, 3):
        for flits in (1, 4, 16, 64):
            matrix.append((f"tensor-2x2-r{root}-f{flits}", 4, 4, 2, root, flits))
    # num-dirs must be a power of two (gem5 address interleaving), so the
    # scale cases use 16 directories while the collective world is num-cpus.
    matrix.append(("tensor-3x3-r4-f16", 9, 16, 3, 4, 16))
    matrix.append(("tensor-4x4-r5-f64", 16, 16, 4, 5, 64))
    return matrix


def parse_stats(path):
    values = {}
    pattern = re.compile(r"^(\S+)\s+([0-9.eE+-]+)\s")
    for line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match:
            values[match.group(1)] = float(match.group(2))
    return values


def write_replay(path, cpus, root, flits):
    request = {
        "id": "h2-0",
        "trace_event_id": "h2-0",
        "iteration": 0,
        "phase": "measurement",
        "operation": "all_reduce",
        "participant_routers": list(range(cpus)),
        "reduction_root_router": root,
        "release_cycle": 0,
        "source_tensor_bytes": flits * 16,
        "scaled_event_bytes": flits * 16,
        "tensor_flits": flits,
        "chunks": [{
            "chunk_id": "h2-0-chunk-000000",
            "payload_bytes": flits * 16,
            "packet_flits": flits,
            "lane_start": 0,
            "lane_count": flits,
        }],
    }
    replay = {
        "schema": "lab4.garnet_tensor_allreduce_replay.v1",
        "source_trace_schema": "lab4.ai_collective_trace.v1",
        "world_size": cpus,
        "rank_to_router": list(range(cpus)),
        "network_clock_ghz": 1.0,
        "flit_bytes": 16,
        "chunk_bytes": 4096,
        "byte_scale": 1.0,
        "time_scale": 1.0,
        "selected_phases": ["measurement"],
        "reduction_root_rank": root,
        "reduction_root_router": root,
        "lowering": {},
        "source_event_count": 1,
        "selected_all_reduce_event_count": 1,
        "request_count": 1,
        "total_tensor_bytes": flits * 16,
        "total_tensor_flits": flits,
        "total_chunk_count": 1,
        "total_contribution_flits": flits * cpus,
        "requests": [request],
    }
    path.write_text(json.dumps(replay, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def run_case(gem5, output_root, case):
    name, cpus, dirs, rows, root, flits = case
    output = output_root / name
    output.mkdir(parents=True, exist_ok=False)
    replay = output / "tensor_replay.json"
    write_replay(replay, cpus, root, flits)
    command = [
        str(gem5),
        "-d",
        str(output),
        str(CONFIG),
        "--network=garnet",
        "--topology=Mesh_XY",
        f"--num-cpus={cpus}",
        f"--num-dirs={dirs}",
        f"--mesh-rows={rows}",
        "--routing-algorithm=1",
        "--sim-cycles=10000000",
        "--lab4-all-reduce",
        "--collective-tensor",
        f"--all-reduce-replay-file={replay}",
    ]
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=os.environ.copy(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    (output / "sim.log").write_text(result.stdout, encoding="utf-8")

    errors = []
    if result.returncode != 0:
        errors.append(f"gem5 returned {result.returncode}")
    if "because Lab4 collective completed" not in result.stdout:
        errors.append("simulation did not use completion-driven exit")
    completion = (
        f"Lab4 tensor collective 0 delivered {flits} lanes to all "
        f"{cpus} routers"
    )
    if completion not in result.stdout:
        errors.append("tensor collective did not complete every lane")

    stats_path = output / "stats.txt"
    if not stats_path.exists():
        errors.append("stats.txt is missing")
        return name, errors

    stats = parse_stats(stats_path)
    prefix = "system.ruby.network."
    expected = {
        "collective_rounds_completed": 1,
        "collective_deliveries": cpus * flits,
        "collective_source_flits": cpus * flits,
        "collective_router_flits": (3 * cpus - 2) * flits,
        "collective_reduce_merges": cpus * flits,
        "collective_tensor_requests_completed": 1,
        "collective_tensor_lanes_delivered": cpus * flits,
    }
    for stat, wanted in expected.items():
        actual = stats.get(prefix + stat)
        if actual != wanted:
            errors.append(f"{stat}: expected {wanted}, got {actual}")
    return name, errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gem5", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    gem5 = args.gem5 or REPO_ROOT / "build" / "Garnet_standalone" / "gem5.opt"
    if not gem5.is_file():
        parser.error(f"gem5 binary does not exist: {gem5}")
    output_root = args.output or Path(
        tempfile.mkdtemp(prefix="lab4-tensor-matrix-")
    )
    matrix = cases()
    failures = []
    with concurrent.futures.ThreadPoolExecutor(
            max_workers=args.jobs) as pool:
        futures = [pool.submit(run_case, gem5, output_root, case)
                   for case in matrix]
        for future in concurrent.futures.as_completed(futures):
            name, errors = future.result()
            if errors:
                failures.append((name, errors))
                print(f"FAIL {name}: {'; '.join(errors)}")
            else:
                print(f"PASS {name}")
    print(f"artifacts: {output_root}")
    if failures:
        print(f"FAIL: {len(failures)} of {len(matrix)} tensor cases")
        return 1
    print(f"PASS: all {len(matrix)} Lab4 tensor cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
