#!/usr/bin/env python3

import argparse
import concurrent.futures
import os
import random
import subprocess
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG = REPO_ROOT / "configs" / "example" / "garnet_synth_traffic.py"

CASES = (
    ("2x2-local", 4, 4, 2, 0, "0"),
    ("2x2-remote", 4, 4, 2, 0, "3"),
    ("2x2-split", 4, 4, 2, 0, "1,2"),
    ("2x2-exclude-source", 4, 4, 2, 3, "0,1,2"),
    ("3x3-center-row", 9, 16, 3, 4, "3,4,5"),
    ("3x3-center-column", 9, 16, 3, 4, "1,7"),
    ("3x3-corner-mixed", 9, 16, 3, 0, "0,2,4,8"),
    ("3x3-random", 9, 16, 3, 8, "random:5"),
)


def destinations(spec, cpus, seed):
    if spec == "all":
        return list(range(cpus))
    if spec.startswith("random:"):
        size = int(spec.split(":", 1)[1])
        return sorted(random.Random(seed).sample(range(cpus), size))
    return sorted({int(item) for item in spec.split(",")})


def tree_edges(cpus, rows, source, members):
    cols = cpus // rows
    source_x = source % cols
    source_y = source // cols
    edges = set()
    for member in members:
        node = member
        while node != source:
            x = node % cols
            y = node // cols
            if x != source_x:
                parent = y * cols + x + (1 if source_x > x else -1)
            else:
                parent = (y + (1 if source_y > y else -1)) * cols + x
            edges.add((parent, node))
            node = parent
    return len(edges)


def parse_stats(path):
    stats = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) >= 2:
            try:
                stats[fields[0]] = float(fields[1])
            except ValueError:
                pass
    return stats


def run_case(gem5, output_root, rounds, seed, case):
    name, cpus, dirs, rows, source, spec = case
    output = output_root / name
    members = destinations(spec, cpus, seed)
    command = [
        str(gem5), "-d", str(output), str(CONFIG),
        "--network=garnet", "--topology=Mesh_XY",
        f"--num-cpus={cpus}", f"--num-dirs={dirs}", f"--mesh-rows={rows}",
        "--routing-algorithm=1", "--sim-cycles=10000000",
        "--multicast-mode=tree_multicast",
        f"--multicast-source={source}",
        f"--multicast-destinations={spec}",
        f"--multicast-rounds={rounds}", f"--multicast-seed={seed}",
    ]
    result = subprocess.run(
        command, cwd=REPO_ROOT, env=os.environ.copy(),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, check=False,
    )
    output.mkdir(parents=True, exist_ok=True)
    (output / "sim.log").write_text(result.stdout, encoding="utf-8")

    errors = []
    completion = (
        f"Lab4 collective round {rounds - 1} delivered to all "
        f"{len(members)} "
    )
    if result.returncode != 0:
        errors.append(f"gem5 returned {result.returncode}")
    if completion not in result.stdout:
        errors.append("final destination bitmap did not complete")
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
        "collective_deliveries": rounds * len(members),
        "collective_source_flits": rounds,
        "collective_router_flits": rounds
        * (len(members) + tree_edges(cpus, rows, source, members)),
        "collective_reduce_merges": 0,
    }
    for stat, wanted in expected.items():
        actual = stats.get(prefix + stat)
        if actual != wanted:
            errors.append(f"{stat}: expected {wanted}, got {actual}")
    return name, errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--gem5", type=Path,
        default=REPO_ROOT / "build" / "Garnet_standalone" / "gem5.opt",
    )
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--jobs", type=int, default=8)
    args = parser.parse_args()
    if args.rounds < 1 or args.jobs < 1:
        parser.error("--rounds and --jobs must be positive")
    if not args.gem5.is_file():
        parser.error(f"gem5 binary does not exist: {args.gem5}")

    output_root = Path(tempfile.mkdtemp(prefix="lab4-multicast-matrix-"))
    print(f"artifacts: {output_root}")
    failures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [
            pool.submit(
                run_case, args.gem5, output_root, args.rounds, args.seed, case
            )
            for case in CASES
        ]
        for future in concurrent.futures.as_completed(futures):
            name, errors = future.result()
            if errors:
                failures.append((name, errors))
                print(f"FAIL {name}: {'; '.join(errors)}")
            else:
                print(f"PASS {name}")
    if failures:
        print(f"{len(failures)}/{len(CASES)} cases failed")
        return 1
    print(f"PASS: all {len(CASES)} M1 multicast cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
