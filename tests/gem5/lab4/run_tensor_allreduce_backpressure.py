"""Run and validate the Lab4 tensor all-reduce backpressure matrix (H3).

Stresses the datapath with 1 VC per vnet, router latencies 1 and 4, and
multiple outstanding requests (1/2/4/8). Every case injects 100 consecutive
tensor requests whose packet sizes cycle 1..4 flits, and requires exact
source/merge/delivery/router-flit counts plus a completion-driven exit.
Wrong lane values, duplicates, credit leaks or lost state fail the run.
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

REQUESTS = 100


def cases():
    """(name, cpus, dirs, rows, root, router_latency, outstanding)"""
    matrix = []
    for cpus, dirs, rows, root in ((4, 4, 2, 0), (9, 16, 3, 0)):
        for router_latency in (1, 4):
            for outstanding in (1, 2, 4, 8):
                matrix.append((
                    f"bp-{rows}x{rows}-r{root}-rl{router_latency}-o{outstanding}",
                    cpus, dirs, rows, root, router_latency, outstanding,
                ))
    return matrix


def parse_stats(path):
    values = {}
    pattern = re.compile(r"^(\S+)\s+([0-9.eE+-]+)\s")
    for line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match:
            values[match.group(1)] = float(match.group(2))
    return values


def write_replay(path, cpus, root):
    requests = []
    total_flits = 0
    for index in range(REQUESTS):
        flits = (index % 4) + 1
        total_flits += flits
        requests.append({
            "id": f"bp-{index:04d}",
            "trace_event_id": f"bp-{index:04d}",
            "iteration": 0,
            "phase": "measurement",
            "operation": "all_reduce",
            "participant_routers": list(range(cpus)),
            "reduction_root_router": root,
            "release_cycle": index * 3,
            "source_tensor_bytes": flits * 16,
            "scaled_event_bytes": flits * 16,
            "tensor_flits": flits,
            "chunks": [{
                "chunk_id": f"bp-{index:04d}-chunk-000000",
                "payload_bytes": flits * 16,
                "packet_flits": flits,
                "lane_start": 0,
                "lane_count": flits,
            }],
        })
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
        "source_event_count": REQUESTS,
        "selected_all_reduce_event_count": REQUESTS,
        "request_count": REQUESTS,
        "total_tensor_bytes": total_flits * 16,
        "total_tensor_flits": total_flits,
        "total_chunk_count": REQUESTS,
        "total_contribution_flits": total_flits * cpus,
        "requests": requests,
    }
    path.write_text(json.dumps(replay, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    return total_flits


def run_case(gem5, output_root, case):
    name, cpus, dirs, rows, root, router_latency, outstanding = case
    output = output_root / name
    output.mkdir(parents=True, exist_ok=False)
    replay = output / "tensor_replay.json"
    total_flits = write_replay(replay, cpus, root)
    command = [
        str(gem5), "-d", str(output), str(CONFIG),
        "--network=garnet", "--topology=Mesh_XY",
        f"--num-cpus={cpus}", f"--num-dirs={dirs}", f"--mesh-rows={rows}",
        "--routing-algorithm=1", "--sim-cycles=100000000",
        "--lab4-all-reduce", "--collective-tensor",
        f"--all-reduce-replay-file={replay}",
        "--vcs-per-vnet=1",
        f"--router-latency={router_latency}",
        "--multicast-workload=throughput",
        f"--multicast-max-outstanding={outstanding}",
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

    stats_path = output / "stats.txt"
    if not stats_path.exists():
        errors.append("stats.txt is missing")
        return name, errors
    stats = parse_stats(stats_path)
    prefix = "system.ruby.network."
    expected = {
        "collective_rounds_completed": REQUESTS,
        "collective_deliveries": cpus * total_flits,
        "collective_source_flits": cpus * total_flits,
        "collective_router_flits": (3 * cpus - 2) * total_flits,
        "collective_reduce_merges": cpus * total_flits,
        "collective_tensor_requests_completed": REQUESTS,
        "collective_tensor_lanes_delivered": cpus * total_flits,
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
        tempfile.mkdtemp(prefix="lab4-tensor-backpressure-")
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
        print(f"FAIL: {len(failures)} of {len(matrix)} backpressure cases")
        return 1
    print(f"PASS: all {len(matrix)} Lab4 backpressure cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
