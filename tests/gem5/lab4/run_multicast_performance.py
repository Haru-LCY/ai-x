#!/usr/bin/env python3

import argparse
import concurrent.futures
import csv
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG = REPO_ROOT / "configs" / "example" / "garnet_synth_traffic.py"
MODES = ("naive_unicast", "tree_multicast")


def parse_stats(path):
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) >= 2:
            try:
                result[fields[0]] = float(fields[1])
            except ValueError:
                pass
    return result


def run_one(gem5, root, case, mode, args):
    group, packet_flits, rate, background, seed = case
    spec = "all" if group == args.cpus else f"random:{group}"
    name = (
        f"{mode}-g{group}-f{packet_flits}-r{rate:g}-"
        f"b{background:g}-s{seed}"
    )
    output = root / name
    command = [
        str(gem5), "-d", str(output), str(CONFIG),
        "--network=garnet", "--topology=Mesh_XY",
        f"--num-cpus={args.cpus}", f"--num-dirs={args.dirs}",
        f"--mesh-rows={args.rows}", "--routing-algorithm=1",
        "--sim-cycles=1000000000", f"--multicast-mode={mode}",
        f"--multicast-source={args.source}",
        f"--multicast-destinations={spec}",
        f"--multicast-packet-flits={packet_flits}",
        f"--multicast-seed={seed}", "--multicast-workload=throughput",
        f"--multicast-injection-rate={rate}",
        f"--multicast-max-outstanding={args.max_outstanding}",
        f"--multicast-warmup-rounds={args.warmup}",
        f"--multicast-measurement-rounds={args.measurement}",
        f"--multicast-cooldown-rounds={args.cooldown}",
    ]
    if background > 0:
        command.extend([
            "--multicast-background-traffic=uniform_random",
            f"--multicast-background-rate={background}",
        ])
    completed = subprocess.run(
        command, cwd=REPO_ROOT, env=os.environ.copy(),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, check=False,
    )
    output.mkdir(parents=True, exist_ok=True)
    (output / "sim.log").write_text(completed.stdout, encoding="utf-8")
    if completed.returncode != 0 or "because Lab4 collective completed" not in completed.stdout:
        raise RuntimeError(f"{name} failed; see {output / 'sim.log'}")
    stats = parse_stats(output / "stats.txt")
    prefix = "system.ruby.network."
    latencies = [
        int(value) for value in re.findall(
            r"Lab4 collective round \d+ delivered .* in (\d+) ticks",
            completed.stdout,
        )
    ]
    measured_latencies = latencies[args.warmup:args.warmup + args.measurement]
    measured = stats[prefix + "multicast_measured_requests"]
    span = stats[prefix + "multicast_measurement_ticks"]
    return {
        "mode": mode, "group_size": group, "packet_flits": packet_flits,
        "injection_rate": rate, "background_rate": background,
        "seed": seed, "source": args.source,
        "measured_requests": measured,
        "average_completion_ticks": sum(measured_latencies) / len(measured_latencies),
        "min_completion_ticks": min(measured_latencies),
        "p50_completion_ticks": sorted(measured_latencies)[len(measured_latencies) // 2],
        "p95_completion_ticks": sorted(measured_latencies)[
            min(len(measured_latencies) - 1, int(len(measured_latencies) * 0.95))
        ],
        "max_completion_ticks": max(measured_latencies),
        "completed_per_cycle": stats[prefix + "multicast_completed_per_cycle"],
        "measured_span_ticks": span,
        "internal_link_flits": stats[
            prefix + "multicast_measured_internal_link_flits"
        ],
        "physical_packets": stats[prefix + "multicast_physical_packets"],
        "replication_events": stats[prefix + "multicast_replication_events"],
        "credit_stalls": stats[prefix + "multicast_credit_stalls"],
        "logical_bytes_per_cycle": (
            measured * group * packet_flits * 16
            / span * 1000
        ),
        "artifact": str(output),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--gem5", type=Path,
        default=REPO_ROOT / "build" / "Garnet_standalone" / "gem5.opt",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--cpus", type=int, default=16)
    parser.add_argument("--dirs", type=int, default=16)
    parser.add_argument("--rows", type=int, default=4)
    parser.add_argument("--source", type=int, default=5)
    parser.add_argument("--groups", type=int, nargs="+", default=[4, 8, 16])
    parser.add_argument("--packet-flits", type=int, nargs="+", default=[1, 4, 16])
    parser.add_argument("--rates", type=float, nargs="+", default=[0.1, 0.5, 1.0])
    parser.add_argument("--background-rates", type=float, nargs="+", default=[0.0, 0.1])
    parser.add_argument("--seeds", type=int, nargs="+", default=[1, 7, 17])
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--measurement", type=int, default=100)
    parser.add_argument("--cooldown", type=int, default=20)
    parser.add_argument("--max-outstanding", type=int, default=8)
    parser.add_argument("--jobs", type=int, default=32)
    args = parser.parse_args()
    if not args.gem5.is_file():
        parser.error(f"gem5 binary does not exist: {args.gem5}")
    if args.cpus != args.rows * args.rows:
        parser.error("performance runner currently requires a square Mesh")
    if any(group < 1 or group > args.cpus for group in args.groups):
        parser.error("group size lies outside the Mesh")
    root = args.output or Path(tempfile.mkdtemp(prefix="lab4-multicast-perf-"))
    root.mkdir(parents=True, exist_ok=True)
    print(f"artifacts: {root}")
    cases = [
        (group, packet, rate, background, seed)
        for group in args.groups for packet in args.packet_flits
        for rate in args.rates for background in args.background_rates
        for seed in args.seeds
    ]
    raw = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {
            pool.submit(run_one, args.gem5, root, case, mode, args): (case, mode)
            for case in cases for mode in MODES
        }
        for future in concurrent.futures.as_completed(futures):
            row = future.result()
            raw.append(row)
            print("PASS", Path(row["artifact"]).name)
    indexed = {
        (row["group_size"], row["packet_flits"], row["injection_rate"],
         row["background_rate"], row["seed"], row["mode"]): row
        for row in raw
    }
    paired = []
    for case in cases:
        key = case
        naive = indexed[key + ("naive_unicast",)]
        tree = indexed[key + ("tree_multicast",)]
        paired.append({
            "group_size": case[0], "packet_flits": case[1],
            "injection_rate": case[2], "background_rate": case[3],
            "seed": case[4],
            "naive_latency_ticks": naive["average_completion_ticks"],
            "tree_latency_ticks": tree["average_completion_ticks"],
            "latency_speedup": naive["average_completion_ticks"] / tree["average_completion_ticks"],
            "naive_link_flits": naive["internal_link_flits"],
            "tree_link_flits": tree["internal_link_flits"],
            "traffic_reduction": 1 - tree["internal_link_flits"] / naive["internal_link_flits"],
            "naive_throughput": naive["completed_per_cycle"],
            "tree_throughput": tree["completed_per_cycle"],
            "throughput_improvement": tree["completed_per_cycle"] / naive["completed_per_cycle"] - 1,
            "naive_logical_bytes_per_cycle": naive["logical_bytes_per_cycle"],
            "tree_logical_bytes_per_cycle": tree["logical_bytes_per_cycle"],
            "naive_artifact": naive["artifact"], "tree_artifact": tree["artifact"],
        })
    with (root / "summary.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=paired[0].keys())
        writer.writeheader()
        writer.writerows(paired)
    (root / "summary.json").write_text(
        json.dumps({"paired": paired, "raw": raw}, indent=2), encoding="utf-8"
    )
    print(f"PASS: {len(paired)} paired cases; summaries written to {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
