#!/usr/bin/env python3

"""Build report tables and figures from paired multicast measurements."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "report" / "data" / "multicast_paired.csv"
DEFAULT_OUTPUT = ROOT / "report" / "figures"
DEFAULT_TABLES = ROOT / "report" / "data"

NAIVE_COLOR = "#3569a8"
TREE_COLOR = "#df7b28"
ACCENT_COLOR = "#398564"


def save_figure(fig: plt.Figure, output: Path, name: str) -> None:
    fig.tight_layout()
    for suffix in ("pdf", "png"):
        fig.savefig(output / f"{name}.{suffix}", dpi=220, bbox_inches="tight")
    plt.close(fig)


def validate(df: pd.DataFrame) -> None:
    required = {
        "group_size",
        "packet_flits",
        "injection_rate",
        "background_rate",
        "seed",
        "naive_latency_ticks",
        "tree_latency_ticks",
        "latency_speedup",
        "naive_link_flits",
        "tree_link_flits",
        "traffic_reduction",
        "naive_throughput",
        "tree_throughput",
        "throughput_improvement",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"missing input columns: {sorted(missing)}")
    numeric = df[list(required)]
    if numeric.isna().any().any() or not np.isfinite(numeric.to_numpy()).all():
        raise ValueError("paired results contain missing or non-finite values")
    if df.duplicated(
        ["group_size", "packet_flits", "injection_rate",
         "background_rate", "seed"]
    ).any():
        raise ValueError("paired results contain duplicate case keys")


def write_tables(df: pd.DataFrame, output: Path) -> None:
    metrics = ["latency_speedup", "traffic_reduction", "throughput_improvement"]
    overall_rows = []
    for metric in metrics:
        values = df[metric]
        overall_rows.append(
            {
                "metric": metric,
                "mean": values.mean(),
                "geometric_mean": (
                    float(np.exp(np.log(values).mean()))
                    if metric == "latency_speedup" else ""
                ),
                "median": values.median(),
                "minimum": values.min(),
                "maximum": values.max(),
            }
        )
    pd.DataFrame(overall_rows).to_csv(output / "overall_summary.csv", index=False)

    def aggregate(column: str) -> pd.DataFrame:
        grouped = df.groupby(column, as_index=False).agg(
            latency_speedup_mean=("latency_speedup", "mean"),
            latency_speedup_min=("latency_speedup", "min"),
            latency_speedup_max=("latency_speedup", "max"),
            traffic_reduction_mean=("traffic_reduction", "mean"),
            traffic_reduction_min=("traffic_reduction", "min"),
            traffic_reduction_max=("traffic_reduction", "max"),
            throughput_improvement_mean=("throughput_improvement", "mean"),
            throughput_improvement_min=("throughput_improvement", "min"),
            throughput_improvement_max=("throughput_improvement", "max"),
            cases=("throughput_improvement", "size"),
            negative_throughput_cases=(
                "throughput_improvement", lambda values: int((values < 0).sum())
            ),
        )
        return grouped

    aggregate("group_size").to_csv(output / "aggregate_by_group.csv", index=False)
    aggregate("packet_flits").to_csv(output / "aggregate_by_packet.csv", index=False)
    df.nsmallest(10, "throughput_improvement").to_csv(
        output / "worst_throughput_cases.csv", index=False
    )


def plot_traffic_reduction(df: pd.DataFrame, output: Path) -> None:
    grouped = df.groupby("group_size")["traffic_reduction"].agg(
        ["mean", "min", "max"]
    )
    x = np.arange(len(grouped))
    means = grouped["mean"].to_numpy() * 100
    errors = np.maximum(0.0, np.vstack(
        ((grouped["mean"] - grouped["min"]).to_numpy(),
         (grouped["max"] - grouped["mean"]).to_numpy())
    )) * 100
    fig, ax = plt.subplots(figsize=(6.3, 3.8))
    bars = ax.bar(x, means, color=ACCENT_COLOR, width=0.62)
    ax.errorbar(x, means, yerr=errors, fmt="none", ecolor="#263238", capsize=5)
    ax.bar_label(bars, labels=[f"{value:.1f}%" for value in means], padding=4)
    ax.set_xticks(x, [str(value) for value in grouped.index])
    ax.set_xlabel("Multicast destination count")
    ax.set_ylabel("Internal-link flit reduction (%)")
    ax.set_title("Tree multicast reduces physical link traffic")
    ax.set_ylim(0, max(60, errors[1].max() + means.max() + 6))
    ax.grid(axis="y", alpha=0.25)
    save_figure(fig, output, "traffic_reduction_by_group")


def plot_latency_speedup(df: pd.DataFrame, output: Path) -> None:
    grouped = df.groupby(["group_size", "packet_flits"])["latency_speedup"].agg(
        ["mean", "min", "max"]
    ).reset_index()
    groups = sorted(df["group_size"].unique())
    packets = sorted(df["packet_flits"].unique())
    x = np.arange(len(groups))
    width = 0.22
    fig, ax = plt.subplots(figsize=(7.1, 4.1))
    colors = ["#6e9bc6", "#df9a55", "#68a887"]
    for index, packet in enumerate(packets):
        part = grouped[grouped["packet_flits"] == packet].set_index("group_size")
        means = part.loc[groups, "mean"].to_numpy()
        lower = np.maximum(0.0, means - part.loc[groups, "min"].to_numpy())
        upper = np.maximum(0.0, part.loc[groups, "max"].to_numpy() - means)
        positions = x + (index - (len(packets) - 1) / 2) * width
        ax.bar(positions, means, width, color=colors[index], label=f"{packet} flits")
        ax.errorbar(
            positions, means, yerr=np.vstack((lower, upper)), fmt="none",
            ecolor="#263238", capsize=3, linewidth=0.9,
        )
    ax.axhline(1.0, color="#444444", linestyle="--", linewidth=1)
    ax.set_xticks(x, [str(value) for value in groups])
    ax.set_xlabel("Multicast destination count")
    ax.set_ylabel("Latency speedup (naive / tree)")
    ax.set_title("Completion-latency speedup grows with fanout")
    ax.legend(frameon=False, ncol=3)
    ax.grid(axis="y", alpha=0.25)
    save_figure(fig, output, "latency_speedup_by_group")


def plot_throughput_heatmap(df: pd.DataFrame, output: Path) -> None:
    pivot = df.pivot_table(
        index="packet_flits", columns="group_size",
        values="throughput_improvement", aggfunc="mean"
    ).sort_index().sort_index(axis=1)
    values = pivot.to_numpy() * 100
    fig, ax = plt.subplots(figsize=(6.1, 3.8))
    image = ax.imshow(values, cmap="RdYlGn", aspect="auto", vmin=-20, vmax=400)
    for row in range(values.shape[0]):
        for column in range(values.shape[1]):
            value = values[row, column]
            ax.text(
                column, row, f"{value:.1f}%", ha="center", va="center",
                color="white" if abs(value) > 190 else "#202020", fontsize=9,
            )
    ax.set_xticks(range(len(pivot.columns)), [str(value) for value in pivot.columns])
    ax.set_yticks(range(len(pivot.index)), [str(value) for value in pivot.index])
    ax.set_xlabel("Multicast destination count")
    ax.set_ylabel("Packet size (flits)")
    ax.set_title("Mean throughput change of tree multicast")
    colorbar = fig.colorbar(image, ax=ax)
    colorbar.set_label("Throughput improvement (%)")
    save_figure(fig, output, "throughput_improvement_heatmap")


def plot_full_group_load(df: pd.DataFrame, output: Path) -> None:
    selected = df[(df["group_size"] == df["group_size"].max()) &
                  (df["background_rate"] == 0)]
    packets = sorted(selected["packet_flits"].unique())
    fig, axes = plt.subplots(1, len(packets), figsize=(11.0, 3.5), sharey=True)
    for ax, packet in zip(axes, packets):
        part = selected[selected["packet_flits"] == packet]
        for column, label, color in (
            ("naive_throughput", "Naive unicast", NAIVE_COLOR),
            ("tree_throughput", "Tree multicast", TREE_COLOR),
        ):
            stats = part.groupby("injection_rate")[column].agg(["mean", "std"])
            ax.errorbar(
                stats.index, stats["mean"], yerr=stats["std"], marker="o",
                linewidth=1.8, capsize=3, label=label, color=color,
            )
        ax.set_title(f"{packet}-flit packets")
        ax.set_xlabel("Offered request probability")
        ax.grid(alpha=0.25)
    axes[0].set_ylabel("Completed multicasts / cycle")
    axes[-1].legend(frameon=False, fontsize=8)
    fig.suptitle("Full-group throughput without background traffic", y=1.03)
    save_figure(fig, output, "throughput_vs_offered_load")


def plot_throughput_distribution(df: pd.DataFrame, output: Path) -> None:
    values = df["throughput_improvement"].to_numpy() * 100
    negative = int((values < 0).sum())
    fig, ax = plt.subplots(figsize=(6.5, 3.8))
    ax.hist(values, bins=24, color="#6f85a8", edgecolor="white")
    ax.axvline(0, color="#b33a3a", linestyle="--", linewidth=1.4)
    ax.text(
        0.98, 0.93, f"Negative cases: {negative}/{len(values)}",
        transform=ax.transAxes, ha="right", va="top",
        bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.85},
    )
    ax.set_xlabel("Throughput improvement (%)")
    ax.set_ylabel("Paired cases")
    ax.set_title("Throughput benefit is workload dependent")
    ax.grid(axis="y", alpha=0.25)
    save_figure(fig, output, "throughput_improvement_distribution")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--tables", type=Path, default=DEFAULT_TABLES)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    args.tables.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.input)
    validate(df)
    write_tables(df, args.tables)
    plot_traffic_reduction(df, args.output)
    plot_latency_speedup(df, args.output)
    plot_throughput_heatmap(df, args.output)
    plot_full_group_load(df, args.output)
    plot_throughput_distribution(df, args.output)
    print(f"Generated tables in {args.tables} and figures in {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
