#!/usr/bin/env python3

"""Run reproducible, completion-checked Mesh versus bypass performance pairs."""

import argparse
import concurrent.futures
import csv
import hashlib
import json
import math
import os
import re
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG = REPO_ROOT / "configs" / "example" / "garnet_synth_traffic.py"
PREFIX = "system.ruby.network."
SOURCE_FILES = [
    "configs/example/garnet_synth_traffic.py",
    "configs/network/Network.py",
    "configs/topologies/Mesh_Bypass.py",
    "configs/topologies/bypass_oracle.py",
    "src/cpu/testers/garnet_synthetic_traffic/GarnetSyntheticTraffic.cc",
    "src/cpu/testers/garnet_synthetic_traffic/GarnetSyntheticTraffic.hh",
    "src/cpu/testers/garnet_synthetic_traffic/GarnetSyntheticTraffic.py",
    "src/mem/ruby/network/garnet/GarnetNetwork.cc",
    "src/mem/ruby/network/garnet/GarnetNetwork.hh",
    "src/mem/ruby/network/garnet/GarnetNetwork.py",
    "src/mem/ruby/network/garnet/CommonTypes.hh",
    "src/mem/ruby/network/garnet/NetworkInterface.cc",
    "src/mem/ruby/network/garnet/OutputUnit.cc",
    "src/mem/ruby/network/garnet/OutputUnit.hh",
    "src/mem/ruby/network/garnet/Router.cc",
    "src/mem/ruby/network/garnet/Router.hh",
    "src/mem/ruby/network/garnet/RoutingUnit.cc",
    "src/mem/ruby/network/garnet/SwitchAllocator.cc",
    "src/mem/ruby/network/garnet/SwitchAllocator.hh",
    "tests/gem5/lab4/run_bypass_performance.py",
]


def source_hashes():
    return {
        name: hashlib.sha256((REPO_ROOT / name).read_bytes()).hexdigest()
        for name in SOURCE_FILES
    }


def parse_blocks(path):
    text = path.read_text(encoding="utf-8")
    blocks = []
    marker = "---------- Begin Simulation Statistics ----------"
    for section in text.split(marker)[1:]:
        values = {}
        for line in section.split("---------- End Simulation Statistics")[0].splitlines():
            fields = line.split()
            if len(fields) < 2:
                continue
            try:
                values[fields[0]] = float(fields[1])
            except ValueError:
                pass
        blocks.append(values)
    return blocks


def percentile_from_sparse(stats, name, percentile):
    samples = []
    prefix = name + "::"
    for key, count in stats.items():
        suffix = key.removeprefix(prefix)
        if key.startswith(prefix) and suffix not in ("samples", "total"):
            try:
                samples.append((int(suffix), int(count)))
            except ValueError:
                pass
    total = sum(count for _, count in samples)
    if not total:
        return math.nan
    target = math.ceil(total * percentile)
    cumulative = 0
    for value, count in sorted(samples):
        cumulative += count
        if cumulative >= target:
            return value
    raise AssertionError("unreachable percentile")


def scalar(stats, name):
    value = stats.get(PREFIX + name)
    if value is None or not math.isfinite(value):
        raise ValueError(f"missing/non-finite statistic {PREFIX + name}")
    return value


def sum_suffix(stats, suffix):
    return sum(value for key, value in stats.items() if key.endswith(suffix))


def base_radix(size):
    result = []
    for y in range(size):
        for x in range(size):
            result.append(
                int(x > 0) + int(x + 1 < size)
                + int(y > 0) + int(y + 1 < size)
            )
    return result


def cost_record(size, topology=None, vcs=4, ctrl_buffers=1, data_buffers=4):
    radix = base_radix(size) if topology is None else topology["router_radix"]
    links = 0 if topology is None else topology["express_undirected_links"]
    wire = 0 if topology is None else topology[
        "total_express_manhattan_wire_length"
    ]
    input_ports = 2 * links
    return {
        "extra_undirected_links": links,
        "extra_unidirectional_links": 2 * links,
        "extra_wire_length": wire,
        "maximum_router_radix": max(radix),
        "average_router_radix": sum(radix) / len(radix),
        "extra_input_ports": input_ports,
        "extra_output_ports": input_ports,
        "extra_buffer_slots_proxy": input_ports * vcs * (
            2 * ctrl_buffers + data_buffers
        ),
    }


def case_name(case, design):
    size, traffic, packet, load, seed = case
    load_name = f"{load:.6f}".rstrip("0").rstrip(".").replace(".", "p")
    return f"{size}x{size}-{traffic}-f{packet}-l{load_name}-s{seed}-{design}"


def command_for(gem5, output, case, design, args):
    size, traffic, packet, load, seed = case
    cpus = size * size
    injection_rate = load / packet
    command = [
        str(gem5), "-d", str(output), str(CONFIG),
        "--network=garnet", f"--num-cpus={cpus}", f"--num-dirs={cpus}",
        f"--mesh-rows={size}", f"--synthetic={traffic}",
        f"--synthetic-seed={seed}", f"--synthetic-packet-flits={packet}",
        f"--inj-vnet={args.inj_vnet}",
        f"--injectionrate={injection_rate:.9f}",
        "--precision=9", f"--synthetic-warmup-cycles={args.warmup}",
        f"--synthetic-drain-cycles={args.drain}",
        f"--synthetic-measurement-cycles={args.measurement}",
        f"--synthetic-cooldown-cycles={args.cooldown}",
        "--sim-cycles=1000000000", "--sys-clock=1GHz", "--ruby-clock=2GHz",
        "--garnet-deadlock-threshold=1000000",
    ]
    if traffic == "hotspot":
        command.extend([
            f"--hotspot-destination={cpus // 2}",
            f"--hotspot-probability={args.hotspot_probability}",
        ])
    if design == "mesh_xy":
        command.extend(["--topology=Mesh_XY", "--routing-algorithm=1"])
    else:
        family, wire_model = design.split("-", 1)
        placement = "checkerboard" if family == "diagonal" else "symmetric"
        command.extend([
            "--topology=Mesh_Bypass", "--routing-algorithm=2",
            f"--bypass-mode={family}", f"--bypass-placement={placement}",
            f"--bypass-wire-model={wire_model}",
            f"--bypass-topology-dump={output / 'topology.json'}",
        ])
        if args.bypass_adaptive_routing:
            command.extend([
                "--bypass-adaptive-routing",
                "--bypass-adaptive-max-packet-flits="
                f"{args.bypass_adaptive_max_packet_flits}",
            ])
    return command


def run_one(gem5, root, case, design, args):
    output = root / case_name(case, design)
    result_path = output / "result.json"
    if args.resume and result_path.is_file():
        saved = json.loads(result_path.read_text(encoding="utf-8"))
        if not saved.get("errors") or not args.retry_failures:
            if "simulation_windows" not in saved:
                saved["simulation_windows"] = command_windows(
                    json.loads((output / "command.json").read_text())
                )
                result_path.write_text(
                    json.dumps(saved, indent=2) + "\n", encoding="utf-8"
                )
            return saved
    output.mkdir(parents=True, exist_ok=True)
    command = command_for(gem5, output, case, design, args)
    (output / "command.json").write_text(
        json.dumps(command, indent=2) + "\n", encoding="utf-8"
    )
    completed = subprocess.run(
        command, cwd=REPO_ROOT, env=os.environ.copy(),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, check=False,
    )
    (output / "sim.log").write_text(completed.stdout, encoding="utf-8")
    errors = []
    stats_path = output / "stats.txt"
    if completed.returncode:
        errors.append(f"gem5 returned {completed.returncode}")
    if not stats_path.is_file():
        errors.append("missing stats.txt")
    blocks = parse_blocks(stats_path) if stats_path.is_file() else []
    if len(blocks) < 3:
        errors.append(f"expected three stats blocks, found {len(blocks)}")
    if errors:
        row = {"case": case_name(case, design), "errors": errors,
               "artifact": str(output)}
        result_path.write_text(json.dumps(row, indent=2) + "\n", encoding="utf-8")
        return row

    warmup, measured, completed_stats = blocks[0], blocks[1], blocks[2]
    warmup_injected = scalar(warmup, "packets_injected::total")
    warmup_received = scalar(warmup, "packets_received::total")
    if warmup_injected != warmup_received:
        errors.append(
            f"warmup drain incomplete: {warmup_injected} injected, "
            f"{warmup_received} received"
        )
    packets_injected = scalar(completed_stats, "packets_injected::total")
    packets_received = scalar(completed_stats, "packets_received::total")
    flits_injected = scalar(completed_stats, "flits_injected::total")
    flits_received = scalar(completed_stats, "flits_received::total")
    if packets_injected != packets_received:
        errors.append(
            f"cooldown incomplete: {packets_injected} injected, "
            f"{packets_received} received"
        )
    if flits_injected != flits_received:
        errors.append(
            f"cooldown incomplete: {flits_injected} flits injected, "
            f"{flits_received} received"
        )
    if flits_injected != packets_injected * case[2]:
        errors.append(
            f"packet size mismatch: {flits_injected} flits for "
            f"{packets_injected} packets of {case[2]}"
        )
    wanted_ticks = args.measurement * 1000
    if measured.get("simTicks") != wanted_ticks:
        errors.append(
            f"measurement window is {measured.get('simTicks')} ticks, "
            f"expected {wanted_ticks}"
        )

    topology = None
    if design != "mesh_xy":
        topology_path = output / "topology.json"
        if not topology_path.is_file():
            errors.append("missing topology.json")
        else:
            topology = json.loads(topology_path.read_text(encoding="utf-8"))
            if topology.get("adaptive_routing") != args.bypass_adaptive_routing:
                errors.append("topology adaptive-routing metadata mismatch")
            if topology.get("adaptive_max_packet_flits") != (
                args.bypass_adaptive_max_packet_flits
            ):
                errors.append("topology adaptive packet-limit metadata mismatch")
    measured_packets = scalar(measured, "packets_received::total")
    measured_flits = scalar(measured, "flits_received::total")
    injected_packets = scalar(measured, "packets_injected::total")
    injected_flits = scalar(measured, "flits_injected::total")
    ruby_cycles = args.measurement * 2
    link_activity = {
        key.rsplit("link-", 1)[1]: value
        for key, value in measured.items()
        if key.startswith(PREFIX + "internal_link_activity::link-")
    }
    traffic_distribution = {
        key.removeprefix(PREFIX + "ctrl_traffic_distribution."): value
        for key, value in measured.items()
        if key.startswith(PREFIX + "ctrl_traffic_distribution.")
    }
    offered_distribution = {
        key: value for key, value in measured.items()
        if ".offered_destinations::dest-" in key
    }
    row = {
        "case": case_name(case, design), "errors": errors,
        "size": case[0], "traffic": case[1], "packet_flits": case[2],
        "offered_flits_per_node_cycle": case[3], "seed": case[4],
        "design": design, "injection_packets_per_node_cycle": case[3] / case[2],
        "injection_vnet": args.inj_vnet,
        "bypass_adaptive_routing": (
            design != "mesh_xy" and args.bypass_adaptive_routing
        ),
        "bypass_adaptive_max_packet_flits": (
            args.bypass_adaptive_max_packet_flits
        ),
        "measured_packets_injected": injected_packets,
        "measured_packets_received": measured_packets,
        "measured_flits_injected": injected_flits,
        "measured_flits_received": measured_flits,
        "accepted_flits_per_node_cycle": injected_flits / args.measurement / (case[0] ** 2),
        "completed_flits_per_node_cycle": measured_flits / args.measurement / (case[0] ** 2),
        "completed_packets_per_cycle": measured_packets / args.measurement,
        "average_latency_cycles": scalar(measured, "average_packet_latency") / 500,
        "average_network_latency_cycles": scalar(
            measured, "average_packet_network_latency"
        ) / 500,
        "average_queueing_latency_cycles": scalar(
            measured, "average_packet_queueing_latency"
        ) / 500,
        "p50_latency_cycles": percentile_from_sparse(
            measured, PREFIX + "packet_latency_histogram", 0.50
        ),
        "p95_latency_cycles": percentile_from_sparse(
            measured, PREFIX + "packet_latency_histogram", 0.95
        ),
        "p99_latency_cycles": percentile_from_sparse(
            measured, PREFIX + "packet_latency_histogram", 0.99
        ),
        "router_traversals": scalar(measured, "router_traversals"),
        "ordinary_link_flits": scalar(measured, "ordinary_internal_link_flits"),
        "express_link_flits": scalar(measured, "express_internal_link_flits"),
        "physical_wire_flit_distance": scalar(
            measured, "physical_wire_flit_distance"
        ),
        "physical_hops_skipped": scalar(measured, "physical_hops_skipped"),
        "average_hops": scalar(measured, "average_hops"),
        "average_link_utilization": scalar(measured, "avg_link_utilization"),
        "maximum_internal_link_utilization": (
            max(link_activity.values(), default=0) / ruby_cycles
        ),
        "average_vc_load": measured.get(PREFIX + "avg_vc_load::total", 0),
        "outvc_stalls": sum_suffix(measured, ".outvc_stalls"),
        "credit_stalls": sum_suffix(measured, ".credit_stalls"),
        "ordering_stalls": sum_suffix(measured, ".ordering_stalls"),
        "per_link_activity": link_activity,
        "traffic_distribution": traffic_distribution,
        "offered_distribution": offered_distribution,
        "express_link_ids": (
            [] if topology is None
            else [str(link["link_id"]) for link in topology["express_links"]]
        ),
        "cost": cost_record(case[0], topology),
        "simulation_windows": {
            "warmup": args.warmup,
            "drain": args.drain,
            "measurement": args.measurement,
            "cooldown": args.cooldown,
        },
        "artifact": str(output),
    }
    result_path.write_text(json.dumps(row, indent=2) + "\n", encoding="utf-8")
    return row


def command_windows(command):
    result = {}
    for name in ("warmup", "drain", "measurement", "cooldown"):
        prefix = f"--synthetic-{name}-cycles="
        value = next(item for item in command if item.startswith(prefix))
        result[name] = int(value.removeprefix(prefix))
    return result


def paired_rows(raw, cases, designs):
    indexed = {(row["case"]): row for row in raw}
    paired = []
    for case in cases:
        baseline = indexed[case_name(case, "mesh_xy")]
        for design in designs:
            bypass = indexed[case_name(case, design)]
            if baseline["offered_distribution"] != bypass["offered_distribution"]:
                raise ValueError(
                    f"paired offered source/destination sequence differs for "
                    f"{case_name(case, design)}"
                )
            row = {
                "size": case[0], "traffic": case[1], "packet_flits": case[2],
                "offered_flits_per_node_cycle": case[3], "seed": case[4],
                "design": design,
                "mesh_latency_cycles": baseline["average_latency_cycles"],
                "bypass_latency_cycles": bypass["average_latency_cycles"],
                "latency_speedup": baseline["average_latency_cycles"] /
                    bypass["average_latency_cycles"],
                "mesh_p95_latency_cycles": baseline["p95_latency_cycles"],
                "bypass_p95_latency_cycles": bypass["p95_latency_cycles"],
                "mesh_completed_flits_per_node_cycle": baseline[
                    "completed_flits_per_node_cycle"
                ],
                "bypass_completed_flits_per_node_cycle": bypass[
                    "completed_flits_per_node_cycle"
                ],
                "throughput_improvement": bypass[
                    "completed_flits_per_node_cycle"
                ] / baseline["completed_flits_per_node_cycle"] - 1,
                "mesh_router_traversals": baseline["router_traversals"],
                "bypass_router_traversals": bypass["router_traversals"],
                "mesh_router_traversals_per_flit": baseline[
                    "router_traversals"
                ] / baseline["measured_flits_received"],
                "bypass_router_traversals_per_flit": bypass[
                    "router_traversals"
                ] / bypass["measured_flits_received"],
                "router_traversal_reduction": 1 - bypass["router_traversals"] /
                    baseline["router_traversals"],
                "mesh_wire_flit_distance": baseline[
                    "physical_wire_flit_distance"
                ],
                "bypass_wire_flit_distance": bypass[
                    "physical_wire_flit_distance"
                ],
                "mesh_wire_distance_per_flit": baseline[
                    "physical_wire_flit_distance"
                ] / baseline["measured_flits_received"],
                "bypass_wire_distance_per_flit": bypass[
                    "physical_wire_flit_distance"
                ] / bypass["measured_flits_received"],
                "wire_traffic_change": bypass["physical_wire_flit_distance"] /
                    baseline["physical_wire_flit_distance"] - 1,
                "express_link_flits": bypass["express_link_flits"],
                "cost": bypass["cost"],
                "mesh_artifact": baseline["artifact"],
                "bypass_artifact": bypass["artifact"],
            }
            paired.append(row)
    return paired


def aggregate(paired):
    grouped = defaultdict(list)
    key_fields = (
        "size", "traffic", "packet_flits",
        "offered_flits_per_node_cycle", "design",
    )
    for row in paired:
        grouped[tuple(row[field] for field in key_fields)].append(row)
    metrics = (
        "mesh_latency_cycles", "bypass_latency_cycles", "latency_speedup",
        "mesh_p95_latency_cycles", "bypass_p95_latency_cycles",
        "mesh_completed_flits_per_node_cycle",
        "bypass_completed_flits_per_node_cycle", "throughput_improvement",
        "router_traversal_reduction", "wire_traffic_change",
        "mesh_router_traversals_per_flit", "bypass_router_traversals_per_flit",
        "mesh_wire_distance_per_flit", "bypass_wire_distance_per_flit",
    )
    result = []
    for key, rows in sorted(grouped.items()):
        item = dict(zip(key_fields, key))
        item["seeds"] = len(rows)
        for metric in metrics:
            values = [row[metric] for row in rows]
            item[metric + "_mean"] = sum(values) / len(values)
            item[metric + "_min"] = min(values)
            item[metric + "_max"] = max(values)
        item["cost"] = rows[0]["cost"]
        result.append(item)
    return result


def write_csv(path, rows):
    flat = []
    for row in rows:
        item = {key: value for key, value in row.items()
                if not isinstance(value, (dict, list))}
        if "cost" in row:
            item.update({"cost_" + key: value for key, value in row["cost"].items()})
        flat.append(item)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(flat[0]))
        writer.writeheader()
        writer.writerows(flat)


def svg_line_plot(path, title, rows, y_fields, y_label):
    width, height = 1000, 620
    left, right, top, bottom = 90, 30, 55, 75
    xs = sorted({row["offered_flits_per_node_cycle"] for row in rows})
    values = [row[field] for row in rows for field, _ in y_fields]
    ymin, ymax = min(values), max(values)
    if ymin == ymax:
        ymax = ymin + 1
    ymin = min(0, ymin)
    xmin, xmax = min(xs), max(xs)
    def px(value):
        if xmin == xmax:
            return (left + width - right) / 2
        return left + (value - xmin) / (xmax - xmin) * (width - left - right)
    def py(value):
        return top + (ymax - value) / (ymax - ymin) * (
            height - top - bottom
        )
    colors = ("#1f77b4", "#d62728", "#2ca02c", "#9467bd")
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{width/2}" y="28" text-anchor="middle" font-size="20">{title}</text>',
        f'<line x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}" stroke="black"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}" stroke="black"/>',
    ]
    for x in xs:
        parts.append(f'<text x="{px(x):.1f}" y="{height-bottom+24}" text-anchor="middle" font-size="12">{x:g}</text>')
    for index, (field, label) in enumerate(y_fields):
        points = " ".join(
            f"{px(row['offered_flits_per_node_cycle']):.1f},{py(row[field]):.1f}"
            for row in sorted(rows, key=lambda item: item["offered_flits_per_node_cycle"])
        )
        color = colors[index]
        parts.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2"/>')
        parts.append(f'<text x="{left+10+index*210}" y="{height-18}" fill="{color}" font-size="13">{label}</text>')
    parts.extend([
        f'<text x="{width/2}" y="{height-42}" text-anchor="middle" font-size="14">offered flits / node / source cycle</text>',
        f'<text x="18" y="{height/2}" text-anchor="middle" transform="rotate(-90 18 {height/2})" font-size="14">{y_label}</text>',
        '</svg>',
    ])
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def svg_scatter_plot(path, title, points, x_label, y_label):
    width, height = 900, 560
    left, right, top, bottom = 90, 30, 55, 75
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    if xmin == xmax:
        xmax += 1
    if ymin == ymax:
        ymax += 1
    def px(value):
        return left + (value - xmin) / (xmax - xmin) * (width - left - right)
    def py(value):
        return top + (ymax - value) / (ymax - ymin) * (height - top - bottom)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{width/2}" y="28" text-anchor="middle" font-size="20">{title}</text>',
        f'<line x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}" stroke="black"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}" stroke="black"/>',
    ]
    for x, y, label in points:
        parts.append(f'<circle cx="{px(x):.1f}" cy="{py(y):.1f}" r="6" fill="#1f77b4"/>')
        parts.append(f'<text x="{px(x)+8:.1f}" y="{py(y)-7:.1f}" font-size="11">{label}</text>')
    parts.extend([
        f'<text x="{width/2}" y="{height-28}" text-anchor="middle" font-size="14">{x_label}</text>',
        f'<text x="18" y="{height/2}" text-anchor="middle" transform="rotate(-90 18 {height/2})" font-size="14">{y_label}</text>',
        '</svg>',
    ])
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def saturation_points(summary):
    grouped = defaultdict(list)
    for row in summary:
        grouped[(row["size"], row["traffic"], row["packet_flits"], row["design"])].append(row)
    result = []
    for key, rows in sorted(grouped.items()):
        rows.sort(key=lambda row: row["offered_flits_per_node_cycle"])
        low_latency = rows[0]["bypass_latency_cycles_mean"]
        saturated = next((
            row for row in rows
            if row["bypass_completed_flits_per_node_cycle_mean"] <
                0.9 * row["offered_flits_per_node_cycle"]
            or row["bypass_latency_cycles_mean"] >= 3 * low_latency
        ), rows[-1])
        post_points = sum(
            row["offered_flits_per_node_cycle"] >
                saturated["offered_flits_per_node_cycle"]
            for row in rows
        )
        result.append({
            "size": key[0], "traffic": key[1], "packet_flits": key[2],
            "design": key[3],
            "saturation_offered_flits_per_node_cycle": saturated[
                "offered_flits_per_node_cycle"
            ],
            "saturation_completed_flits_per_node_cycle": saturated[
                "bypass_completed_flits_per_node_cycle_mean"
            ],
            "saturation_latency_cycles": saturated[
                "bypass_latency_cycles_mean"
            ],
            "post_saturation_points": post_points,
        })
    return result


def svg_link_heatmap(path, rows, measurement):
    cell, label_width = 9, 190
    link_ids = sorted(
        {int(link) for row in rows for link in row["per_link_activity"]}
    )
    width = label_width + cell * len(link_ids) + 30
    height = 90 + 34 * len(rows)
    maximum = max(
        (value for row in rows for value in row["per_link_activity"].values()),
        default=1,
    )
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{width/2}" y="24" text-anchor="middle" font-size="18">8x8 per-link utilization heatmap</text>',
    ]
    for row_index, row in enumerate(sorted(rows, key=lambda item: item["design"])):
        y = 45 + row_index * 34
        parts.append(f'<text x="5" y="{y+10}" font-size="11">{row["design"]}</text>')
        express = set(row["express_link_ids"])
        for column, link_id in enumerate(link_ids):
            activity = row["per_link_activity"].get(str(link_id), 0)
            ratio = activity / maximum
            red = int(255 * ratio)
            blue = 255 - red
            stroke = "#000" if str(link_id) in express else "none"
            parts.append(
                f'<rect x="{label_width + column*cell}" y="{y}" width="{cell}" '
                f'height="20" fill="rgb({red},80,{blue})" stroke="{stroke}"/>'
            )
    parts.extend([
        f'<text x="{label_width}" y="{height-16}" font-size="11">link id →; black border = express; activity normalized to max; measurement={measurement} source cycles</text>',
        '</svg>',
    ])
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def make_plots(root, summary, raw, measurement):
    plots = root / "plots"
    plots.mkdir(exist_ok=True)
    maximum_size = max(row["size"] for row in summary)
    focus_traffic = (
        "uniform_random"
        if any(row["traffic"] == "uniform_random" for row in summary)
        else summary[0]["traffic"]
    )
    focus_packet = (
        4 if any(row["packet_flits"] == 4 for row in summary)
        else summary[0]["packet_flits"]
    )
    focus_design = (
        "diagonal-distance_scaled"
        if any(row["design"] == "diagonal-distance_scaled" for row in summary)
        else summary[0]["design"]
    )
    focus = [
        row for row in summary
        if row["size"] == maximum_size
        and row["traffic"] == focus_traffic
        and row["packet_flits"] == focus_packet
        and row["design"] == focus_design
    ]
    focus_label = (
        f"{maximum_size}x{maximum_size} {focus_traffic}, "
        f"{focus_packet}-flit"
    )
    svg_line_plot(
        plots / "latency_vs_offered_load.svg", focus_label + " latency",
        focus, (("mesh_latency_cycles_mean", "mesh_xy"),
                ("bypass_latency_cycles_mean", "diagonal distance-scaled")),
        "average packet latency (Ruby cycles)",
    )
    svg_line_plot(
        plots / "throughput_vs_offered_load.svg", focus_label + " throughput",
        focus, (("mesh_completed_flits_per_node_cycle_mean", "mesh_xy"),
                ("bypass_completed_flits_per_node_cycle_mean", "diagonal distance-scaled")),
        "completed flits / node / source cycle",
    )
    svg_line_plot(
        plots / "p95_latency_vs_offered_load.svg", focus_label + " p95",
        focus, (("mesh_p95_latency_cycles_mean", "mesh_xy"),
                ("bypass_p95_latency_cycles_mean", "diagonal distance-scaled")),
        "p95 packet latency (Ruby cycles)",
    )
    svg_line_plot(
        plots / "router_traversal_and_wire_distance.svg",
        focus_label + " path cost",
        focus,
        (("mesh_router_traversals_per_flit_mean", "mesh traversal/flit"),
         ("bypass_router_traversals_per_flit_mean", "bypass traversal/flit"),
         ("mesh_wire_distance_per_flit_mean", "mesh wire/flit"),
         ("bypass_wire_distance_per_flit_mean", "bypass wire/flit")),
        "distance per delivered flit",
    )
    sensitivity = [
        row for row in summary
        if row["size"] == maximum_size
        and row["traffic"] == focus_traffic
        and row["offered_flits_per_node_cycle"] == min(
            r["offered_flits_per_node_cycle"] for r in summary
        )
        and row["design"] == focus_design
    ]
    # Reuse the x-axis renderer by presenting packet sizes as its x variable.
    packet_rows = []
    for row in sensitivity:
        copy = dict(row)
        copy["offered_flits_per_node_cycle"] = row["packet_flits"]
        packet_rows.append(copy)
    svg_line_plot(
        plots / "packet_size_sensitivity.svg",
        f"{maximum_size}x{maximum_size} low-load packet sensitivity",
        packet_rows, (("latency_speedup_mean", "latency speedup"),), "speedup",
    )
    cost_groups = defaultdict(list)
    for row in summary:
        cost_groups[row["design"]].append(row)
    cost_points = []
    for design, rows in sorted(cost_groups.items()):
        cost_points.append((
            rows[0]["cost"]["extra_wire_length"],
            sum(row["latency_speedup_mean"] for row in rows) / len(rows),
            design,
        ))
    svg_scatter_plot(
        plots / "speedup_vs_wire_length.svg", "Mean latency speedup versus wire cost",
        cost_points, "extra normalized Manhattan wire length", "mean latency speedup",
    )
    representative = [
        row for row in raw
        if row["size"] == max(item["size"] for item in raw)
        and row["traffic"] == "uniform_random" and row["packet_flits"] == 4
        and row["offered_flits_per_node_cycle"] == 0.3
        and row["seed"] == 1
    ]
    if not representative:
        representative = raw[:min(5, len(raw))]
    svg_link_heatmap(
        plots / "ordinary_express_link_heatmap.svg", representative, measurement
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gem5", type=Path, default=REPO_ROOT / "build" / "Garnet_standalone" / "gem5.opt")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--sizes", type=int, nargs="+", default=[4, 8])
    parser.add_argument("--traffic", nargs="+", default=["uniform_random", "transpose", "bit_complement", "hotspot"])
    parser.add_argument("--packet-flits", type=int, nargs="+", default=[1, 4, 16, 64])
    parser.add_argument(
        "--offered-loads", type=float, nargs="+",
        default=[
            0.01, 0.025, 0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9, 1.0,
            1.25, 1.5, 1.75, 2.0, 2.5, 3.0,
        ],
    )
    parser.add_argument("--families", nargs="+", default=["diagonal", "stride"])
    parser.add_argument("--wire-models", nargs="+", default=["optimistic", "distance_scaled"])
    parser.add_argument("--seeds", type=int, nargs="+", default=[1, 7, 17])
    parser.add_argument("--hotspot-probability", type=float, default=0.5)
    parser.add_argument(
        "--inj-vnet", type=int, choices=[0, 1, 2], default=2,
        help="synthetic VNet (2 is Garnet's buffered data VNet)",
    )
    parser.add_argument(
        "--bypass-adaptive-routing",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="enable free-VC-aware source admission for express hops",
    )
    parser.add_argument(
        "--bypass-adaptive-max-packet-flits", type=int, default=32,
        help="largest packet admitted to adaptive express routing (0=unlimited)",
    )
    parser.add_argument("--warmup", type=int, default=1000)
    parser.add_argument("--drain", type=int, default=100000)
    parser.add_argument("--measurement", type=int, default=5000)
    parser.add_argument("--cooldown", type=int, default=1000000)
    parser.add_argument("--jobs", type=int, default=32)
    parser.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--retry-failures", action="store_true")
    args = parser.parse_args()
    if not args.gem5.is_file():
        parser.error(f"gem5 binary does not exist: {args.gem5}")
    allowed = {"uniform_random", "transpose", "bit_complement", "hotspot"}
    if not set(args.traffic) <= allowed:
        parser.error("unsupported traffic selection")
    if any(size < 2 for size in args.sizes) or any(packet < 1 for packet in args.packet_flits):
        parser.error("sizes and packet flits must be positive")
    if any(load <= 0 for load in args.offered_loads):
        parser.error("offered loads must be positive")
    if args.bypass_adaptive_max_packet_flits < 0:
        parser.error("adaptive maximum packet flits must be non-negative")
    root = args.output or Path(tempfile.mkdtemp(prefix="lab4-bypass-perf-"))
    root.mkdir(parents=True, exist_ok=True)
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    designs = [f"{family}-{model}" for family in args.families for model in args.wire_models]
    cases = [
        (size, traffic, packet, load, seed)
        for size in args.sizes for traffic in args.traffic
        for packet in args.packet_flits for load in args.offered_loads
        for seed in args.seeds
    ]
    manifest = {
        "git_revision": revision,
        "source_sha256": source_hashes(),
        "cases": len(cases),
        "gem5_runs": len(cases) * (1 + len(designs)),
        "arguments": vars(args),
    }
    manifest["arguments"]["gem5"] = str(args.gem5)
    manifest["arguments"]["output"] = str(root)
    (root / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(f"artifacts: {root}")
    raw = []
    work = [(case, design) for case in cases for design in ["mesh_xy"] + designs]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {
            pool.submit(run_one, args.gem5, root, case, design, args): (case, design)
            for case, design in work
        }
        for future in concurrent.futures.as_completed(futures):
            row = future.result()
            raw.append(row)
            print("PASS" if not row["errors"] else "FAIL", row["case"])
    raw.sort(key=lambda row: row["case"])
    failures = [row for row in raw if row["errors"]]
    (root / "raw.json").write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
    window_counts = defaultdict(int)
    for row in raw:
        window = tuple(sorted(row["simulation_windows"].items()))
        window_counts[window] += 1
    manifest["actual_simulation_windows"] = [
        {**dict(window), "gem5_runs": count}
        for window, count in sorted(window_counts.items())
    ]
    (root / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    if failures:
        print(f"FAIL: {len(failures)}/{len(raw)} runs failed")
        return 1
    paired = paired_rows(raw, cases, designs)
    summary = aggregate(paired)
    saturation = saturation_points(summary)
    write_csv(root / "paired.csv", paired)
    write_csv(root / "summary.csv", summary)
    (root / "paired.json").write_text(json.dumps(paired, indent=2) + "\n", encoding="utf-8")
    (root / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (root / "saturation.json").write_text(
        json.dumps(saturation, indent=2) + "\n", encoding="utf-8"
    )
    write_csv(root / "saturation.csv", saturation)
    make_plots(root, summary, raw, args.measurement)
    print(f"PASS: {len(raw)} gem5 runs, {len(paired)} paired seed cases, {len(summary)} aggregated points")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
