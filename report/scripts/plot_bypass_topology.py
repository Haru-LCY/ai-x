#!/usr/bin/env python3

"""Plot the accepted final-bypass results separately for 4x4 and 8x8."""

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


REPORT = Path(__file__).resolve().parents[1]
DATA = REPORT / "data" / "bypass_multihop_summary.csv"
FIGURES = REPORT / "figures"


def main() -> None:
    with DATA.open(newline="", encoding="utf-8") as stream:
        indexed = {row["group"]: row for row in csv.DictReader(stream)}
    rows = [indexed["size=4"], indexed["size=8"]]

    labels = ["4×4", "8×8"]
    positions = np.arange(len(labels))
    width = 0.34
    colors = ("#4c78a8", "#f28e2b")

    fig, axes = plt.subplots(1, 2, figsize=(8.8, 3.25))

    geomean = [float(row["latency_speedup_geomean"]) for row in rows]
    median = [float(row["latency_speedup_median"]) for row in rows]
    left_a = axes[0].bar(
        positions - width / 2, geomean, width, color=colors[0],
        label="Geometric mean",
    )
    left_b = axes[0].bar(
        positions + width / 2, median, width, color=colors[1], label="Median",
    )
    axes[0].axhline(1, color="#333333", linestyle="--", linewidth=1)
    axes[0].set_ylabel("Mesh / bypass latency")
    axes[0].set_title("Latency speedup")
    axes[0].set_xticks(positions, labels)
    axes[0].set_ylim(0.9, 1.72)
    axes[0].grid(axis="y", alpha=0.25)
    axes[0].legend(frameon=False, fontsize=8, loc="upper left")
    axes[0].bar_label(left_a, fmt="%.3f×", padding=3, fontsize=8)
    axes[0].bar_label(left_b, fmt="%.3f×", padding=3, fontsize=8)

    throughput = [100 * float(row["throughput_change_mean"]) for row in rows]
    traversal = [
        100 * float(row["router_traversal_per_flit_reduction_mean"])
        for row in rows
    ]
    right_a = axes[1].bar(
        positions - width / 2, throughput, width, color=colors[0],
        label="Throughput change",
    )
    right_b = axes[1].bar(
        positions + width / 2, traversal, width, color=colors[1],
        label="Router/flit reduction",
    )
    axes[1].axhline(0, color="#333333", linewidth=1)
    axes[1].set_ylabel("Mean change (%)")
    axes[1].set_title("Throughput and Router work")
    axes[1].set_xticks(positions, labels)
    axes[1].set_ylim(0, 45)
    axes[1].grid(axis="y", alpha=0.25)
    axes[1].legend(frameon=False, fontsize=8, loc="upper left")
    axes[1].bar_label(right_a, fmt="%+.2f%%", padding=3, fontsize=8)
    axes[1].bar_label(right_b, fmt="%.2f%%", padding=3, fontsize=8)

    fig.suptitle("Final distance-scaled, multi-hop stride bypass")
    fig.tight_layout()
    FIGURES.mkdir(parents=True, exist_ok=True)
    for suffix in ("pdf", "png"):
        fig.savefig(
            FIGURES / f"bypass_topology_comparison.{suffix}",
            dpi=220,
            bbox_inches="tight",
        )
    plt.close(fig)


if __name__ == "__main__":
    main()
