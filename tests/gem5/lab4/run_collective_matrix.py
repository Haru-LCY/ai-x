#!/usr/bin/env python3

"""Run and validate the Lab4 scalar collective regression matrix."""

import argparse
import concurrent.futures
import os
from pathlib import Path
import re
import subprocess
import tempfile


REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG = REPO_ROOT / "configs" / "example" / "garnet_synth_traffic.py"


def cases():
    return [
        ("allreduce-2x2-r0", "allreduce", 4, 4, 2, 0),
        ("allreduce-2x2-r3", "allreduce", 4, 4, 2, 3),
        ("allreduce-3x3-r0", "allreduce", 9, 16, 3, 0),
        ("allreduce-3x3-r4", "allreduce", 9, 16, 3, 4),
        ("allreduce-3x3-r8", "allreduce", 9, 16, 3, 8),
        ("allreduce-4x4-r0", "allreduce", 16, 16, 4, 0),
        ("allreduce-4x4-r5", "allreduce", 16, 16, 4, 5),
        ("allreduce-4x4-r15", "allreduce", 16, 16, 4, 15),
        ("multicast-2x2-r0", "multicast", 4, 4, 2, 0),
        ("multicast-3x3-r4", "multicast", 9, 16, 3, 4),
        ("multicast-4x4-r5", "multicast", 16, 16, 4, 5),
    ]


def parse_stats(path):
    values = {}
    pattern = re.compile(r"^(\S+)\s+([0-9.eE+-]+)\s")
    for line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match:
            values[match.group(1)] = float(match.group(2))
    return values


def run_case(gem5, output_root, rounds, case):
    name, mode, cpus, dirs, rows, root = case
    output = output_root / name
    output.mkdir(parents=True, exist_ok=False)
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
        f"--collective-rounds={rounds}",
        f"--collective-root={root}",
        "--lab4-all-reduce" if mode == "allreduce" else "--lab4-multicast",
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
    completion = (
        f"Lab4 collective round {rounds - 1} delivered to all {cpus} routers"
    )
    if result.returncode != 0:
        errors.append(f"gem5 returned {result.returncode}")
    if completion not in result.stdout:
        errors.append("last round did not reach every router")
    if "because Lab4 collective completed" not in result.stdout:
        errors.append("simulation did not use completion-driven exit")

    stats_path = output / "stats.txt"
    if not stats_path.exists():
        errors.append("stats.txt is missing")
        return name, errors

    stats = parse_stats(stats_path)
    prefix = "system.ruby.network."
    expected = {
        "collective_rounds_completed": rounds,
        "collective_deliveries": cpus * rounds,
        "collective_source_flits":
            (cpus if mode == "allreduce" else 1) * rounds,
        "collective_router_flits":
            ((3 * cpus - 2) if mode == "allreduce" else (2 * cpus - 1))
            * rounds,
        "collective_reduce_merges":
            (cpus if mode == "allreduce" else 0) * rounds,
    }
    for stat, wanted in expected.items():
        actual = stats.get(prefix + stat)
        if actual != wanted:
            errors.append(f"{stat}: expected {wanted}, got {actual}")

    latency = stats.get(prefix + "average_collective_completion_ticks")
    if latency is None or latency <= 0:
        errors.append(f"invalid average completion latency: {latency}")
    return name, errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--gem5",
        type=Path,
        default=REPO_ROOT / "build" / "Garnet_standalone" / "gem5.opt",
    )
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    if args.rounds < 1 or args.jobs < 1:
        parser.error("--rounds and --jobs must be positive")
    if not args.gem5.is_file():
        parser.error(f"gem5 binary does not exist: {args.gem5}")

    output_root = Path(tempfile.mkdtemp(prefix="lab4-collective-matrix-"))
    print(f"artifacts: {output_root}")
    failures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [
            pool.submit(run_case, args.gem5, output_root, args.rounds, case)
            for case in cases()
        ]
        for future in concurrent.futures.as_completed(futures):
            name, errors = future.result()
            if errors:
                failures.append((name, errors))
                print(f"FAIL {name}: {'; '.join(errors)}")
            else:
                print(f"PASS {name}")

    if failures:
        print(f"{len(failures)}/{len(cases())} cases failed")
        return 1
    print(f"PASS: all {len(cases())} Lab4 collective cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
