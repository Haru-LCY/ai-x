#!/usr/bin/env python3

"""Run a compiled Lab4 collective replay on paired Garnet topologies."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG = REPO_ROOT / "configs/example/garnet_synth_traffic.py"


def parse_stats(path):
    result = {}
    if not path.exists():
        return result
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) >= 2:
            try:
                result[fields[0]] = float(fields[1])
            except ValueError:
                pass
    return result


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


def run_case(gem5, replay, output, design, sim_cycles):
    output.mkdir(parents=True, exist_ok=True)
    command = [
        str(gem5), "-d", str(output), str(CONFIG),
        "--network=garnet", f"--topology={'Mesh_XY' if design == 'mesh_xy' else 'Mesh_Bypass'}",
        "--num-cpus=8", "--num-dirs=8", "--mesh-rows=4",
        f"--routing-algorithm={'1' if design == 'mesh_xy' else '2'}",
        f"--sim-cycles={sim_cycles}",
        "--multicast-mode=tree_multicast",
        f"--multicast-replay-file={replay}",
        "--multicast-packet-flits=1",
        "--multicast-workload=latency",
    ]
    if design == "mesh_bypass":
        command += [
            "--bypass-mode=diagonal", "--bypass-link-budget=4",
            "--bypass-wire-model=distance_scaled",
        ]
    result = subprocess.run(
        command, cwd=REPO_ROOT, env=os.environ.copy(),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, check=False,
    )
    (output / "sim.log").write_text(result.stdout, encoding="utf-8")
    stats = parse_stats(output / "stats.txt")
    prefix = "system.ruby.network."
    row = {
        "design": design,
        "returncode": result.returncode,
        "completed": result.returncode == 0 and
        "Lab4 collective completed" in result.stdout,
        "collective_source_flits": int(stats.get(prefix + "collective_source_flits", -1)),
        "multicast_logical_requests": int(stats.get(prefix + "multicast_logical_requests", -1)),
        "multicast_physical_packets": int(stats.get(prefix + "multicast_physical_packets", -1)),
        "multicast_measured_requests": int(stats.get(prefix + "multicast_measured_requests", -1)),
        "multicast_measurement_ticks": int(stats.get(prefix + "multicast_measurement_ticks", -1)),
        "multicast_p95_completion_ticks": int(
            stats.get(prefix + "multicast_p95_completion_ticks", -1)
        ),
        "express_internal_link_flits": int(stats.get(prefix + "express_internal_link_flits", 0)),
        "physical_wire_flit_distance": int(stats.get(prefix + "physical_wire_flit_distance", -1)),
        "sim_ticks": int(stats.get("sim_ticks", -1)),
        "output": str(output),
        "command": command,
    }
    if result.returncode != 0:
        row["tail"] = result.stdout.splitlines()[-12:]
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gem5", type=Path, required=True)
    parser.add_argument("--replay", type=Path, required=True)
    parser.add_argument("--source-trace", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--sim-cycles", type=int, default=2_000_000)
    args = parser.parse_args()
    if args.sim_cycles < 1:
        parser.error("--sim-cycles must be positive")
    if not args.replay.exists():
        parser.error(f"replay does not exist: {args.replay}")
    if args.source_trace and not args.source_trace.exists():
        parser.error(f"source trace does not exist: {args.source_trace}")
    replay = json.loads(args.replay.read_text(encoding="utf-8"))
    if replay.get("schema") != "lab4.garnet_collective_replay.v1":
        parser.error("unsupported replay schema")
    expected_requests = replay.get("request_count")
    expected_flits = sum(request["packet_flits"] for request in replay["requests"])
    if expected_requests != len(replay.get("requests", [])):
        parser.error("replay request_count mismatch")
    root = args.output or Path(tempfile.mkdtemp(prefix="lab4-trace-replay-"))
    root.mkdir(parents=True, exist_ok=True)
    rows = [
        run_case(args.gem5, args.replay, root / "mesh_xy", "mesh_xy", args.sim_cycles),
        run_case(args.gem5, args.replay, root / "mesh_bypass", "mesh_bypass", args.sim_cycles),
    ]
    dirty_lines = git_output("status", "--porcelain").splitlines()
    provenance = {
        "git_revision": git_output("rev-parse", "HEAD"),
        "git_dirty": bool(dirty_lines),
        "git_dirty_paths": dirty_lines,
        "replay": str(args.replay),
        "replay_sha256": sha256(args.replay),
        "source_trace": str(args.source_trace) if args.source_trace else None,
        "source_trace_sha256": sha256(args.source_trace) if args.source_trace else None,
        "schema": replay["schema"],
        "byte_scale": replay.get("byte_scale"),
        "time_scale": replay.get("time_scale"),
        "rank_to_router": replay.get("rank_to_router"),
        "expected_requests": expected_requests,
        "expected_source_flits": expected_flits,
        "sim_cycles": args.sim_cycles,
    }
    summary = {"provenance": provenance, "rows": rows}
    for row in rows:
        print(
            f"{row['design']}: completed={row['completed']} "
            f"requests={row['multicast_logical_requests']} "
            f"source_flits={row['collective_source_flits']} "
            f"measurement_ticks={row['multicast_measurement_ticks']}"
        )
    baseline = rows[0]
    for row in rows[1:]:
        row["latency_ratio_vs_mesh_xy"] = (
            row["multicast_measurement_ticks"] /
            baseline["multicast_measurement_ticks"]
        )
        row["wire_distance_ratio_vs_mesh_xy"] = (
            row["physical_wire_flit_distance"] /
            baseline["physical_wire_flit_distance"]
        )
    (root / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (root / "provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8"
    )
    csv_fields = [
        "design", "completed", "returncode", "collective_source_flits",
        "multicast_logical_requests", "multicast_physical_packets",
        "multicast_measured_requests", "multicast_measurement_ticks",
        "multicast_p95_completion_ticks",
        "express_internal_link_flits", "physical_wire_flit_distance",
        "latency_ratio_vs_mesh_xy", "wire_distance_ratio_vs_mesh_xy",
        "output", "command",
    ]
    with (root / "raw.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=csv_fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            output_row = dict(row)
            output_row["command"] = json.dumps(row["command"])
            writer.writerow(output_row)
    failures = []
    for row in rows:
        if not row["completed"]:
            failures.append(f"{row['design']}: incomplete")
        for field, expected in (
            ("multicast_logical_requests", expected_requests),
            ("multicast_physical_packets", expected_requests),
            ("multicast_measured_requests", expected_requests),
            ("collective_source_flits", expected_flits),
        ):
            if row[field] != expected:
                failures.append(
                    f"{row['design']}: {field}={row[field]} expected={expected}"
                )
    if failures:
        print("FAIL: " + "; ".join(failures))
        return 1
    print(f"PASS: paired trace replay artifacts at {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
