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
OPT_RAW = ROOT / "report" / "raw-results" / "bypass-optimization-v7"
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
    if fig.get_layout_engine() is None:
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
            "latency_speedup_geomean": geometric_mean(
                row["latency_speedup"] for row in rows
            ),
            "latency_speedup_mean": statistics.fmean(
                row["latency_speedup"] for row in rows
            ),
            "latency_speedup_median": statistics.median(
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
    with (DATA / "bypass_multihop_summary.csv").open(
        newline="", encoding="utf-8"
    ) as stream:
        multihop = next(
            row for row in csv.DictReader(stream) if row["group"] == "overall"
        )
    bypass_plot_rows = bypass_rows + [{
        "design": "stride-multihop-adaptive-scaled",
        "latency_speedup_geomean": float(
            multihop["latency_speedup_geomean"]
        ),
        "throughput_change_mean": float(multihop["throughput_change_mean"]),
    }]

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

    # Multicast scaling views: show how the shared tree changes with fanout
    # and packet size, and expose the throughput tail hidden by mean latency.
    multicast_groups = [4, 8, 16]
    multicast_packets = [1, 4, 16]
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.5))
    positions = np.arange(len(multicast_groups))
    width = 0.24
    for offset, packet, color in zip(
        (-width, 0, width), multicast_packets, ("#4c78a8", "#f28e2b", "#59a14f")
    ):
        values = []
        lows = []
        highs = []
        for group_size in multicast_groups:
            cases = [
                row for row in multicast_rows
                if row["group_size"] == group_size
                and row["packet_flits"] == packet
            ]
            samples = [100 * row["throughput_improvement"] for row in cases]
            values.append(statistics.fmean(samples))
            lows.append(values[-1] - min(samples))
            highs.append(max(samples) - values[-1])
        axes[0].bar(
            positions + offset, values, width, label=f"{packet} flits",
            color=color, yerr=[lows, highs], capsize=3,
        )
    axes[0].axhline(0, color="#333333", linewidth=1)
    axes[0].set_xticks(positions, [str(value) for value in multicast_groups])
    axes[0].set_xlabel("Destination count")
    axes[0].set_ylabel("Throughput change (%)")
    axes[0].set_title("Throughput is workload-sensitive")
    axes[0].legend(frameon=False, fontsize=8)
    axes[0].grid(axis="y", alpha=0.25)

    injection_rates = [0.1, 0.5, 1.0]
    matrix = []
    for packet in multicast_packets:
        row_values = []
        for injection in injection_rates:
            cases = [
                row for row in multicast_rows
                if row["packet_flits"] == packet
                and row["injection_rate"] == injection
            ]
            row_values.append(geometric_mean(
                row["latency_speedup"] for row in cases
            ))
        matrix.append(row_values)
    image = axes[1].imshow(
        matrix, vmin=1.0, vmax=max(5.0, max(max(row) for row in matrix)),
        cmap="YlGnBu", aspect="auto"
    )
    for packet_index, packet in enumerate(multicast_packets):
        for injection_index, injection in enumerate(injection_rates):
            matrix_value = matrix[packet_index][injection_index]
            axes[1].text(
                injection_index, packet_index, f"{matrix_value:.2f}",
                ha="center", va="center", fontsize=8,
                color="white" if matrix_value > 4 else "black",
            )
    axes[1].set_xticks(range(len(injection_rates)), [".1", ".5", "1.0"])
    axes[1].set_yticks(range(len(multicast_packets)), ["1", "4", "16"])
    axes[1].set_xlabel("Injection rate")
    axes[1].set_ylabel("Packet flits")
    axes[1].set_title("Latency speedup grows with load")
    fig.colorbar(image, ax=axes[1], shrink=0.82, label="Mesh / tree latency")
    fig.suptitle("Multicast scaling across fanout, packet size, and load")
    save(fig, "multicast_scaling")

    # Each point is one paired case; this makes the shared-traffic mechanism
    # and the occasional throughput regression visible simultaneously.
    fig, axis = plt.subplots(figsize=(6.2, 3.7))
    fanout_colors = {4: "#4c78a8", 8: "#f28e2b", 16: "#59a14f"}
    for group_size, color in fanout_colors.items():
        cases = [row for row in multicast_rows if row["group_size"] == group_size]
        axis.scatter(
            [100 * row["traffic_reduction"] for row in cases],
            [100 * row["throughput_improvement"] for row in cases],
            s=16, alpha=0.5, color=color, label=f"{group_size} destinations",
        )
    axis.axhline(0, color="#333333", linestyle="--", linewidth=1)
    axis.set_xlabel("Internal-link flit reduction (%)")
    axis.set_ylabel("Throughput change (%)")
    axis.set_title("Shared traffic does not guarantee throughput")
    axis.grid(alpha=0.2)
    axis.legend(frameon=False, fontsize=8)
    save(fig, "multicast_traffic_throughput_tradeoff")

    labels = [
        row["design"].replace("-", "\n").replace("_", " ")
        for row in bypass_plot_rows
    ]
    x = np.arange(len(labels))
    latency = [row["latency_speedup_geomean"] for row in bypass_plot_rows]
    throughput = [
        100 * row["throughput_change_mean"] for row in bypass_plot_rows
    ]
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.5))
    axes[0].bar(x, latency, color="#4c78a8")
    axes[0].axhline(1, color="#333333", linestyle="--", linewidth=1)
    axes[0].set_ylabel("Latency speedup (geometric mean)")
    axes[0].set_xticks(x, labels, fontsize=8)
    axes[0].grid(axis="y", alpha=0.25)
    colors = ["#3a8f62" if value >= 0 else "#b54a4a" for value in throughput]
    axes[1].bar(x, throughput, color=colors)
    axes[1].axhline(0, color="#333333", linewidth=1)
    axes[1].set_ylabel("Throughput change (%)")
    axes[1].set_xticks(x, labels, fontsize=8)
    axes[1].grid(axis="y", alpha=0.25)
    fig.suptitle("Source-only screen plus 1,536-pair multi-hop refinement")
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

    # Matrix view: expose the workload/packet-size/load corners hidden by
    # geometric means.  Each cell is the geometric mean over the three seeds.
    matrix_traffic = [
        ("uniform_random", "uniform\nrandom"),
        ("transpose", "transpose"),
        ("bit_complement", "bit\ncomplement"),
        ("hotspot", "hotspot"),
    ]
    matrix_sizes = [4, 8]
    matrix_packets = [1, 4, 16, 64]
    matrix_loads = [0.05, 0.1, 0.3, 0.7]
    fig, axes = plt.subplots(
        2, 4, figsize=(11.2, 5.5), squeeze=False, constrained_layout=True
    )
    image = None
    for row_index, size in enumerate(matrix_sizes):
        for col_index, (traffic, title) in enumerate(matrix_traffic):
            axis = axes[row_index, col_index]
            matrix = []
            for packet in matrix_packets:
                values = []
                for offered_load in matrix_loads:
                    cases = [
                        item for item in optimized["adaptive"]
                        if int(item["size"]) == size
                        and item["traffic"] == traffic
                        and int(item["packet_flits"]) == packet
                        and float(item["offered_flits_per_node_cycle"])
                        == offered_load
                    ]
                    values.append(geometric_mean(
                        item["latency_speedup"] for item in cases
                    ))
                matrix.append(values)
            image = axis.imshow(
                matrix, vmin=0.95, vmax=1.35, cmap="RdYlGn", aspect="auto"
            )
            for packet_index in range(len(matrix_packets)):
                for load_index in range(len(matrix_loads)):
                    value = matrix[packet_index][load_index]
                    text_color = "white" if value < 1.02 else "black"
                    axis.text(
                        load_index, packet_index, f"{value:.3f}",
                        ha="center", va="center", fontsize=7,
                        color=text_color,
                    )
            axis.set_title(title, fontsize=9)
            axis.set_xticks(range(len(matrix_loads)), [".05", ".1", ".3", ".7"])
            axis.set_yticks(range(len(matrix_packets)), ["1", "4", "16", "64"])
            axis.set_xlabel("offered load", fontsize=8)
            if col_index == 0:
                axis.set_ylabel(f"{size}×{size}; packet flits", fontsize=8)
    assert image is not None
    fig.colorbar(
        image, ax=axes.ravel().tolist(), shrink=0.82, pad=0.02,
        label="Mesh / adaptive bypass latency",
    )
    fig.suptitle("Adaptive bypass latency over all VNet-2 data-traffic configurations")
    save(fig, "bypass_matrix_heatmap")

    # Average versus tail latency: a policy can improve the mean while still
    # worsening the tail, so report both metrics on the same workload axes.
    tail_groups = [
        ("traffic", traffic_order, "Traffic pattern"),
        (
            "offered_flits_per_node_cycle", load_order, "Offered load"
        ),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.5))
    for axis, (dimension, values, title) in zip(axes, tail_groups):
        average_values = []
        p95_values = []
        for value in values:
            cases = [
                item for item in optimized["adaptive"]
                if item[dimension] == value
            ]
            average_values.append(geometric_mean(
                item["latency_speedup"] for item in cases
            ))
            p95_values.append(geometric_mean(
                item["mesh_p95_latency_cycles"] /
                item["bypass_p95_latency_cycles"] for item in cases
            ))
        positions = np.arange(len(values))
        width = 0.36
        axis.bar(
            positions - width / 2, average_values, width,
            label="mean latency", color="#4c78a8",
        )
        axis.bar(
            positions + width / 2, p95_values, width,
            label="p95 latency", color="#f28e2b",
        )
        axis.axhline(1, color="#333333", linestyle="--", linewidth=1)
        axis.set_title(title)
        axis.set_xticks(
            positions,
            [str(value).replace("_", "\n") for value in values],
            fontsize=8,
        )
        axis.grid(axis="y", alpha=0.25)
    axes[0].set_ylabel("Mesh / bypass speedup")
    axes[0].legend(frameon=False, fontsize=8)
    fig.suptitle("Adaptive bypass improves both mean and p95 latency")
    save(fig, "bypass_tail_latency")

    # Mechanism-level view: path shortening is useful, but the scatter also
    # makes clear why a topology-only claim cannot predict latency.
    fig, axis = plt.subplots(figsize=(6.2, 3.7))
    traffic_colors = {
        "uniform_random": "#4c78a8",
        "transpose": "#f28e2b",
        "bit_complement": "#59a14f",
        "hotspot": "#e15759",
    }
    for traffic, color in traffic_colors.items():
        cases = [
            item for item in optimized["adaptive"]
            if item["traffic"] == traffic
        ]
        axis.scatter(
            [100 * item["router_traversal_reduction"] for item in cases],
            [item["latency_speedup"] for item in cases],
            s=13, alpha=0.48, color=color, label=traffic.replace("_", "-"),
        )
    axis.axhline(1, color="#333333", linestyle="--", linewidth=1)
    axis.set_yscale("log")
    axis.set_xlabel("Router-traversal reduction (%)")
    axis.set_ylabel("Latency speedup (log scale)")
    axis.set_title("Path shortening is necessary but not sufficient")
    axis.grid(alpha=0.2, which="both")
    axis.legend(frameon=False, fontsize=8, ncol=2)
    save(fig, "bypass_path_tradeoff")

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
        "PASS: validated 8,628 original matrix/validation runs, 1,536 bypass "
        "optimization runs, and 4 tensor comparison runs; compact data and "
        "figures generated"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
