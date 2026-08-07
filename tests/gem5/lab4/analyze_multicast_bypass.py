#!/usr/bin/env python3

"""Audit and summarize the G10 multicast × bypass factorial artifacts."""

import argparse
import json
import re
import statistics
from collections import defaultdict
from pathlib import Path


PREFIX = "system.ruby.network."
LATENCY = re.compile(r"delivered to all .* in (\d+) ticks")


def stats(path):
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) >= 2:
            try:
                result[fields[0]] = float(fields[1])
            except ValueError:
                pass
    return result


def scalar(values, name):
    value = values.get(PREFIX + name)
    if value is None:
        raise AssertionError(f"missing {name}")
    return value


def mean(rows, field):
    return statistics.fmean(row[field] for row in rows)


def pct(value):
    return f"{100 * value:.2f}%"


def ratio(numerator, denominator):
    if denominator == 0:
        return 1.0 if numerator == 0 else float("inf")
    return numerator / denominator


def reduction(baseline, bypass):
    if baseline == 0:
        return 0.0 if bypass == 0 else float("-inf")
    return 1 - bypass / baseline


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.artifact
    raw = json.loads((root / "raw.json").read_text())
    manifest = json.loads((root / "manifest.json").read_text())
    assert len(raw) == manifest["runs"] == 624
    assert not [row for row in raw if row["errors"]]
    assert {row["packet_flits"] for row in raw} == {1, 4, 16, 64}
    assert {row["mode"] for row in raw} == {"naive_unicast", "tree_multicast"}
    assert {row["design"] for row in raw} == {"mesh_xy", "mesh_bypass"}

    enriched = []
    for row in raw:
        values = stats(Path(row["artifact"]) / "stats.txt")
        latencies = [
            int(match.group(1))
            for match in LATENCY.finditer(
                (Path(row["artifact"]) / "sim.log").read_text()
            )
        ]
        assert len(latencies) == row["rounds"] == 100, row["case"]
        item = dict(row)
        item.update({
            "latency_ticks": statistics.fmean(latencies),
            "p95_ticks": sorted(latencies)[min(99, int(len(latencies) * 0.95))],
            "internal_link_flits": scalar(values, "multicast_internal_link_flits"),
            "ordinary_link_flits": scalar(values, "ordinary_internal_link_flits"),
            "express_link_flits": scalar(values, "express_internal_link_flits"),
            "wire_flit_distance": scalar(values, "physical_wire_flit_distance"),
            "router_traversals": scalar(values, "router_traversals"),
        })
        enriched.append(item)

    index = {
        (row["mode"], row["name"], row["packet_flits"], row["design"], row["wire_model"]): row
        for row in enriched
    }
    paired = []
    for row in enriched:
        if row["design"] != "mesh_bypass":
            continue
        mesh = index[(row["mode"], row["name"], row["packet_flits"], "mesh_xy", "baseline")]
        assert row["members"] == mesh["members"]
        assert row["collective_deliveries"] == mesh["collective_deliveries"]
        assert row["collective_source_flits"] == mesh["collective_source_flits"]
        assert row["multicast_physical_packets"] == mesh["multicast_physical_packets"]
        paired.append({
            "mode": row["mode"], "wire_model": row["wire_model"],
            "case": row["name"], "packet_flits": row["packet_flits"],
            "latency_speedup": ratio(mesh["latency_ticks"], row["latency_ticks"]),
            "p95_speedup": ratio(mesh["p95_ticks"], row["p95_ticks"]),
            "link_traffic_change": reduction(mesh["internal_link_flits"], row["internal_link_flits"]),
            "wire_distance_change": reduction(mesh["wire_flit_distance"], row["wire_flit_distance"]),
            "router_traversal_change": reduction(mesh["router_traversals"], row["router_traversals"]),
            "express_link_flits": row["express_link_flits"],
        })

    groups = defaultdict(list)
    for row in paired:
        groups[(row["mode"], row["wire_model"])].append(row)
    output = args.output or root / "g10_report.md"
    lines = [
        "# G10 — multicast interaction with bypass",
        "",
        f"Artifact: `{root}`",
        f"Validated factorial: {len(enriched)} runs, {len(paired)} mesh/bypass pairs, "
        "100 rounds per case; all raw errors are empty.",
        "",
        "## Factorial result",
        "",
        "| multicast mode | link model | pairs | latency speedup | p95 speedup | link-flit change | wire-distance change | regressions |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for key, rows in sorted(groups.items()):
        lines.append(
            f"| {key[0]} | {key[1]} | {len(rows)} | "
            f"{mean(rows, 'latency_speedup'):.3f}× | {mean(rows, 'p95_speedup'):.3f}× | "
            f"{pct(mean(rows, 'link_traffic_change'))} | "
            f"{pct(mean(rows, 'wire_distance_change'))} | "
            f"{sum(row['latency_speedup'] < 1 for row in rows)} |"
        )

    lines += [
        "",
        "## Packet-size sensitivity",
        "",
        "| mode | model | packet flits | latency speedup | link-flit change |",
        "|---|---|---:|---:|---:|",
    ]
    by_packet = defaultdict(list)
    for row in paired:
        by_packet[(row["mode"], row["wire_model"], row["packet_flits"])].append(row)
    for key, rows in sorted(by_packet.items()):
        lines.append(
            f"| {key[0]} | {key[1]} | {key[2]} | {mean(rows, 'latency_speedup'):.3f}× | "
            f"{pct(mean(rows, 'link_traffic_change'))} |"
        )

    tree_bypass_express = [
        row["express_link_flits"] for row in paired if row["mode"] == "tree_multicast"
    ]
    naive_bypass_express = [
        row["express_link_flits"] for row in paired if row["mode"] == "naive_unicast"
    ]
    lines += [
        "",
        "## Interpretation",
        "",
        f"- Tree multicast bypass express-flit total is "
        f"`{sum(tree_bypass_express):.0f}` across paired runs; naive-unicast "
        f"bypass express-flit total is `{sum(naive_bypass_express):.0f}`.",
        "- Tree multicast preserves the ordinary XY convergence tree; the bypass "
        "topology does not silently change multicast branch semantics.",
        "- Naive unicast can use express links, so any interaction benefit must be "
        "separated from tree replication savings.",
        "- This is a correctness/interaction study, not a replacement for the G8 "
        "unicast performance sweep or the G9 hardware-cost conclusion.",
        "",
    ]
    output.write_text("\n".join(lines), encoding="utf-8")
    (root / "g10_paired.json").write_text(json.dumps(paired, indent=2) + "\n")
    print(f"PASS: G10 report written to {output}; {len(paired)} pairs audited")


if __name__ == "__main__":
    main()
