"""Run and validate the real eight-H100 tensor all-reduce replay (H5).

The committed tensor replay lowers the 15 measured all-reduce events to 15
logical tensor requests (6,720 flits per rank) instead of 6,720 scalar
rounds. This runner requires exact completion and counts on both Mesh_XY and
Mesh_Bypass, per-lane value validation (enforced by network-interface
asserts and error counters), and reports request completion percentiles,
peak router accumulator state, wire distance and express usage.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG = REPO_ROOT / "configs/example/garnet_synth_traffic.py"
SOURCE_TRACE = REPO_ROOT / "traces" / "h100_8gpu_collectives.json"
REPLAY = REPO_ROOT / "traces" / "h100_8gpu_tensor_allreduce_replay.json"


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


def parse_stats(path):
    values = {}
    pattern = re.compile(r"^(\S+)\s+([0-9.eE+-]+)\s")
    for line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match:
            values[match.group(1)] = float(match.group(2))
    return values


def run_case(gem5, output, sim_cycles, world_size, design, request_count):
    output.mkdir(parents=True, exist_ok=True)
    topology = "Mesh_XY" if design == "mesh_xy" else "Mesh_Bypass"
    command = [
        str(gem5), "-d", str(output), str(CONFIG),
        "--network=garnet", f"--topology={topology}",
        f"--num-cpus={world_size}", f"--num-dirs={world_size}",
        "--mesh-rows=4",
        f"--routing-algorithm={'1' if design == 'mesh_xy' else '2'}",
        f"--sim-cycles={sim_cycles}", "--lab4-all-reduce",
        "--collective-tensor", f"--all-reduce-replay-file={REPLAY}",
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
        "collective_rounds_completed": int(
            stats.get(prefix + "collective_rounds_completed", -1)),
        "collective_deliveries": int(
            stats.get(prefix + "collective_deliveries", -1)),
        "collective_source_flits": int(
            stats.get(prefix + "collective_source_flits", -1)),
        "collective_router_flits": int(
            stats.get(prefix + "collective_router_flits", -1)),
        "collective_reduce_merges": int(
            stats.get(prefix + "collective_reduce_merges", -1)),
        "tensor_requests_completed": int(
            stats.get(prefix + "collective_tensor_requests_completed", -1)),
        "incomplete_requests": max(0, request_count - int(
            stats.get(prefix + "collective_tensor_requests_completed", -1))),
        "tensor_lanes_delivered": int(
            stats.get(prefix + "collective_tensor_lanes_delivered", -1)),
        "p50_ticks": int(
            stats.get(prefix + "collective_tensor_p50_completion_ticks", -1)),
        "p95_ticks": int(
            stats.get(prefix + "collective_tensor_p95_completion_ticks", -1)),
        "p99_ticks": int(
            stats.get(prefix + "collective_tensor_p99_completion_ticks", -1)),
        "measurement_ticks": int(
            stats.get(prefix + "collective_tensor_measurement_ticks", -1)),
        "peak_lanes": int(
            stats.get(prefix + "collective_tensor_peak_lanes", -1)),
        "credit_stalls": int(
            stats.get(prefix + "collective_credit_stalls", -1)),
        "outvc_stalls": int(
            stats.get(prefix + "collective_outvc_stalls", -1)),
        "reduce_internal_link_flits": int(
            stats.get(prefix + "collective_reduce_internal_link_flits", -1)),
        "broadcast_internal_link_flits": int(
            stats.get(prefix + "collective_broadcast_internal_link_flits", -1)),
        "active_entries": int(
            stats.get(prefix + "collective_tensor_active_entries", -1)),
        "duplicate_deliveries": int(
            stats.get(prefix + "collective_duplicate_deliveries", -1)),
        "unexpected_deliveries": int(
            stats.get(prefix + "collective_unexpected_deliveries", -1)),
        "wrong_lane_deliveries": int(
            stats.get(prefix + "collective_wrong_lane_deliveries", -1)),
        "wrong_value_deliveries": int(
            stats.get(prefix + "collective_wrong_value_deliveries", -1)),
        "express_internal_link_flits": int(
            stats.get(prefix + "express_internal_link_flits", -1)),
        "wire_flit_distance": int(
            stats.get(prefix + "physical_wire_flit_distance", -1)),
        "sim_ticks": int(stats.get("simTicks", -1)),
        "output": str(output),
    }
    if result.returncode != 0:
        row["tail"] = result.stdout.splitlines()[-15:]
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gem5", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--sim-cycles", type=int, default=100_000_000)
    parser.add_argument("--world-size", type=int, default=8)
    args = parser.parse_args()
    gem5 = args.gem5 or REPO_ROOT / "build" / "Garnet_standalone" / "gem5.opt"
    if not gem5.is_file():
        parser.error(f"gem5 binary does not exist: {gem5}")
    output = args.output or Path(
        tempfile.mkdtemp(prefix="lab4-tensor-trace-replay-"))

    replay = json.loads(REPLAY.read_text(encoding="utf-8"))
    world = args.world_size
    lanes = replay["total_tensor_flits"]
    contributions = replay["total_contribution_flits"]
    expected = {
        "collective_rounds_completed": replay["request_count"],
        "collective_deliveries": lanes * world,
        "collective_source_flits": contributions,
        "collective_router_flits": lanes * (3 * world - 2),
        "collective_reduce_merges": contributions,
        "reduce_internal_link_flits": lanes * (world - 1),
        "broadcast_internal_link_flits": lanes * (world - 1),
        "tensor_requests_completed": replay["request_count"],
        "tensor_lanes_delivered": contributions,
        "active_entries": 0,
    }
    rows = [
        run_case(gem5, output / design, args.sim_cycles, world, design,
                 replay["request_count"])
        for design in ("mesh_xy", "mesh_bypass")
    ]
    errors = []
    for row in rows:
        tag = row["design"]
        if not row["completed"]:
            errors.append(f"{tag}: replay did not complete")
        for field, wanted in expected.items():
            if row[field] != wanted:
                errors.append(
                    f"{tag}: {field}={row[field]} expected={wanted}")
        for field in ("p50_ticks", "p95_ticks", "p99_ticks",
                      "measurement_ticks"):
            if row[field] <= 0:
                errors.append(f"{tag}: {field} not reported")
        for field in ("duplicate_deliveries", "unexpected_deliveries",
                      "wrong_lane_deliveries", "wrong_value_deliveries"):
            if row[field] != 0:
                errors.append(f"{tag}: {field}={row[field]} expected 0")
        if row["incomplete_requests"] != 0:
            errors.append(
                f"{tag}: incomplete_requests={row['incomplete_requests']}")

    provenance = {
        "git_revision": git_output("rev-parse", "HEAD"),
        "source_trace_sha256": sha256(SOURCE_TRACE),
        "tensor_replay_sha256": sha256(REPLAY),
        "flit_bytes": replay["flit_bytes"],
        "byte_scale": replay["byte_scale"],
        "time_scale": replay["time_scale"],
        "logical_events": replay["request_count"],
        "tensor_flits_per_rank": lanes,
        "contribution_flits": contributions,
        "min_chunks_per_request": min(
            len(request["chunks"]) for request in replay["requests"]),
        "max_chunks_per_request": max(
            len(request["chunks"]) for request in replay["requests"]),
        "min_flits_per_request": min(
            request["tensor_flits"] for request in replay["requests"]),
        "max_flits_per_request": max(
            request["tensor_flits"] for request in replay["requests"]),
    }
    summary = {"provenance": provenance, "expected": expected, "rows": rows}
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    csv_header = (
        "design,git_revision,source_trace_sha256,tensor_replay_sha256,"
        "completed,rounds,deliveries,source_flits,router_flits,merges,"
        "requests,incomplete_requests,lanes_delivered,p50,p95,p99,"
        "measurement_ticks,peak_lanes,active_entries,credit_stalls,"
        "outvc_stalls,reduce_internal,broadcast_internal,duplicate,"
        "unexpected,wrong_lane,wrong_value,express_flits,"
        "wire_flit_distance,sim_ticks\n"
    )
    csv_rows = []
    for row in rows:
        csv_rows.append(
            f"{row['design']},{provenance['git_revision']},"
            f"{provenance['source_trace_sha256']},"
            f"{provenance['tensor_replay_sha256']},{row['completed']},"
            f"{row['collective_rounds_completed']},"
            f"{row['collective_deliveries']},"
            f"{row['collective_source_flits']},"
            f"{row['collective_router_flits']},"
            f"{row['collective_reduce_merges']},"
            f"{row['tensor_requests_completed']},"
            f"{row['incomplete_requests']},"
            f"{row['tensor_lanes_delivered']},{row['p50_ticks']},"
            f"{row['p95_ticks']},{row['p99_ticks']},"
            f"{row['measurement_ticks']},{row['peak_lanes']},"
            f"{row['active_entries']},{row['credit_stalls']},"
            f"{row['outvc_stalls']},"
            f"{row['reduce_internal_link_flits']},"
            f"{row['broadcast_internal_link_flits']},"
            f"{row['duplicate_deliveries']},"
            f"{row['unexpected_deliveries']},{row['wrong_lane_deliveries']},"
            f"{row['wrong_value_deliveries']},"
            f"{row['express_internal_link_flits']},"
            f"{row['wire_flit_distance']},{row['sim_ticks']}\n"
        )
    (output / "summary.csv").write_text(
        csv_header + "".join(csv_rows), encoding="utf-8")

    if errors:
        print(f"FAIL: {'; '.join(errors)}")
        print(f"artifacts: {output}")
        return 1
    for row in rows:
        print(
            f"PASS {row['design']}: {row['collective_rounds_completed']} "
            f"logical requests, measurement_ticks={row['measurement_ticks']} "
            f"p50/p95/p99={row['p50_ticks']}/{row['p95_ticks']}/"
            f"{row['p99_ticks']} peak_lanes={row['peak_lanes']} "
            f"reduce/bcast_internal="
            f"{row['reduce_internal_link_flits']}/"
            f"{row['broadcast_internal_link_flits']} "
            f"wire_distance={row['wire_flit_distance']} "
            f"express_flits={row['express_internal_link_flits']}"
        )
    print(f"artifacts: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
