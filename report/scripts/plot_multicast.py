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
    if fig.get_layout_engine() is None:
        fig.tight_layout()
    for suffix in ("pdf", "png"):
        fig.savefig(output / f"{name}.{suffix}", dpi=220, bbox_inches="tight")
    plt.close(fig)


def validate(df: pd.DataFrame) -> None:
    required = {
        "topology",
        "nodes",
        "mesh_rows",
        "source",
        "scope",
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
    numeric = df[list(required - {"topology", "scope"})]
    if numeric.isna().any().any() or not np.isfinite(numeric.to_numpy()).all():
        raise ValueError("paired results contain missing or non-finite values")
    if set(df["topology"]) != {"4x4", "8x8"}:
        raise ValueError("paired results must contain both 4x4 and 8x8")
    if set(df["scope"]) - {"common", "scaleout"}:
        raise ValueError("unknown multicast evaluation scope")
    common = df[df["scope"] == "common"]
    common_counts = common.groupby("topology").size()
    if common_counts.nunique() != 1:
        raise ValueError("cross-topology common matrices are not balanced")
    if (df[df["scope"] == "scaleout"]["topology"] != "8x8").any():
        raise ValueError("scale-out fanouts must belong to the 8x8 topology")
    if df.duplicated(
        ["topology", "group_size", "packet_flits", "injection_rate",
         "background_rate", "seed"]
    ).any():
        raise ValueError("paired results contain duplicate case keys")


def write_tables(df: pd.DataFrame, output: Path) -> None:
    metrics = ["latency_speedup", "traffic_reduction", "throughput_improvement"]
    overall_rows = []
    slices = [("common_combined", df[df["scope"] == "common"])]
    slices.extend(
        (f"common_{topology}", part)
        for topology, part in df[df["scope"] == "common"].groupby("topology")
    )
    slices.append(("8x8_all_fanouts", df[df["topology"] == "8x8"]))
    for evaluation, rows in slices:
        for metric in metrics:
            values = rows[metric]
            overall_rows.append(
                {
                    "evaluation": evaluation,
                    "metric": metric,
                    "mean": values.mean(),
                    "geometric_mean": (
                        float(np.exp(np.log(values).mean()))
                        if metric == "latency_speedup" else ""
                    ),
                    "median": values.median(),
                    "minimum": values.min(),
                    "maximum": values.max(),
                    "cases": len(values),
                }
            )
    pd.DataFrame(overall_rows).to_csv(output / "overall_summary.csv", index=False)

    def aggregate(columns: list[str]) -> pd.DataFrame:
        grouped = df.groupby(columns, as_index=False).agg(
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

    aggregate(["topology", "scope", "group_size"]).to_csv(
        output / "aggregate_by_group.csv", index=False
    )
    aggregate(["topology", "scope", "packet_flits"]).to_csv(
        output / "aggregate_by_packet.csv", index=False
    )
    df.nsmallest(10, "throughput_improvement").to_csv(
        output / "worst_throughput_cases.csv", index=False
    )


def plot_traffic_reduction(df: pd.DataFrame, output: Path) -> None:
    grouped = df.groupby(["topology", "group_size"])["traffic_reduction"].agg(
        ["mean", "min", "max"]
    ).reset_index()
    groups = sorted(df["group_size"].unique())
    x = np.arange(len(groups))
    fig, ax = plt.subplots(figsize=(7.1, 3.8))
    width = 0.36
    colors = {"4x4": "#4c78a8", "8x8": ACCENT_COLOR}
    for index, topology in enumerate(("4x4", "8x8")):
        part = grouped[grouped["topology"] == topology].set_index("group_size")
        available = [group for group in groups if group in part.index]
        positions = np.array([groups.index(group) for group in available])
        means = part.loc[available, "mean"].to_numpy() * 100
        errors = np.maximum(0.0, np.vstack((
            (part.loc[available, "mean"] - part.loc[available, "min"]).to_numpy(),
            (part.loc[available, "max"] - part.loc[available, "mean"]).to_numpy(),
        ))) * 100
        offset = (index - 0.5) * width
        ax.bar(positions + offset, means, width, color=colors[topology],
               label=topology)
        ax.errorbar(positions + offset, means, yerr=errors, fmt="none",
                    ecolor="#263238", capsize=4)
    ax.set_xticks(x, [str(value) for value in groups])
    ax.set_xlabel("Multicast destination count")
    ax.set_ylabel("Internal-link flit reduction (%)")
    ax.set_title("Tree multicast traffic reduction across Mesh sizes")
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.25)
    save_figure(fig, output, "traffic_reduction_by_group")


def plot_latency_speedup(df: pd.DataFrame, output: Path) -> None:
    grouped = df.groupby(
        ["topology", "group_size", "packet_flits"]
    )["latency_speedup"].agg(
        ["mean", "min", "max"]
    ).reset_index()
    packets = sorted(df["packet_flits"].unique())
    width = 0.22
    fig, axes = plt.subplots(1, 2, figsize=(10.0, 4.0), sharey=True)
    colors = ["#6e9bc6", "#df9a55", "#68a887"]
    for ax, topology in zip(axes, ("4x4", "8x8")):
        topo = grouped[grouped["topology"] == topology]
        groups = sorted(topo["group_size"].unique())
        x = np.arange(len(groups))
        for index, packet in enumerate(packets):
            part = topo[topo["packet_flits"] == packet].set_index("group_size")
            means = part.loc[groups, "mean"].to_numpy()
            lower = np.maximum(0.0, means - part.loc[groups, "min"].to_numpy())
            upper = np.maximum(0.0, part.loc[groups, "max"].to_numpy() - means)
            positions = x + (index - (len(packets) - 1) / 2) * width
            ax.bar(positions, means, width, color=colors[index],
                   label=f"{packet} flits")
            ax.errorbar(positions, means, yerr=np.vstack((lower, upper)),
                        fmt="none", ecolor="#263238", capsize=3, linewidth=0.9)
        ax.axhline(1.0, color="#444444", linestyle="--", linewidth=1)
        ax.set_xticks(x, [str(value) for value in groups])
        ax.set_xlabel("Multicast destination count")
        ax.set_title(f"{topology} Mesh")
        ax.grid(axis="y", alpha=0.25)
    axes[0].set_ylabel("Latency speedup (naive / tree)")
    axes[-1].legend(frameon=False, ncol=3)
    fig.suptitle("Completion-latency speedup across fanout and Mesh size")
    save_figure(fig, output, "latency_speedup_by_group")


def plot_throughput_heatmap(df: pd.DataFrame, output: Path) -> None:
    fig, axes = plt.subplots(
        1, 2, figsize=(10.0, 3.8), layout="constrained"
    )
    image = None
    for ax, topology in zip(axes, ("4x4", "8x8")):
        pivot = df[df["topology"] == topology].pivot_table(
            index="packet_flits", columns="group_size",
            values="throughput_improvement", aggfunc="mean"
        ).sort_index().sort_index(axis=1)
        values = pivot.to_numpy() * 100
        image = ax.imshow(values, cmap="RdYlGn", aspect="auto", vmin=-20, vmax=400)
        for row in range(values.shape[0]):
            for column in range(values.shape[1]):
                value = values[row, column]
                ax.text(column, row, f"{value:.1f}%", ha="center", va="center",
                        color="white" if abs(value) > 190 else "#202020", fontsize=8)
        ax.set_xticks(range(len(pivot.columns)), [str(v) for v in pivot.columns])
        ax.set_yticks(range(len(pivot.index)), [str(v) for v in pivot.index])
        ax.set_xlabel("Multicast destination count")
        ax.set_title(f"{topology} Mesh")
    axes[0].set_ylabel("Packet size (flits)")
    fig.suptitle("Mean throughput change of tree multicast")
    colorbar = fig.colorbar(image, ax=axes.ravel().tolist())
    colorbar.set_label("Throughput improvement (%)")
    save_figure(fig, output, "throughput_improvement_heatmap")


def plot_full_group_load(df: pd.DataFrame, output: Path) -> None:
    packets = sorted(df["packet_flits"].unique())
    fig, axes = plt.subplots(2, len(packets), figsize=(11.0, 6.2), sharey="row")
    for row, topology in enumerate(("4x4", "8x8")):
        topo = df[df["topology"] == topology]
        selected = topo[(topo["group_size"] == topo["nodes"]) &
                        (topo["background_rate"] == 0)]
        for ax, packet in zip(axes[row], packets):
            part = selected[selected["packet_flits"] == packet]
            for column, label, color in (
                ("naive_throughput", "Naive unicast", NAIVE_COLOR),
                ("tree_throughput", "Tree multicast", TREE_COLOR),
            ):
                stats = part.groupby("injection_rate")[column].agg(["mean", "std"])
                ax.errorbar(stats.index, stats["mean"], yerr=stats["std"],
                            marker="o", linewidth=1.8, capsize=3,
                            label=label, color=color)
            ax.set_title(f"{topology}, {packet}-flit packets")
            ax.set_xlabel("Offered request probability")
            ax.grid(alpha=0.25)
        axes[row, 0].set_ylabel("Completed multicasts / cycle")
    axes[0, -1].legend(frameon=False, fontsize=8)
    fig.suptitle("Full-group throughput without background traffic", y=1.02)
    save_figure(fig, output, "throughput_vs_offered_load")


def plot_throughput_distribution(df: pd.DataFrame, output: Path) -> None:
    fig, ax = plt.subplots(figsize=(6.5, 3.8))
    negative = 0
    for topology, color in (("4x4", "#4c78a8"), ("8x8", "#59a14f")):
        values = df[df["topology"] == topology]["throughput_improvement"].to_numpy() * 100
        negative += int((values < 0).sum())
        ax.hist(values, bins=24, alpha=0.6, color=color, edgecolor="white",
                label=topology)
    ax.axvline(0, color="#b33a3a", linestyle="--", linewidth=1.4)
    ax.text(
        0.98, 0.93, f"Negative cases: {negative}/{len(df)}",
        transform=ax.transAxes, ha="right", va="top",
        bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.85},
    )
    ax.set_xlabel("Throughput improvement (%)")
    ax.set_ylabel("Paired cases")
    ax.set_title("Throughput benefit is workload dependent")
    ax.legend(frameon=False)
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
