#!/usr/bin/env python3

"""Run the G10 multicast × bypass factorial with completion/stat checks."""

import argparse
import concurrent.futures
import csv
import json
import os
import subprocess
import tempfile
from pathlib import Path

from run_multicast_matrix import CASES, MODES, destinations, parse_stats, tree_edges


REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG = REPO_ROOT / "configs" / "example" / "garnet_synth_traffic.py"
DESIGNS = ("mesh_xy", "mesh_bypass")
WIRE_MODELS = ("optimistic", "distance_scaled")


def all_cases():
    cases = list(CASES)
    for mask in range(1, 1 << 4):
        spec = ",".join(str(router) for router in range(4) if mask & (1 << router))
        cases.append((f"2x2-mask-{mask:02x}", 4, 4, 2, 0, spec))
    return cases


def run_case(gem5, root, rounds, seed, packet_flits, mode, design, wire_model, case):
    name, cpus, dirs, rows, source, spec = case
    suffix = "mesh_xy" if design == "mesh_xy" else f"mesh_bypass-{wire_model}"
    case_name = f"{suffix}-{mode}-{name}-f{packet_flits}"
    output = root / case_name
    members = destinations(spec, cpus, seed)
    command = [
        str(gem5), "-d", str(output), str(CONFIG),
        "--network=garnet", f"--topology={'Mesh_XY' if design == 'mesh_xy' else 'Mesh_Bypass'}",
        f"--num-cpus={cpus}", f"--num-dirs={dirs}", f"--mesh-rows={rows}",
        f"--routing-algorithm={'1' if design == 'mesh_xy' else '2'}",
        "--sim-cycles=100000000", f"--multicast-mode={mode}",
        f"--multicast-source={source}", f"--multicast-destinations={spec}",
        f"--multicast-rounds={rounds}", f"--multicast-seed={seed}",
        f"--multicast-packet-flits={packet_flits}",
    ]
    if design == "mesh_bypass":
        command.extend([
            "--bypass-mode=diagonal", "--bypass-placement=checkerboard",
            f"--bypass-wire-model={wire_model}",
            f"--bypass-topology-dump={output / 'topology.json'}",
        ])
    completed = subprocess.run(
        command, cwd=REPO_ROOT, env=os.environ.copy(),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, check=False,
    )
    output.mkdir(parents=True, exist_ok=True)
    (output / "command.json").write_text(json.dumps(command, indent=2) + "\n")
    (output / "sim.log").write_text(completed.stdout, encoding="utf-8")
    errors = []
    completion = (
        f"Lab4 collective round {rounds - 1} delivered to all {len(members)} "
    )
    if completed.returncode != 0:
        errors.append(f"gem5 returned {completed.returncode}")
    if completion not in completed.stdout:
        errors.append("final destination bitmap did not complete")
    if "because Lab4 collective completed" not in completed.stdout:
        errors.append("simulation did not use completion-driven exit")
    stats_path = output / "stats.txt"
    if not stats_path.exists():
        errors.append("stats.txt is missing")
        return {"case": case_name, "errors": errors, "artifact": str(output)}
    stats = parse_stats(stats_path)
    prefix = "system.ruby.network."
    remote_members = [member for member in members if member != source]
    is_tree = mode == "tree_multicast"
    expected = {
        "collective_rounds_completed": rounds,
        "collective_deliveries": rounds * len(members),
        "collective_source_flits": rounds
        * (1 if is_tree else len(remote_members)) * packet_flits,
        "collective_router_flits": rounds
        * (len(members) + tree_edges(cpus, rows, source, members))
        * packet_flits if is_tree else 0,
        "collective_reduce_merges": 0,
        "multicast_logical_requests": rounds,
        "multicast_physical_packets": rounds
        * (1 if is_tree else len(remote_members)),
    }
    for stat, wanted in expected.items():
        actual = stats.get(prefix + stat)
        if actual != wanted:
            errors.append(f"{stat}: expected {wanted}, got {actual}")
    if design == "mesh_bypass":
        topology_path = output / "topology.json"
        if not topology_path.exists():
            errors.append("topology.json is missing")
        else:
            topology = json.loads(topology_path.read_text())
            oracle = topology.get("routing_oracle", {})
            if not oracle.get("channel_dependency", {}).get("dag"):
                errors.append("bypass routing oracle is not DAG")
            if oracle.get("all_pairs") != cpus * cpus:
                errors.append("bypass routing oracle all-pairs mismatch")
    return {
        "case": case_name, "errors": errors, "design": design,
        "wire_model": wire_model if design == "mesh_bypass" else "baseline",
        "mode": mode, "name": name, "size": rows, "source": source,
        "members": members, "packet_flits": packet_flits, "seed": seed,
        "rounds": rounds, "collective_deliveries": expected["collective_deliveries"],
        "collective_source_flits": expected["collective_source_flits"],
        "collective_router_flits": expected["collective_router_flits"],
        "multicast_physical_packets": expected["multicast_physical_packets"],
        "artifact": str(output),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gem5", type=Path, default=REPO_ROOT / "build" / "Garnet_standalone" / "gem5.opt")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--rounds", type=int, default=100)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--packet-flits", type=int, nargs="+", default=[1, 4, 16, 64])
    parser.add_argument("--jobs", type=int, default=32)
    args = parser.parse_args()
    if not args.gem5.is_file():
        parser.error(f"gem5 binary does not exist: {args.gem5}")
    root = args.output or Path(tempfile.mkdtemp(prefix="lab4-multicast-bypass-"))
    root.mkdir(parents=True, exist_ok=True)
    cases = all_cases()
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    work = [
        (packet, mode, design, wire, case)
        for packet in args.packet_flits for mode in MODES
        for design in DESIGNS for wire in (WIRE_MODELS if design == "mesh_bypass" else ("baseline",))
        for case in cases
    ]
    raw = []
    print(f"artifacts: {root}")
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {
            pool.submit(run_case, args.gem5, root, args.rounds, args.seed,
                        packet, mode, design, wire, case): (packet, mode, design, wire, case)
            for packet, mode, design, wire, case in work
        }
        for future in concurrent.futures.as_completed(futures):
            row = future.result()
            raw.append(row)
            print("PASS" if not row["errors"] else "FAIL", row["case"])
    raw.sort(key=lambda row: row["case"])
    (root / "raw.json").write_text(json.dumps(raw, indent=2) + "\n")
    failures = [row for row in raw if row["errors"]]
    if failures:
        print(f"FAIL: {len(failures)}/{len(raw)} runs failed")
        return 1
    index = {row["case"]: row for row in raw}
    paired = []
    for packet, mode, design, wire, case in work:
        if design != "mesh_bypass":
            continue
        name = case[0]
        prefix = f"{mode}-{name}-f{packet}"
        mesh = index[f"mesh_xy-{prefix}"]
        bypass = index[f"mesh_bypass-{wire}-{prefix}"]
        paired.append({
            "mode": mode, "wire_model": wire, "case": name,
            "packet_flits": packet, "seed": args.seed, "size": case[3],
            "mesh_deliveries": mesh["collective_deliveries"],
            "bypass_deliveries": bypass["collective_deliveries"],
            "mesh_source_flits": mesh["collective_source_flits"],
            "bypass_source_flits": bypass["collective_source_flits"],
            "mesh_router_flits": mesh["collective_router_flits"],
            "bypass_router_flits": bypass["collective_router_flits"],
            "mesh_physical_packets": mesh["multicast_physical_packets"],
            "bypass_physical_packets": bypass["multicast_physical_packets"],
            "mesh_artifact": mesh["artifact"], "bypass_artifact": bypass["artifact"],
        })
    (root / "paired.json").write_text(json.dumps(paired, indent=2) + "\n")
    (root / "manifest.json").write_text(json.dumps({
        "git_revision": revision,
        "rounds": args.rounds, "seed": args.seed, "packet_flits": args.packet_flits,
        "cases": len(cases), "runs": len(raw), "paired": len(paired),
        "factorial": ["naive_unicast", "tree_multicast", "mesh_xy",
                      "mesh_bypass-diagonal"],
    }, indent=2) + "\n")
    print(f"PASS: {len(raw)} runs, {len(paired)} paired bypass cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
