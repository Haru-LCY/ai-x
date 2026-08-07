#!/usr/bin/env python3

"""Run the sequential bypass acceptance gates.

The initial implementation is intentionally limited to G1.  Each case runs
the same completion-driven workload on Mesh_XY and Mesh_Bypass(mode=none),
then compares the instantiated graph and correctness/performance counters.
"""

import argparse
import concurrent.futures
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG = REPO_ROOT / "configs" / "example" / "garnet_synth_traffic.py"
STAT_RE = re.compile(r"^(system\.ruby\.network\.\S+)\s+([0-9.eE+-]+)\s")


def cases():
    return [
        ("2x2", 4, 4, 2, 0),
        ("3x3", 9, 16, 3, 4),
        ("4x4", 16, 16, 4, 15),
    ]


def g2_cases():
    fixed = REPO_ROOT / "tests" / "gem5" / "lab4" / "bypass_cases" / "fixed_4x4.json"
    return [
        ("diagonal-2x2-optimistic", 4, 4, 2, "diagonal", "checkerboard", 2, 0,
         "optimistic", 1, [(0, 3, 2, 1)]),
        ("diagonal-3x3-scaled", 9, 16, 3, "diagonal", "checkerboard", 2, 0,
         "distance_scaled", 1,
         [(0, 4, 2, 2), (2, 4, 2, 2), (4, 6, 2, 2), (4, 8, 2, 2)]),
        ("stride2-4x4-optimistic", 16, 16, 4, "stride", "symmetric", 2, 0,
         "optimistic", 3, None),
        ("fixed-4x4-scaled", 16, 16, 4, "diagonal", f"file:{fixed}", 2, 0,
         "distance_scaled", 1, [(0, 10, 4, 4), (5, 15, 4, 4)]),
        ("diagonal-4x4-budget3", 16, 16, 4, "diagonal", "checkerboard", 2, 3,
         "optimistic", 1, None),
    ]


def router_id(path):
    return int(path.rsplit("routers", 1)[1])


def normalized_topology(config_path):
    config = json.loads(config_path.read_text(encoding="utf-8"))
    network = config["system"]["ruby"]["network"]
    routers = [
        {
            "router_id": router["router_id"],
            "latency": router["latency"],
            "collective_root": router["collective_root"],
            "collective_parent_outport": router["collective_parent_outport"],
            "collective_child_inports": router["collective_child_inports"],
        }
        for router in network["routers"]
    ]
    int_links = [
        {
            "link_id": link["link_id"],
            "src": router_id(link["src_node"]),
            "dst": router_id(link["dst_node"]),
            "src_outport": link["src_outport"],
            "dst_inport": link["dst_inport"],
            "latency": link["latency"],
            "weight": link["weight"],
            "credit_link_id": link["credit_link"]["link_id"],
            "credit_latency": link["credit_link"]["link_latency"],
        }
        for link in network["int_links"]
    ]
    ext_links = [
        {
            "link_id": link["link_id"],
            "router": router_id(link["int_node"]),
            "latency": link["latency"],
        }
        for link in network["ext_links"]
    ]
    return {"routers": routers, "int_links": int_links, "ext_links": ext_links}


def parse_scalar_stats(path):
    stats = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = STAT_RE.match(line)
        if match:
            stats[match.group(1)] = float(match.group(2))
    return stats


def run_one(gem5, output, topology, cpus, dirs, rows, root, rounds):
    output.mkdir(parents=True, exist_ok=False)
    command = [
        str(gem5), "-d", str(output), str(CONFIG),
        "--network=garnet", f"--topology={topology}",
        f"--num-cpus={cpus}", f"--num-dirs={dirs}",
        f"--mesh-rows={rows}", "--routing-algorithm=1",
        "--bypass-mode=none", "--sim-cycles=10000000",
        f"--collective-rounds={rounds}", f"--collective-root={root}",
        "--lab4-all-reduce",
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
    (output / "command.json").write_text(
        json.dumps(command, indent=2) + "\n", encoding="utf-8"
    )
    (output / "sim.log").write_text(result.stdout, encoding="utf-8")
    errors = []
    if result.returncode != 0:
        errors.append(f"{topology} returned {result.returncode}")
    completion = f"Lab4 collective round {rounds - 1} delivered to all {cpus} routers"
    if completion not in result.stdout:
        errors.append(f"{topology} did not complete all destinations")
    if "because Lab4 collective completed" not in result.stdout:
        errors.append(f"{topology} did not use completion-driven exit")
    required = ("config.json", "stats.txt")
    for name in required:
        if not (output / name).is_file():
            errors.append(f"{topology} missing {name}")
    return result.returncode, errors


def run_pair(gem5, output_root, rounds, case):
    name, cpus, dirs, rows, root = case
    case_dir = output_root / name
    xy_dir = case_dir / "mesh_xy"
    bypass_dir = case_dir / "mesh_bypass_none"
    errors = []
    _, run_errors = run_one(
        gem5, xy_dir, "Mesh_XY", cpus, dirs, rows, root, rounds
    )
    errors.extend(run_errors)
    _, run_errors = run_one(
        gem5, bypass_dir, "Mesh_Bypass", cpus, dirs, rows, root, rounds
    )
    errors.extend(run_errors)
    if errors:
        return name, errors, None

    xy_graph = normalized_topology(xy_dir / "config.json")
    bypass_graph = normalized_topology(bypass_dir / "config.json")
    (case_dir / "mesh_xy.topology.json").write_text(
        json.dumps(xy_graph, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (case_dir / "mesh_bypass_none.topology.json").write_text(
        json.dumps(bypass_graph, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if xy_graph != bypass_graph:
        errors.append("normalized instantiated topology differs")

    xy_stats = parse_scalar_stats(xy_dir / "stats.txt")
    bypass_stats = parse_scalar_stats(bypass_dir / "stats.txt")
    keys = [
        "system.ruby.network.packets_injected::total",
        "system.ruby.network.packets_received::total",
        "system.ruby.network.flits_injected::total",
        "system.ruby.network.flits_received::total",
        "system.ruby.network.average_packet_network_latency",
        "system.ruby.network.average_hops",
        "system.ruby.network.collective_rounds_completed",
        "system.ruby.network.collective_deliveries",
        "system.ruby.network.collective_source_flits",
        "system.ruby.network.collective_router_flits",
        "system.ruby.network.average_collective_completion_ticks",
    ]
    compared = {}
    for key in keys:
        xy_value = xy_stats.get(key)
        bypass_value = bypass_stats.get(key)
        compared[key] = {"mesh_xy": xy_value, "mesh_bypass_none": bypass_value}
        if xy_value is None or bypass_value is None:
            errors.append(f"missing required stat {key}")
        elif xy_value != bypass_value:
            errors.append(f"stat differs: {key}: {xy_value} != {bypass_value}")

    expected_uni_links = 2 * (rows * (cpus // rows - 1) + (rows - 1) * (cpus // rows))
    evidence = {
        "case": name,
        "routers": len(bypass_graph["routers"]),
        "unidirectional_internal_links": len(bypass_graph["int_links"]),
        "expected_unidirectional_internal_links": expected_uni_links,
        "external_links": len(bypass_graph["ext_links"]),
        "stats": compared,
    }
    if len(bypass_graph["routers"]) != cpus:
        errors.append("router count is incorrect")
    if len(bypass_graph["int_links"]) != expected_uni_links:
        errors.append("ordinary internal-link count is incorrect")
    return name, errors, evidence


def run_g2_case(gem5, output_root, case):
    (name, cpus, dirs, rows, mode, placement, stride, budget, wire_model,
     base_latency, expected_links) = case
    output = output_root / name
    output.mkdir(parents=True, exist_ok=False)
    dump_path = output / "topology.json"
    command = [
        str(gem5), "-d", str(output), str(CONFIG),
        "--network=garnet", "--topology=Mesh_Bypass",
        f"--num-cpus={cpus}", f"--num-dirs={dirs}", f"--mesh-rows={rows}",
        "--routing-algorithm=1", f"--bypass-mode={mode}",
        f"--bypass-placement={placement}", f"--bypass-stride={stride}",
        f"--bypass-link-budget={budget}", f"--bypass-wire-model={wire_model}",
        f"--bypass-link-latency={base_latency}",
        f"--bypass-topology-dump={dump_path}",
        "--sim-cycles=20", "--num-packets-max=1", "--inj-vnet=0",
    ]
    result = subprocess.run(
        command, cwd=REPO_ROOT, env=os.environ.copy(), stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, check=False,
    )
    (output / "command.json").write_text(
        json.dumps(command, indent=2) + "\n", encoding="utf-8"
    )
    (output / "sim.log").write_text(result.stdout, encoding="utf-8")
    errors = []
    if result.returncode != 0:
        errors.append(f"gem5 returned {result.returncode}")
    if "because Network Tester completed simCycles" not in result.stdout:
        errors.append("simulation did not cleanly finish the construction probe")
    if not (output / "config.json").is_file():
        errors.append("config.json is missing")
    if not dump_path.is_file():
        errors.append("topology dump is missing")
    if errors:
        return name, errors, None

    config = json.loads((output / "config.json").read_text(encoding="utf-8"))
    network = config["system"]["ruby"]["network"]
    dump = json.loads(dump_path.read_text(encoding="utf-8"))
    links = network["int_links"]
    express = [link for link in links if link["src_outport"].startswith("Bypass_")]
    ordinary = [link for link in links if not link["src_outport"].startswith("Bypass_")]

    all_link_ids = [link["link_id"] for link in network["ext_links"] + links]
    if len(all_link_ids) != len(set(all_link_ids)):
        errors.append("link ids are not globally unique")
    output_ports = [(link["src_node"], link["src_outport"]) for link in links]
    input_ports = [(link["dst_node"], link["dst_inport"]) for link in links]
    if len(output_ports) != len(set(output_ports)):
        errors.append("duplicate Router output port name")
    if len(input_ports) != len(set(input_ports)):
        errors.append("duplicate Router input port name")
    for link in links:
        credit = link.get("credit_link")
        if not credit or credit.get("link_id") != link["link_id"]:
            errors.append(f"link {link['link_id']} has incomplete credit connection")

    dump_by_id = {link["link_id"]: link for link in dump["express_links"]}
    actual_pairs = {}
    for link in express:
        record = dump_by_id.get(link["link_id"])
        if record is None:
            errors.append(f"express link {link['link_id']} missing from topology dump")
            continue
        src = router_id(link["src_node"])
        dst = router_id(link["dst_node"])
        if (src, dst, link["src_outport"], link["latency"]) != (
            record["src"], record["dst"], record["name"], record["latency"]
        ):
            errors.append(f"express link {link['link_id']} disagrees with dump")
        pair = (min(src, dst), max(src, dst))
        actual_pairs.setdefault(pair, []).append(
            (src, dst, record["physical_span"], link["latency"])
        )
    for pair, directions in actual_pairs.items():
        directed = {(src, dst) for src, dst, _, _ in directions}
        if directed != {pair, (pair[1], pair[0])}:
            errors.append(f"express pair {pair} is not exactly bidirectional")
        if len({(span, latency) for _, _, span, latency in directions}) != 1:
            errors.append(f"express pair {pair} has asymmetric span or latency")

    if expected_links is not None:
        actual_undirected = sorted(
            (src, dst, values[0][2], values[0][3])
            for (src, dst), values in actual_pairs.items()
        )
        if actual_undirected != expected_links:
            errors.append(
                f"express placement mismatch: {actual_undirected} != {expected_links}"
            )
    if budget and len(actual_pairs) != budget:
        errors.append(f"link budget mismatch: {len(actual_pairs)} != {budget}")
    expected_ordinary = 2 * (
        rows * (cpus // rows - 1) + (rows - 1) * (cpus // rows)
    )
    if len(ordinary) != expected_ordinary:
        errors.append(
            f"ordinary link count changed: {len(ordinary)} != {expected_ordinary}"
        )
    if dump["express_undirected_links"] != len(actual_pairs):
        errors.append("dump undirected-link count mismatch")
    if dump["express_unidirectional_links"] != len(express):
        errors.append("dump unidirectional-link count mismatch")
    wire_length = sum(values[0][2] for values in actual_pairs.values())
    if dump["total_express_manhattan_wire_length"] != wire_length:
        errors.append("dump wire-length cost mismatch")

    evidence = {
        "case": name,
        "ordinary_unidirectional_links": len(ordinary),
        "express_undirected_links": len(actual_pairs),
        "express_unidirectional_links": len(express),
        "total_express_manhattan_wire_length": wire_length,
        "maximum_router_radix": dump["maximum_router_radix"],
        "express_latencies": sorted({link["latency"] for link in express}),
        "unique_link_ids": len(set(all_link_ids)),
        "credit_links_checked": len(links),
    }
    return name, errors, evidence


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--gem5", type=Path,
        default=REPO_ROOT / "build" / "Garnet_standalone" / "gem5.opt",
    )
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--jobs", type=int, default=3)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--gate", choices=["G1", "G2"], default="G1")
    args = parser.parse_args()
    if args.rounds < 1 or args.jobs < 1:
        parser.error("--rounds and --jobs must be positive")
    if not args.gem5.is_file():
        parser.error(f"gem5 binary does not exist: {args.gem5}")

    output_root = args.output or Path(tempfile.mkdtemp(prefix="lab4-bypass-g1-"))
    output_root.mkdir(parents=True, exist_ok=True)
    print(f"artifacts: {output_root}")
    results = []
    selected_cases = cases() if args.gate == "G1" else g2_cases()
    worker = run_pair if args.gate == "G1" else run_g2_case
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [
            (pool.submit(worker, args.gem5, output_root, args.rounds, case)
             if args.gate == "G1" else
             pool.submit(worker, args.gem5, output_root, case))
            for case in selected_cases
        ]
        for future in concurrent.futures.as_completed(futures):
            name, errors, evidence = future.result()
            results.append({"case": name, "errors": errors, "evidence": evidence})
            if errors:
                print(f"FAIL {name}: {'; '.join(errors)}")
            else:
                print(
                    f"PASS {name}: "
                    + (f"routers={evidence['routers']}, "
                       f"uni_int_links={evidence['unidirectional_internal_links']}, "
                       f"compared_stats={len(evidence['stats'])}"
                       if args.gate == "G1" else
                       f"express_bidir={evidence['express_undirected_links']}, "
                       f"wire={evidence['total_express_manhattan_wire_length']}, "
                       f"credit_links={evidence['credit_links_checked']}")
                )
    results.sort(key=lambda item: item["case"])
    (output_root / f"{args.gate.lower()}-summary.json").write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    failures = [result for result in results if result["errors"]]
    if failures:
        print(
            f"FAIL: {len(failures)}/{len(results)} {args.gate} cases failed"
        )
        return 1
    label = (
        "baseline-equivalence pairs"
        if args.gate == "G1"
        else "link-construction cases"
    )
    print(f"PASS: all {len(results)} {args.gate} {label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
