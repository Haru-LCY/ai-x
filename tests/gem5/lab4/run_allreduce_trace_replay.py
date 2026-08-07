#!/usr/bin/env python3

"""Run and strictly validate a paired real-trace all-reduce replay."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG = REPO_ROOT / "configs/example/garnet_synth_traffic.py"
sys.path.insert(0, str(REPO_ROOT / "util/lab4_trace"))

from validate_replay import validate_allreduce_replay


def parse_stats(path):
    stats = {}
    if not path.exists():
        return stats
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) >= 2:
            try:
                stats[fields[0]] = float(fields[1])
            except ValueError:
                pass
    return stats


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_output(*args):
    result = subprocess.run(
        ["git", *args], cwd=REPO_ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def run_case(gem5, replay_path, output, design, sim_cycles, world_size):
    output.mkdir(parents=True, exist_ok=True)
    topology = "Mesh_XY" if design == "mesh_xy" else "Mesh_Bypass"
    command = [
        str(gem5), "-d", str(output), str(CONFIG),
        "--network=garnet", f"--topology={topology}",
        f"--num-cpus={world_size}", f"--num-dirs={world_size}",
        "--mesh-rows=4", f"--routing-algorithm={'1' if design == 'mesh_xy' else '2'}",
        f"--sim-cycles={sim_cycles}", "--lab4-all-reduce",
        f"--all-reduce-replay-file={replay_path}",
    ]
    if design == "mesh_bypass":
        command += [
            "--bypass-mode=diagonal", "--bypass-link-budget=4",
            "--bypass-wire-model=distance_scaled",
        ]
    result = subprocess.run(
        command, cwd=REPO_ROOT, env=os.environ.copy(), text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    (output / "sim.log").write_text(result.stdout, encoding="utf-8")
    stats = parse_stats(output / "stats.txt")
    prefix = "system.ruby.network."
    row = {
        "design": design,
        "returncode": result.returncode,
        "completed": result.returncode == 0 and
                     "because Lab4 collective completed" in result.stdout,
        "collective_rounds_completed": int(stats.get(prefix + "collective_rounds_completed", -1)),
        "collective_deliveries": int(stats.get(prefix + "collective_deliveries", -1)),
        "collective_source_flits": int(stats.get(prefix + "collective_source_flits", -1)),
        "collective_router_flits": int(stats.get(prefix + "collective_router_flits", -1)),
        "collective_reduce_merges": int(stats.get(prefix + "collective_reduce_merges", -1)),
        "measured_lanes": int(stats.get(prefix + "multicast_measured_requests", -1)),
        "measurement_ticks": int(stats.get(prefix + "multicast_measurement_ticks", -1)),
        "p95_lane_ticks": int(stats.get(prefix + "multicast_p95_completion_ticks", -1)),
        "express_internal_link_flits": int(stats.get(prefix + "express_internal_link_flits", 0)),
        "physical_wire_flit_distance": int(stats.get(prefix + "physical_wire_flit_distance", -1)),
        "sim_ticks": int(stats.get("simTicks", -1)),
        "output": str(output),
        "command": command,
    }
    if result.returncode != 0:
        row["tail"] = result.stdout.splitlines()[-15:]
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gem5", type=Path, required=True)
    parser.add_argument("--replay", type=Path, required=True)
    parser.add_argument("--source-trace", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--sim-cycles", type=int, default=100_000_000)
    args = parser.parse_args()
    if not args.gem5.is_file() or not args.replay.is_file() or not args.source_trace.is_file():
        parser.error("gem5, replay, and source trace must exist")
    try:
        replay = validate_allreduce_replay(
            json.loads(args.replay.read_text(encoding="utf-8"))
        )
    except (ValueError, json.JSONDecodeError) as error:
        parser.error(f"invalid all-reduce replay: {error}")
    world = replay["world_size"]
    lanes = replay["total_lane_rounds"]
    contributions = replay["total_contribution_flits"]
    expected = {
        "collective_rounds_completed": lanes,
        "collective_deliveries": lanes * world,
        "collective_source_flits": contributions,
        "collective_router_flits": lanes * (3 * world - 2),
        "collective_reduce_merges": lanes * world,
        "measured_lanes": lanes,
    }
    root = args.output or Path(tempfile.mkdtemp(prefix="lab4-allreduce-replay-"))
    root.mkdir(parents=True, exist_ok=True)
    rows = [
        run_case(args.gem5, args.replay, root / "mesh_xy", "mesh_xy", args.sim_cycles, world),
        run_case(args.gem5, args.replay, root / "mesh_bypass", "mesh_bypass", args.sim_cycles, world),
    ]
    dirty = git_output("status", "--porcelain").splitlines()
    provenance = {
        "git_revision": git_output("rev-parse", "HEAD"),
        "git_dirty": bool(dirty),
        "git_dirty_paths": dirty,
        "source_trace": str(args.source_trace),
        "source_trace_sha256": sha256(args.source_trace),
        "replay": str(args.replay),
        "replay_sha256": sha256(args.replay),
        "schema": replay["schema"],
        "byte_scale": replay["byte_scale"],
        "time_scale": replay["time_scale"],
        "rank_to_router": replay["rank_to_router"],
        "expected_events": replay["request_count"],
        "expected_lane_rounds": lanes,
        "expected_contribution_flits": contributions,
        "sim_cycles": args.sim_cycles,
    }
    failures = []
    for row in rows:
        print(
            f"{row['design']}: completed={row['completed']} "
            f"lanes={row['collective_rounds_completed']} "
            f"source_flits={row['collective_source_flits']} "
            f"measurement_ticks={row['measurement_ticks']}"
        )
        if not row["completed"]:
            failures.append(f"{row['design']}: incomplete")
        for field, wanted in expected.items():
            if row[field] != wanted:
                failures.append(
                    f"{row['design']}: {field}={row[field]} expected={wanted}"
                )
    baseline = rows[0]
    for row in rows:
        row["latency_ratio_vs_mesh_xy"] = (
            row["measurement_ticks"] / baseline["measurement_ticks"]
            if baseline["measurement_ticks"] > 0 else None
        )
        row["wire_ratio_vs_mesh_xy"] = (
            row["physical_wire_flit_distance"] /
            baseline["physical_wire_flit_distance"]
            if baseline["physical_wire_flit_distance"] > 0 else None
        )
    summary = {"provenance": provenance, "expected": expected, "rows": rows}
    (root / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (root / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    fields = [
        "design", "completed", "returncode", *expected,
        "measurement_ticks", "p95_lane_ticks", "express_internal_link_flits",
        "physical_wire_flit_distance", "sim_ticks", "latency_ratio_vs_mesh_xy",
        "wire_ratio_vs_mesh_xy", "output", "command",
    ]
    with (root / "raw.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            record = dict(row)
            record["command"] = json.dumps(row["command"])
            writer.writerow(record)
    if failures:
        print("FAIL: " + "; ".join(failures))
        return 1
    print(f"PASS: paired all-reduce replay artifacts at {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
