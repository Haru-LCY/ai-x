#!/usr/bin/env python3

"""Plot bypass latency speedup by traffic and mesh size, packet-averaged."""

import csv
import math
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


REPORT = Path(__file__).resolve().parents[1]
DIAGONAL = REPORT / "raw-results" / "refinement-v3-diagonal-adaptive-run2" / "paired.csv"
STRIDE = REPORT / "raw-results" / "refinement-v3-stride-adaptive-run2" / "paired.csv"
DATA_OUT = REPORT / "data" / "bypass_by_traffic_packet_avg.csv"
FIGURES = REPORT / "figures"

TRAFFIC = ["uniform_random", "transpose", "bit_complement", "hotspot"]
TRAFFIC_LABEL = {
    "uniform_random": "Uniform random",
    "transpose": "Transpose",
    "bit_complement": "Bit complement",
    "hotspot": "Hotspot",
}
COLORS = ["#4c78a8", "#f28e2b", "#59a14f", "#e15759"]


def load(path: Path, topology: str):
    with path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            yield {
                "topology": topology,
                "size": int(row["size"]),
                "traffic": row["traffic"],
                "packet_flits": int(row["packet_flits"]),
                "latency_speedup": float(row["latency_speedup"]),
                "throughput_improvement": float(row["throughput_improvement"]),
                "router_traversal_reduction": float(row["router_traversal_reduction"]),
            }


def main() -> None:
    rows = list(load(DIAGONAL, "Diagonal")) + list(load(STRIDE, "Stride-2"))
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["topology"], row["size"], row["traffic"], row["packet_flits"])].append(row)

    fields = [
        "topology", "size", "traffic", "packet_avg_cases",
        "latency_speedup_mean", "throughput_improvement_mean",
        "router_traversal_reduction_mean",
    ]
    summary = []
    packet_groups = defaultdict(list)
    for (topology, size, traffic, packet_flits), values in sorted(grouped.items()):
        packet_groups[(topology, size, traffic)].append({
            "latency": math.exp(sum(math.log(v["latency_speedup"]) for v in values) / len(values)),
            "throughput": sum(v["throughput_improvement"] for v in values) / len(values),
            "traversal": sum(v["router_traversal_reduction"] for v in values) / len(values),
        })

    for (topology, size, traffic), values in sorted(packet_groups.items()):
        summary.append({
            "topology": topology,
            "size": size,
            "traffic": traffic,
            "packet_avg_cases": len(values),
            "latency_speedup_mean": sum(v["latency"] for v in values) / len(values),
            "throughput_improvement_mean": sum(v["throughput"] for v in values) / len(values),
            "router_traversal_reduction_mean": sum(v["traversal"] for v in values) / len(values),
        })

    DATA_OUT.parent.mkdir(parents=True, exist_ok=True)
    with DATA_OUT.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summary)

    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.8), sharey=True)
    x = np.arange(2)
    width = 0.18
    max_value = max(row["latency_speedup_mean"] for row in summary)
    for ax, topology in zip(axes, ("Diagonal", "Stride-2")):
        for index, (traffic, color) in enumerate(zip(TRAFFIC, COLORS)):
            values = [
                next(row["latency_speedup_mean"] for row in summary
                     if row["topology"] == topology and row["size"] == size
                     and row["traffic"] == traffic)
                for size in (4, 8)
            ]
            bars = ax.bar(x + (index - 1.5) * width, values, width,
                          color=color, label=TRAFFIC_LABEL[traffic])
            ax.bar_label(bars, labels=[f"{value:.2f}×" for value in values],
                         padding=2, fontsize=7, rotation=90)
        ax.axhline(1.0, color="#444444", linestyle="--", linewidth=0.9)
        ax.set_title(f"{topology} adaptive bypass")
        ax.set_xticks(x, ["4×4", "8×8"])
        ax.set_xlabel("Mesh size")
        ax.grid(axis="y", alpha=0.25)
        ax.set_ylim(0.9, max_value * 1.16)
    axes[0].set_ylabel("Mesh XY / bypass latency speedup")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4,
               frameon=False, fontsize=8, bbox_to_anchor=(0.5, 0.995))
    fig.suptitle("Packet-averaged latency speedup by traffic pattern", y=0.925)
    fig.tight_layout(rect=(0, 0, 1, 0.985))
    FIGURES.mkdir(parents=True, exist_ok=True)
    for suffix in ("pdf", "png"):
        fig.savefig(FIGURES / f"bypass_by_traffic_packet_avg.{suffix}",
                    dpi=220, bbox_inches="tight")
    plt.close(fig)

    # A separate small-multiple view makes each traffic distribution easier
    # to compare without requiring the reader to decode two topology panels.
    fig, axes = plt.subplots(2, 2, figsize=(8.8, 6.4), sharey=True)
    topology_colors = {"Diagonal": "#4c78a8", "Stride-2": "#f28e2b"}
    labels = ["Diagonal\n4×4", "Stride-2\n4×4", "Diagonal\n8×8", "Stride-2\n8×8"]
    for ax, traffic in zip(axes.flat, TRAFFIC):
        values = []
        colors = []
        for size in (4, 8):
            for topology in ("Diagonal", "Stride-2"):
                row = next(row for row in summary
                           if row["topology"] == topology
                           and row["size"] == size
                           and row["traffic"] == traffic)
                values.append(row["latency_speedup_mean"])
                colors.append(topology_colors[topology])
        bars = ax.bar(np.arange(4), values, color=colors, width=0.68)
        ax.bar_label(bars, labels=[f"{v:.2f}×" for v in values],
                     padding=2, fontsize=7, rotation=90)
        ax.axhline(1.0, color="#444444", linestyle="--", linewidth=0.9)
        ax.set_title(TRAFFIC_LABEL[traffic])
        ax.set_xticks(np.arange(4), labels, fontsize=8)
        ax.grid(axis="y", alpha=0.25)
        ax.set_ylim(0.9, max_value * 1.16)
    axes[0, 0].set_ylabel("Latency speedup")
    axes[1, 0].set_ylabel("Latency speedup")
    handles = [plt.Rectangle((0, 0), 1, 1, color=topology_colors[name])
               for name in ("Diagonal", "Stride-2")]
    fig.legend(handles, ["Diagonal", "Stride-2"], loc="upper center",
               ncol=2, frameon=False, bbox_to_anchor=(0.5, 0.995))
    fig.suptitle("Latency speedup distribution by traffic pattern", y=0.965)
    fig.tight_layout(rect=(0, 0, 1, 0.985))
    for suffix in ("pdf", "png"):
        fig.savefig(FIGURES / f"bypass_traffic_distribution.{suffix}",
                    dpi=220, bbox_inches="tight")
    plt.close(fig)

if __name__ == "__main__":
    main()
