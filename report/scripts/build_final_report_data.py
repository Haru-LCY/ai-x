#!/usr/bin/env python3

"""Validate the final Lab4 artifacts and build compact report summaries."""

from __future__ import annotations

import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "report" / "raw-results" / "head-77fcf26d"
OPT_RAW = ROOT / "report" / "raw-results" / "bypass-optimization-v4"
DATA = ROOT / "report" / "data"
FIGURES = ROOT / "report" / "figures"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=list(rows[0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def save(fig: plt.Figure, name: str) -> None:
    fig.tight_layout()
    for suffix in ("pdf", "png"):
        fig.savefig(FIGURES / f"{name}.{suffix}", dpi=220, bbox_inches="tight")
    plt.close(fig)


def geometric_mean(values) -> float:
    values = list(values)
    assert values and all(value > 0 for value in values)
    return math.exp(statistics.fmean(math.log(value) for value in values))


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)

    multicast = load(RAW / "multicast-performance" / "summary.json")
    assert len(multicast["raw"]) == 324
    assert len(multicast["paired"]) == 162
    assert all(
        row["measured_requests"] == 100 for row in multicast["raw"]
    )

    bypass_root = RAW / "bypass-performance"
    bypass_raw = load(bypass_root / "raw.json")
    bypass_paired = load(bypass_root / "paired.json")
    bypass_summary = load(bypass_root / "summary.json")
    bypass_saturation = load(bypass_root / "saturation.json")
    assert (len(bypass_raw), len(bypass_paired), len(bypass_summary)) == (
        7680, 6144, 2048
    )
    assert len(bypass_saturation) == 128
    assert not any(row["errors"] for row in bypass_raw)

    optimized = {}
    optimization_manifests = {}
    for mode in ("static", "adaptive"):
        result_root = OPT_RAW / f"{mode}-data-vnet"
        raw = load(result_root / "raw.json")
        paired = load(result_root / "paired.json")
        manifest = load(result_root / "manifest.json")
        assert len(raw) == 768 and len(paired) == 384
        assert not any(row["errors"] for row in raw)
        assert {row["injection_vnet"] for row in raw} == {2}
        assert {
            row["bypass_adaptive_max_packet_flits"] for row in raw
        } == {32}
        bypass_rows_for_mode = [
            row for row in raw if row["design"] != "mesh_xy"
        ]
        assert {
            row["bypass_adaptive_routing"]
            for row in bypass_rows_for_mode
        } == {mode == "adaptive"}
        assert manifest["arguments"]["inj_vnet"] == 2
        assert (
            manifest["arguments"]["bypass_adaptive_max_packet_flits"] == 32
        )
        assert manifest["arguments"]["bypass_adaptive_routing"] == (
            mode == "adaptive"
        )
        optimized[mode] = paired
        optimization_manifests[mode] = manifest
    assert (
        optimization_manifests["static"]["source_sha256"]
        == optimization_manifests["adaptive"]["source_sha256"]
    )

    g10_raw = load(RAW / "multicast-bypass" / "raw.json")
    g10_paired = load(RAW / "multicast-bypass" / "g10_paired.json")
    assert len(g10_raw) == 624 and len(g10_paired) == 416
    assert not any(row["errors"] for row in g10_raw)

    gates = list(csv.DictReader(
        (RAW / "full-gate" / "full_gate_summary.csv").open(
            encoding="utf-8"
        )
    ))
    assert len(gates) == 7 and all(row["status"] == "PASS" for row in gates)

    tensor = load(RAW / "tensor-paired" / "paired_summary.json")
    assert set(tensor["designs"]) == {"mesh_xy", "mesh_bypass"}

    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in bypass_paired:
        grouped[row["design"]].append(row)
    bypass_rows = []
    for design in sorted(grouped):
        rows = grouped[design]
        bypass_rows.append({
            "design": design,
            "paired_seed_cases": len(rows),
            "latency_speedup_mean": statistics.fmean(
                row["latency_speedup"] for row in rows
            ),
            "throughput_change_mean": statistics.fmean(
                row["throughput_improvement"] for row in rows
            ),
            "router_traversal_reduction_mean": statistics.fmean(
                row["router_traversal_reduction"] for row in rows
            ),
            "wire_traffic_change_mean": statistics.fmean(
                row["wire_traffic_change"] for row in rows
            ),
            "latency_regressions": sum(
                row["latency_speedup"] < 1 for row in rows
            ),
        })
    write_csv(DATA / "bypass_overall_summary.csv", bypass_rows)

    optimization_rows = []
    optimization_group_rows = []
    for mode, rows in optimized.items():
        latency = [row["latency_speedup"] for row in rows]
        p95 = [
            row["mesh_p95_latency_cycles"]
            / row["bypass_p95_latency_cycles"]
            for row in rows
        ]
        optimization_rows.append({
            "mode": mode,
            "paired_seed_cases": len(rows),
            "latency_speedup_geomean": geometric_mean(latency),
            "latency_speedup_mean": statistics.fmean(latency),
            "latency_speedup_median": statistics.median(latency),
            "p95_latency_speedup_geomean": geometric_mean(p95),
            "throughput_change_mean": statistics.fmean(
                row["throughput_improvement"] for row in rows
            ),
            "router_traversal_reduction_mean": statistics.fmean(
                row["router_traversal_reduction"] for row in rows
            ),
            "latency_regressions": sum(value < 1 for value in latency),
            "latency_regressions_over_5pct": sum(
                value < 0.95 for value in latency
            ),
            "worst_latency_speedup": min(latency),
        })
        for dimension in ("traffic", "offered_flits_per_node_cycle"):
            for value in sorted({row[dimension] for row in rows}, key=str):
                group = [row for row in rows if row[dimension] == value]
                speedups = [row["latency_speedup"] for row in group]
                optimization_group_rows.append({
                    "mode": mode,
                    "dimension": dimension,
                    "value": value,
                    "paired_seed_cases": len(group),
                    "latency_speedup_geomean": geometric_mean(speedups),
                    "latency_regressions_over_5pct": sum(
                        speedup < 0.95 for speedup in speedups
                    ),
                    "worst_latency_speedup": min(speedups),
                })
    write_csv(DATA / "bypass_optimization_summary.csv", optimization_rows)
    write_csv(
        DATA / "bypass_optimization_by_group.csv", optimization_group_rows
    )

    multicast_rows = multicast["paired"]
    headline = [
        {
            "scope": "multicast_performance",
            "raw_runs": len(multicast["raw"]),
            "paired_cases": len(multicast_rows),
            "primary_metric": "mean_internal_link_flit_reduction",
            "value": statistics.fmean(
                row["traffic_reduction"] for row in multicast_rows
            ),
        },
        {
            "scope": "bypass_performance",
            "raw_runs": len(bypass_raw),
            "paired_cases": len(bypass_paired),
            "primary_metric": "aggregated_points",
            "value": len(bypass_summary),
        },
        {
            "scope": "multicast_bypass_interaction",
            "raw_runs": len(g10_raw),
            "paired_cases": len(g10_paired),
            "primary_metric": "all_runs_pass",
            "value": 1,
        },
        {
            "scope": "tensor_scalar_comparison",
            "raw_runs": 4,
            "paired_cases": 2,
            "primary_metric": "measurement_speedup",
            "value": tensor["designs"]["mesh_xy"]["measurement_speedup"],
        },
    ]
    write_csv(DATA / "quantitative_inventory.csv", headline)

    labels = [
        row["design"].replace("-", "\n").replace("_", " ")
        for row in bypass_rows
    ]
    x = np.arange(len(labels))
    latency = [row["latency_speedup_mean"] for row in bypass_rows]
    throughput = [100 * row["throughput_change_mean"] for row in bypass_rows]
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.5))
    axes[0].bar(x, latency, color="#4c78a8")
    axes[0].axhline(1, color="#333333", linestyle="--", linewidth=1)
    axes[0].set_ylabel("Latency speedup (Mesh / Bypass)")
    axes[0].set_xticks(x, labels, fontsize=8)
    axes[0].grid(axis="y", alpha=0.25)
    colors = ["#3a8f62" if value >= 0 else "#b54a4a" for value in throughput]
    axes[1].bar(x, throughput, color=colors)
    axes[1].axhline(0, color="#333333", linewidth=1)
    axes[1].set_ylabel("Throughput change (%)")
    axes[1].set_xticks(x, labels, fontsize=8)
    axes[1].grid(axis="y", alpha=0.25)
    fig.suptitle("Bypass results over 6,144 paired seed cases")
    save(fig, "bypass_overall")

    traffic_order = [
        "uniform_random", "transpose", "bit_complement", "hotspot"
    ]
    load_order = [0.05, 0.1, 0.3, 0.7]
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.45))
    width = 0.36
    for axis, dimension, values, title in (
        (axes[0], "traffic", traffic_order, "By traffic pattern"),
        (
            axes[1], "offered_flits_per_node_cycle", load_order,
            "By offered load",
        ),
    ):
        positions = np.arange(len(values))
        for offset, mode, color in (
            (-width / 2, "static", "#9aa0a6"),
            (width / 2, "adaptive", "#2a9d8f"),
        ):
            mode_values = []
            for value in values:
                row = next(
                    item for item in optimization_group_rows
                    if item["mode"] == mode
                    and item["dimension"] == dimension
                    and item["value"] == value
                )
                mode_values.append(row["latency_speedup_geomean"])
            axis.bar(
                positions + offset, mode_values, width, label=mode,
                color=color,
            )
        axis.axhline(1, color="#333333", linestyle="--", linewidth=1)
        labels = [str(value).replace("_", "\n") for value in values]
        axis.set_xticks(positions, labels, fontsize=8)
        axis.set_title(title)
        axis.grid(axis="y", alpha=0.25)
    axes[0].set_ylabel("Geometric-mean latency speedup")
    axes[0].legend(frameon=False, fontsize=8)
    fig.suptitle("Distance-scaled diagonal bypass: congestion-aware admission")
    save(fig, "bypass_optimization")

    comparison = tensor["designs"]["mesh_xy"]
    scalar = comparison["scalar_measurement_ticks"]
    tensor_ticks = comparison["tensor_measurement_ticks"]
    fig, ax = plt.subplots(figsize=(5.7, 3.5))
    bars = ax.bar(
        ["Serialized scalar lanes", "Tensor streaming"],
        [scalar / 1e6, tensor_ticks / 1e6],
        color=["#8c6bb1", "#2a9d8f"],
    )
    ax.bar_label(
        bars,
        labels=[f"{scalar / 1e6:.3f} M", f"{tensor_ticks / 1e6:.3f} M"],
        padding=3,
    )
    ax.set_ylabel("Trace measurement window (ticks)")
    ax.set_title(
        f"Scaled H100 all-reduce replay: "
        f"{comparison['measurement_speedup']:.3f}x"
    )
    ax.grid(axis="y", alpha=0.25)
    save(fig, "tensor_measurement_comparison")

    print(
        "PASS: validated 8,628 original matrix/gate runs, 1,536 bypass "
        "optimization runs, and 4 tensor comparison runs; compact data and "
        "figures generated"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
