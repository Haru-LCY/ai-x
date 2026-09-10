#!/usr/bin/env python3

"""Visualize the spatial structure of the four synthetic traffic patterns."""

from pathlib import Path
import random

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import colors as mcolors
from matplotlib.patches import FancyArrowPatch


REPORT = Path(__file__).resolve().parents[1]
FIGURES = REPORT / "figures"
N = 4


def xy(node):
    return node % N, node // N


def pairs(kind):
    rng = random.Random(7)
    result = []
    for source in range(N * N):
        sx, sy = xy(source)
        if kind == "uniform_random":
            destination = rng.randrange(N * N)
        elif kind == "transpose":
            destination = sx * N + sy
        elif kind == "bit_complement":
            destination = (N - sy - 1) * N + (N - sx - 1)
        else:  # 50% hotspot, remaining traffic uniform random
            destination = 8 if rng.random() < 0.5 else rng.randrange(N * N)
        result.append((source, destination))
    return result


def main():
    names = ["Uniform random", "Transpose", "Bit complement", "Hotspot"]
    kinds = ["uniform_random", "transpose", "bit_complement", "hotspot"]
    colors = ["#4c78a8", "#f28e2b", "#59a14f", "#e15759"]
    fig, axes = plt.subplots(2, 2, figsize=(8.6, 7.2))
    for panel_index, (ax, name, kind, color) in enumerate(zip(axes.flat, names, kinds, colors)):
        links = pairs(kind)
        indegree = [0] * (N * N)
        for _, destination in links:
            indegree[destination] += 1
        max_degree = max(indegree) or 1
        for source, destination in links:
            if source == destination:
                continue
            x1, y1 = xy(source)
            x2, y2 = xy(destination)
            arrow = FancyArrowPatch(
                (x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=8,
                linewidth=1.25, color=color, alpha=0.62,
                connectionstyle="arc3,rad=0.06",
            )
            ax.add_patch(arrow)
        for node in range(N * N):
            x, y = xy(node)
            size = 150 + 700 * indegree[node] / max_degree
            intensity = indegree[node] / max_degree
            node_color = mcolors.to_rgba(color, alpha=0.20 + 0.55 * intensity)
            ax.scatter(x, y, s=size, color=node_color, edgecolor=color,
                       linewidth=1.5, zorder=3)
            ax.text(x, y, str(node), ha="center", va="center", fontsize=8,
                    zorder=4)
        ax.set_title(name)
        ax.set_xlim(-0.55, N - 0.45)
        ax.set_ylim(-0.55, N - 0.45)
        ax.set_xticks(range(N), [str(i) for i in range(N)])
        if panel_index < 2:
            ax.tick_params(axis="x", labelbottom=False)
        ax.set_yticks(range(N), [str(i) for i in range(N)])
        ax.set_xlabel("x coordinate" if panel_index >= 2 else "")
        ax.set_ylabel("y coordinate")
        ax.set_aspect("equal")
        ax.grid(alpha=0.18)
    fig.suptitle("Spatial structure of synthetic traffic patterns", y=0.99)
    fig.text(0.5, 0.01, "Arrow: source → destination; node size: incoming traffic",
             ha="center", fontsize=9)
    fig.subplots_adjust(left=0.07, right=0.98, bottom=0.08, top=0.92,
                        wspace=0.08, hspace=0.08)
    FIGURES.mkdir(parents=True, exist_ok=True)
    for suffix in ("pdf", "png"):
        fig.savefig(FIGURES / f"traffic_patterns_4x4.{suffix}",
                    dpi=220, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
