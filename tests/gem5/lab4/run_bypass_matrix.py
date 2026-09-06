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
import sys
import tempfile


REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG = REPO_ROOT / "configs" / "example" / "garnet_synth_traffic.py"
sys.path.insert(0, str(REPO_ROOT / "configs"))

from topologies.bypass_oracle import build_oracle  # noqa: E402


STAT_RE = re.compile(r"^(system\.ruby\.\S+)\s+([0-9.eE+-]+)\s")


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


def g3_cases():
    fixed = REPO_ROOT / "tests" / "gem5" / "lab4" / "bypass_cases" / "fixed_4x4.json"
    return [
        ("none-2x2", 4, 4, 2, "none", "checkerboard", 2, 0),
        ("diagonal-2x2", 4, 4, 2, "diagonal", "checkerboard", 2, 2),
        ("diagonal-3x3", 9, 16, 3, "diagonal", "checkerboard", 2, 20),
        ("stride2-4x4", 16, 16, 4, "stride", "symmetric", 2, 156),
        ("fixed-4x4", 16, 16, 4, "diagonal", f"file:{fixed}", 2, 22),
    ]


def g4_cases():
    fixed = REPO_ROOT / "tests" / "gem5" / "lab4" / "bypass_cases" / "fixed_4x4.json"
    return [
        ("none-4x4-0to15", 16, 16, 4, "none", "checkerboard", 0, 15,
         [0, 1, 2, 3, 7, 11, 15]),
        ("diagonal-3x3-0to8", 9, 16, 3, "diagonal", "checkerboard", 0, 8,
         [0, 4, 5, 8]),
        ("diagonal-3x3-8to0", 9, 16, 3, "diagonal", "checkerboard", 8, 0,
         [8, 4, 3, 0]),
        ("diagonal-3x3-no-shortcut", 9, 16, 3, "diagonal", "checkerboard",
         0, 1, [0, 1]),
        ("stride2-4x4-0to3", 16, 16, 4, "stride", "symmetric", 0, 3,
         [0, 1, 3]),
        ("stride2-4x4-3to0", 16, 16, 4, "stride", "symmetric", 3, 0,
         [3, 2, 0]),
        ("stride2-4x4-multihop-0to15", 16, 16, 4, "stride", "symmetric",
         0, 15, [0, 1, 3, 7, 15]),
        ("fixed-4x4-0to15", 16, 16, 4, "diagonal", f"file:{fixed}", 0, 15,
         [0, 10, 11, 15]),
    ]


def g5_cases():
    packet_flits = (1, 2, 4, 8, 16, 64)
    cases = []
    for flits in packet_flits:
        cases.append(
            (f"default-diagonal-0to8-f{flits}", 0, 8, flits, False)
        )
        cases.append(
            (f"restricted-diagonal-8to0-f{flits}", 8, 0, flits, True)
        )
    cases.append(
        ("restricted-stride-bit-complement-contention", None,
         "bit_complement", 5, True)
    )
    cases.append(
        ("restricted-stride-opposing-contention", None, "opposing", 5, True)
    )
    return cases


def g6_cases():
    fixed = REPO_ROOT / "tests" / "gem5" / "lab4" / "bypass_cases" / "fixed_4x4.json"
    return [
        ("plain-4x4", 16, 16, 4, "none", "checkerboard", "optimistic", 0, 15),
        ("diagonal-optimistic", 9, 16, 3, "diagonal", "checkerboard",
         "optimistic", 0, 8),
        ("diagonal-scaled", 9, 16, 3, "diagonal", "checkerboard",
         "distance_scaled", 0, 8),
        ("stride-optimistic", 16, 16, 4, "stride", "symmetric",
         "optimistic", 0, 3),
        ("stride-scaled", 16, 16, 4, "stride", "symmetric",
         "distance_scaled", 0, 3),
        ("fixed-span4-scaled", 16, 16, 4, "diagonal", f"file:{fixed}",
         "distance_scaled", 0, 15),
    ]


def g7_cases():
    cases = []
    for size_name, cpus, dirs, rows in (
        ("2x2", 4, 4, 2),
        ("3x3", 9, 16, 3),
        ("4x4", 16, 16, 4),
    ):
        for mode, placement in (
            ("none", "checkerboard"),
            ("diagonal", "checkerboard"),
            ("stride", "symmetric"),
        ):
            for source in range(cpus):
                for destination in range(cpus):
                    if source != destination:
                        name = f"{size_name}-{mode}-{source}to{destination}"
                        cases.append(
                            (name, cpus, dirs, rows, mode, placement,
                             source, destination)
                        )
    return cases


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


def run_g3_case(gem5, output_root, case):
    name, cpus, dirs, rows, mode, placement, stride, expected_bypass_pairs = case
    output = output_root / name
    output.mkdir(parents=True, exist_ok=False)
    dump_path = output / "topology.json"
    command = [
        str(gem5), "-d", str(output), str(CONFIG),
        "--network=garnet", "--topology=Mesh_Bypass",
        f"--num-cpus={cpus}", f"--num-dirs={dirs}", f"--mesh-rows={rows}",
        "--routing-algorithm=2", f"--bypass-mode={mode}",
        f"--bypass-placement={placement}", f"--bypass-stride={stride}",
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
        errors.append("custom-routing configuration did not cleanly instantiate")
    for required in (output / "config.json", dump_path):
        if not required.is_file():
            errors.append(f"missing {required.name}")
    if errors:
        return name, errors, None

    topology = json.loads(dump_path.read_text(encoding="utf-8"))
    rebuilt = build_oracle(topology)
    embedded = topology.get("routing_oracle")
    if embedded != rebuilt:
        errors.append("embedded oracle differs from independent rebuild")
    config = json.loads((output / "config.json").read_text(encoding="utf-8"))
    configured_hops = config["system"]["ruby"]["network"]["bypass_first_hops"]
    if configured_hops != rebuilt["first_hops"]:
        errors.append("C++ first-hop parameter differs from audited oracle")
    routes = rebuilt["routes"]
    if len(routes) != cpus * cpus:
        errors.append(f"route count mismatch: {len(routes)} != {cpus * cpus}")
    pairs = {(route["source"], route["destination"]) for route in routes}
    if len(pairs) != cpus * cpus:
        errors.append("route table is not deterministic and complete")
    for route in routes:
        if route["path"][-1] != route["destination"]:
            errors.append(
                f"route does not terminate: "
                f"{route['source']}->{route['destination']}"
            )
        if len(route["path"]) != len(set(route["path"])):
            errors.append(f"route loops: {route['source']}->{route['destination']}")
        rank = route.get("remaining_route_rank", [])
        if any(left <= right for left, right in zip(rank, rank[1:])):
            errors.append(
                f"route rank is not decreasing: "
                f"{route['source']}->{route['destination']}"
            )
    if rebuilt["bypass_pairs"] != expected_bypass_pairs:
        errors.append(
            f"bypass pair count {rebuilt['bypass_pairs']} != {expected_bypass_pairs}"
        )
    if mode == "stride" and not any(
        route["express_hops"] >= 2 for route in routes
    ):
        errors.append("stride oracle did not construct any multi-hop route")
    dependency = rebuilt["channel_dependency"]
    if not dependency["dag"]:
        errors.append("channel dependency graph is not a DAG")
    if len(dependency["topological_order"]) != dependency["channels"]:
        errors.append("channel topological order is incomplete")
    oracle_path = output / "route-oracle.json"
    oracle_path.write_text(
        json.dumps(rebuilt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    evidence = {
        "case": name,
        "all_pairs": rebuilt["all_pairs"],
        "nonlocal_pairs": rebuilt["nonlocal_pairs"],
        "bypass_pairs": rebuilt["bypass_pairs"],
        "bypass_hops": rebuilt["bypass_hops"],
        "multi_hop": rebuilt["multi_hop"],
        "channels": dependency["channels"],
        "dependencies": dependency["dependencies"],
        "dag": dependency["dag"],
        "deterministic_routes": len(pairs),
    }
    return name, errors, evidence


def run_g4_case(gem5, output_root, case):
    name, cpus, dirs, rows, mode, placement, source, destination, expected_path = case
    output = output_root / name
    output.mkdir(parents=True, exist_ok=False)
    dump_path = output / "topology.json"
    command = [
        str(gem5), "-d", str(output), str(CONFIG),
        "--network=garnet", "--topology=Mesh_Bypass",
        f"--num-cpus={cpus}", f"--num-dirs={dirs}", f"--mesh-rows={rows}",
        "--routing-algorithm=2", f"--bypass-mode={mode}",
        f"--bypass-placement={placement}",
        f"--bypass-topology-dump={dump_path}",
        f"--single-sender-id={source}", f"--single-dest-id={destination}",
        "--num-packets-max=1", "--inj-vnet=0", "--injectionrate=1",
        "--sim-cycles=10000",
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
    for required in (output / "config.json", output / "stats.txt", dump_path):
        if not required.is_file():
            errors.append(f"missing {required.name}")
    if errors:
        return name, errors, None

    topology = json.loads(dump_path.read_text(encoding="utf-8"))
    oracle = build_oracle(topology)
    route = next(
        item for item in oracle["routes"]
        if item["source"] == source and item["destination"] == destination
    )
    if route["path"] != expected_path:
        errors.append(f"oracle path {route['path']} != {expected_path}")
    expected_express = sum(
        channel.startswith("Bypass_") for channel in route["channels"]
    )
    expected_ordinary = len(route["channels"]) - expected_express
    stats = parse_scalar_stats(output / "stats.txt")
    prefix = "system.ruby.network."
    expected_stats = {
        "packets_injected::total": 1,
        "packets_received::total": 1,
        "flits_injected::total": 1,
        "flits_received::total": 1,
        "average_hops": len(route["channels"]),
        "ordinary_internal_link_flits": expected_ordinary,
        "express_internal_link_flits": expected_express,
    }
    actual_stats = {}
    for stat, wanted in expected_stats.items():
        actual = stats.get(prefix + stat)
        actual_stats[stat] = actual
        if actual != wanted:
            errors.append(f"{stat}: expected {wanted}, got {actual}")
    evidence = {
        "case": name,
        "source": source,
        "destination": destination,
        "oracle_path": route["path"],
        "oracle_channels": route["channels"],
        "measured": actual_stats,
    }
    return name, errors, evidence


def run_g5_case(gem5, output_root, rounds, case):
    name, source, destination, packet_flits, restricted = case
    if source is None:
        return run_g5_contention_case(gem5, output_root, case)
    cpus, dirs, rows = 9, 16, 3
    output = output_root / name
    output.mkdir(parents=True, exist_ok=False)
    dump_path = output / "topology.json"
    command = [
        str(gem5), "-d", str(output), str(CONFIG),
        "--network=garnet", "--topology=Mesh_Bypass",
        f"--num-cpus={cpus}", f"--num-dirs={dirs}", f"--mesh-rows={rows}",
        "--routing-algorithm=2", "--bypass-mode=diagonal",
        "--bypass-placement=checkerboard",
        f"--bypass-topology-dump={dump_path}",
        "--multicast-mode=naive_unicast", f"--multicast-source={source}",
        f"--multicast-destinations={destination}",
        f"--multicast-rounds={rounds}",
        f"--multicast-packet-flits={packet_flits}",
        "--sim-cycles=100000000",
    ]
    if restricted:
        command.extend(
            [
                "--vcs-per-vnet=1",
                "--buffers-per-ctrl-vc=1",
                "--buffers-per-data-vc=1",
                "--router-latency=4",
                "--link-latency=4",
                "--multicast-workload=throughput",
                "--multicast-max-outstanding=4",
            ]
        )
    result = subprocess.run(
        command, cwd=REPO_ROOT, env=os.environ.copy(), stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, check=False,
    )
    (output / "command.json").write_text(
        json.dumps(command, indent=2) + "\n", encoding="utf-8"
    )
    (output / "sim.log").write_text(result.stdout, encoding="utf-8")
    errors = []
    completion = f"Lab4 collective round {rounds - 1} delivered to all 1 "
    if result.returncode != 0:
        errors.append(f"gem5 returned {result.returncode}")
    if completion not in result.stdout:
        errors.append("final unicast round did not complete")
    if "because Lab4 collective completed" not in result.stdout:
        errors.append("simulation did not use completion-driven exit")
    for required in (output / "stats.txt", dump_path):
        if not required.is_file():
            errors.append(f"missing {required.name}")
    if errors:
        return name, errors, None

    topology = json.loads(dump_path.read_text(encoding="utf-8"))
    oracle = build_oracle(topology)
    route = next(
        item for item in oracle["routes"]
        if item["source"] == source and item["destination"] == destination
    )
    express_hops = sum(
        channel.startswith("Bypass_") for channel in route["channels"]
    )
    ordinary_hops = len(route["channels"]) - express_hops
    total_flits = rounds * packet_flits
    expected = {
        "collective_rounds_completed": rounds,
        "collective_deliveries": rounds,
        "collective_source_flits": total_flits,
        "multicast_logical_requests": rounds,
        "multicast_physical_packets": rounds,
        "packets_injected::total": rounds,
        "packets_received::total": rounds,
        "flits_injected::total": total_flits,
        "flits_received::total": total_flits,
        "ordinary_internal_link_flits": total_flits * ordinary_hops,
        "express_internal_link_flits": total_flits * express_hops,
    }
    stats = parse_scalar_stats(output / "stats.txt")
    prefix = "system.ruby.network."
    measured = {}
    for stat, wanted in expected.items():
        actual = stats.get(prefix + stat)
        measured[stat] = actual
        if actual != wanted:
            errors.append(f"{stat}: expected {wanted}, got {actual}")
    source_stall = stats.get(
        f"system.ruby.l1_cntrl{source}.requestFromCache.m_stall_time"
    )
    if restricted and (source_stall is None or source_stall <= 0):
        errors.append(f"restricted case did not measure backpressure: {source_stall}")
    evidence = {
        "case": name,
        "rounds": rounds,
        "packet_flits": packet_flits,
        "restricted": restricted,
        "max_outstanding": 4 if restricted else 1,
        "path": route["path"],
        "source_message_buffer_stall_ticks": source_stall,
        "measured": measured,
    }
    return name, errors, evidence


def run_g5_contention_case(gem5, output_root, case):
    name, _, pattern, packet_flits, restricted = case
    cpus, dirs, rows, packets_per_source = 16, 16, 4, 10
    if pattern == "bit_complement":
        source_destinations = {
            source: cpus - 1 - source for source in range(cpus)
        }
        traffic_args = ["--synthetic=bit_complement"]
    else:
        # Exercise both directions of the same stride express channel under
        # the deterministic multi-hop DOR tie-breaking policy.
        source_destinations = {1: 3, 3: 1}
        mapping = ",".join(
            f"{source}:{destination}"
            for source, destination in source_destinations.items()
        )
        traffic_args = [f"--source-destinations={mapping}"]
    output = output_root / name
    output.mkdir(parents=True, exist_ok=False)
    dump_path = output / "topology.json"
    command = [
        str(gem5), "-d", str(output), str(CONFIG),
        "--network=garnet", "--topology=Mesh_Bypass",
        f"--num-cpus={cpus}", f"--num-dirs={dirs}", f"--mesh-rows={rows}",
        "--routing-algorithm=2", "--bypass-mode=stride",
        "--bypass-placement=symmetric",
        f"--bypass-topology-dump={dump_path}",
        f"--num-packets-max={packets_per_source}",
        "--inj-vnet=2", "--injectionrate=1", "--sim-cycles=5000000",
        "--vcs-per-vnet=1", "--buffers-per-data-vc=1",
        "--buffers-per-ctrl-vc=1", "--router-latency=4", "--link-latency=4",
    ] + traffic_args
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
    for required in (output / "stats.txt", dump_path):
        if not required.is_file():
            errors.append(f"missing {required.name}")
    if errors:
        return name, errors, None

    topology = json.loads(dump_path.read_text(encoding="utf-8"))
    oracle = build_oracle(topology)
    route_map = {
        (route["source"], route["destination"]): route
        for route in oracle["routes"]
    }
    routes = [
        route_map[(source, destination)]
        for source, destination in source_destinations.items()
    ]
    express_channels = {
        channel
        for route in routes
        for channel in route["channels"]
        if channel.startswith("Bypass_")
    }
    reverse_pairs = 0
    for channel in express_channels:
        _, src, _, dst = channel.split("_")
        if f"Bypass_{dst}_to_{src}" in express_channels:
            reverse_pairs += 1
    if pattern == "opposing" and reverse_pairs == 0:
        errors.append("traffic does not exercise opposing express directions")
    express_hops = sum(
        channel.startswith("Bypass_")
        for route in routes
        for channel in route["channels"]
    )
    all_hops = sum(len(route["channels"]) for route in routes)
    ordinary_hops = all_hops - express_hops
    sources = len(source_destinations)
    packets = sources * packets_per_source
    flits = packets * packet_flits
    expected = {
        "packets_injected::total": packets,
        "packets_received::total": packets,
        "flits_injected::total": flits,
        "flits_received::total": flits,
        "ordinary_internal_link_flits": ordinary_hops * packets_per_source
        * packet_flits,
        "express_internal_link_flits": express_hops * packets_per_source
        * packet_flits,
    }
    stats = parse_scalar_stats(output / "stats.txt")
    prefix = "system.ruby.network."
    measured = {}
    for stat, wanted in expected.items():
        actual = stats.get(prefix + stat)
        measured[stat] = actual
        if actual != wanted:
            errors.append(f"{stat}: expected {wanted}, got {actual}")
    stall_values = [
        value for key, value in stats.items()
        if key.endswith("responseFromCache.m_stall_time") and value > 0
    ]
    if len(stall_values) != sources:
        errors.append(
            f"expected {sources} stalled sources, got {len(stall_values)}"
        )
    evidence = {
        "case": name,
        "sources": sources,
        "pattern": pattern,
        "packets_per_source": packets_per_source,
        "packet_flits": packet_flits,
        "restricted": restricted,
        "opposing_express_directed_channels": reverse_pairs,
        "sources_with_positive_stall": len(stall_values),
        "total_stall_ticks": sum(stall_values),
        "measured": measured,
    }
    return name, errors, evidence


def run_g6_case(gem5, output_root, case):
    (name, cpus, dirs, rows, mode, placement, wire_model,
     source, destination) = case
    output = output_root / name
    output.mkdir(parents=True, exist_ok=False)
    dump_path = output / "topology.json"
    command = [
        str(gem5), "-d", str(output), str(CONFIG),
        "--network=garnet", "--topology=Mesh_Bypass",
        f"--num-cpus={cpus}", f"--num-dirs={dirs}", f"--mesh-rows={rows}",
        "--routing-algorithm=2", f"--bypass-mode={mode}",
        f"--bypass-placement={placement}", f"--bypass-wire-model={wire_model}",
        f"--bypass-topology-dump={dump_path}",
        f"--single-sender-id={source}", f"--single-dest-id={destination}",
        "--num-packets-max=1", "--inj-vnet=0", "--injectionrate=1",
        "--sim-cycles=10000",
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
    for required in (output / "stats.txt", dump_path):
        if not required.is_file():
            errors.append(f"missing {required.name}")
    if errors:
        return name, errors, None

    topology = json.loads(dump_path.read_text(encoding="utf-8"))
    oracle = build_oracle(topology)
    route = next(
        item for item in oracle["routes"]
        if item["source"] == source and item["destination"] == destination
    )
    spans = {link["name"]: link["physical_span"] for link in topology["express_links"]}
    express_channels = [
        channel for channel in route["channels"] if channel.startswith("Bypass_")
    ]
    express_hops = len(express_channels)
    ordinary_hops = len(route["channels"]) - express_hops
    wire_distance = ordinary_hops + sum(spans[channel] for channel in express_channels)
    skipped = wire_distance - len(route["channels"])
    extra_latency_cycles = skipped if wire_model == "distance_scaled" else 0
    # The default Ruby clock is 2 GHz (500 ticks/cycle). Each ordinary hop has
    # one Router plus one link cycle, and NI injection/ejection add 3 cycles.
    # A scaled link adds exactly span-1 link cycles without extra Router work.
    expected_latency = (
        2 * len(route["channels"]) + 3 + extra_latency_cycles
    ) * 500
    expected = {
        "average_hops": len(route["channels"]),
        "ordinary_internal_link_flits": ordinary_hops,
        "express_internal_link_flits": express_hops,
        "router_traversals": len(route["channels"]),
        "physical_wire_flit_distance": wire_distance,
        "physical_hops_skipped": skipped,
        "average_packet_network_latency": expected_latency,
        "packets_injected::total": 1,
        "packets_received::total": 1,
    }
    stats = parse_scalar_stats(output / "stats.txt")
    prefix = "system.ruby.network."
    measured = {}
    for stat, wanted in expected.items():
        actual = stats.get(prefix + stat)
        measured[stat] = actual
        if actual != wanted:
            errors.append(f"{stat}: expected {wanted}, got {actual}")
    evidence = {
        "case": name,
        "wire_model": wire_model,
        "path": route["path"],
        "channels": route["channels"],
        "measured": measured,
    }
    return name, errors, evidence


def run_g7_case(gem5, output_root, case):
    name, cpus, dirs, rows, mode, placement, source, destination = case
    output = output_root / name
    output.mkdir(parents=True, exist_ok=False)
    dump_path = output / "topology.json"
    command = [
        str(gem5), "-d", str(output), str(CONFIG),
        "--network=garnet", "--topology=Mesh_Bypass",
        f"--num-cpus={cpus}", f"--num-dirs={dirs}", f"--mesh-rows={rows}",
        "--routing-algorithm=2", f"--bypass-mode={mode}",
        f"--bypass-placement={placement}",
        f"--bypass-topology-dump={dump_path}",
        f"--single-sender-id={source}", f"--single-dest-id={destination}",
        "--num-packets-max=1", "--inj-vnet=0", "--injectionrate=1",
        "--sim-cycles=10000",
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
    for required in (output / "stats.txt", dump_path):
        if not required.is_file():
            errors.append(f"missing {required.name}")
    if errors:
        return name, errors, None

    topology = json.loads(dump_path.read_text(encoding="utf-8"))
    oracle = build_oracle(topology)
    route = next(
        item for item in oracle["routes"]
        if item["source"] == source and item["destination"] == destination
    )
    spans = {link["name"]: link["physical_span"] for link in topology["express_links"]}
    express = [
        channel for channel in route["channels"] if channel.startswith("Bypass_")
    ]
    ordinary = len(route["channels"]) - len(express)
    wire = ordinary + sum(spans[channel] for channel in express)
    expected = {
        "packets_injected::total": 1,
        "packets_received::total": 1,
        "flits_injected::total": 1,
        "flits_received::total": 1,
        "ordinary_internal_link_flits": ordinary,
        "express_internal_link_flits": len(express),
        "router_traversals": len(route["channels"]),
        "physical_wire_flit_distance": wire,
        "physical_hops_skipped": wire - len(route["channels"]),
        "average_hops": len(route["channels"]),
    }
    stats = parse_scalar_stats(output / "stats.txt")
    prefix = "system.ruby.network."
    for stat, wanted in expected.items():
        actual = stats.get(prefix + stat)
        if actual != wanted:
            errors.append(f"{stat}: expected {wanted}, got {actual}")
    evidence = {
        "case": name,
        "mode": mode,
        "source": source,
        "destination": destination,
        "path": route["path"],
        "express_hops": len(express),
        "ordinary_hops": ordinary,
        "wire_distance": wire,
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
    parser.add_argument(
        "--gate",
        choices=["G1", "G2", "G3", "G4", "G5", "G6", "G7"],
        default="G1",
    )
    args = parser.parse_args()
    if args.rounds < 1 or args.jobs < 1:
        parser.error("--rounds and --jobs must be positive")
    if not args.gem5.is_file():
        parser.error(f"gem5 binary does not exist: {args.gem5}")

    output_root = args.output or Path(tempfile.mkdtemp(prefix="lab4-bypass-g1-"))
    output_root.mkdir(parents=True, exist_ok=True)
    print(f"artifacts: {output_root}")
    results = []
    selected_cases = {
        "G1": cases,
        "G2": g2_cases,
        "G3": g3_cases,
        "G4": g4_cases,
        "G5": g5_cases,
        "G6": g6_cases,
        "G7": g7_cases,
    }[args.gate]()
    worker = {
        "G1": run_pair,
        "G2": run_g2_case,
        "G3": run_g3_case,
        "G4": run_g4_case,
        "G5": run_g5_case,
        "G6": run_g6_case,
        "G7": run_g7_case,
    }[args.gate]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        if args.gate in ("G1", "G5"):
            futures = [
                pool.submit(worker, args.gem5, output_root, args.rounds, case)
                for case in selected_cases
            ]
        else:
            futures = [
                pool.submit(worker, args.gem5, output_root, case)
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
                       (f"express_bidir={evidence['express_undirected_links']}, "
                        f"wire={evidence['total_express_manhattan_wire_length']}, "
                        f"credit_links={evidence['credit_links_checked']}"
                        if args.gate == "G2" else
                        (f"pairs={evidence['all_pairs']}, "
                         f"bypass_pairs={evidence['bypass_pairs']}, "
                         f"channels={evidence['channels']}, "
                         f"dependencies={evidence['dependencies']}, "
                         f"dag={evidence['dag']}"
                         if args.gate == "G3" else
                         (f"path={evidence['oracle_path']}, "
                          f"measured={evidence['measured']}"
                          if args.gate == "G4" else
                          (f"mode={evidence['mode']}, "
                           f"{evidence['source']}->{evidence['destination']}, "
                           f"path={evidence['path']}"
                           if args.gate == "G7" else
                          (f"model={evidence['wire_model']}, "
                           f"path={evidence['path']}, "
                           f"measured={evidence['measured']}"
                           if args.gate == "G6" else
                          (f"sources={evidence['sources']}, "
                           f"packets_per_source={evidence['packets_per_source']}, "
                           f"stalled_sources="
                           f"{evidence['sources_with_positive_stall']}"
                           if "sources" in evidence else
                           f"rounds={evidence['rounds']}, "
                           f"flits={evidence['packet_flits']}, "
                           f"restricted={evidence['restricted']}, "
                           f"path={evidence['path']}")))))))
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
    label = {
        "G1": "baseline-equivalence pairs",
        "G2": "link-construction cases",
        "G3": "route/dependency audits",
        "G4": "single-flit route/traversal cases",
        "G5": "multi-flit/backpressure cases",
        "G6": "hand-calculated statistics cases",
        "G7": "all-to-all single-flit correctness cases",
    }[args.gate]
    print(f"PASS: all {len(results)} {args.gate} {label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
