#!/usr/bin/env python3

"""Generate implementation diagrams used by the Lab 4 report.

The diagrams are deliberately rendered from the topology and collective
contracts in the repository instead of being hand-drawn screenshots.  The
script emits both PDF (for LaTeX) and PNG (for quick inspection) versions.
Graphviz's fixed-position ``neato`` layout keeps the Mesh coordinates visible.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FIGURES = ROOT / "report" / "figures"


def render(name: str, source: str) -> None:
    """Render one DOT source to a vector PDF and a high-resolution PNG."""

    FIGURES.mkdir(parents=True, exist_ok=True)
    # Graphviz interprets fixed ``pos`` values as points.  The diagram builders
    # use compact, human-readable grid coordinates; expand them here so the
    # Mesh nodes and explanatory labels are not collapsed into one glyph.
    def expand(match: re.Match[str]) -> str:
        x, y = (float(value) for value in match.groups())
        return f'pos="{x * 100:.2f},{y * 100:.2f}!"'

    source = re.sub(
        r'pos="(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)!"', expand, source
    )
    for suffix, args in (
        ("pdf", ["-Tpdf"]),
        ("png", ["-Tpng", "-Gdpi=220"]),
    ):
        output = FIGURES / f"{name}.{suffix}"
        subprocess.run(
            ["neato", "-n2", *args, "-o", str(output)],
            input=source.encode("utf-8"),
            check=True,
        )


def mesh_nodes(prefix: str, x_offset: float, *, rows: int = 4,
               columns: int = 4, source: int = 5,
               destinations: tuple[int, ...] = (3, 10, 15)) -> str:
    lines = []
    for y in range(rows):
        for x in range(columns):
            node = f"{prefix}{y * columns + x}"
            fill = "#f7f8fa"
            color = "#68727d"
            node_id = y * columns + x
            if node_id == source:
                fill, color = "#f6c177", "#b36b00"
            if node_id in destinations:
                fill, color = "#b9e3c6", "#3a8f62"
            lines.append(
                f'{node} [label="{node_id}", '
                f'pos="{x_offset + x},{3 - y}!", fillcolor="{fill}", '
                f'color="{color}"];'
            )
    return "\n".join(lines)


def mesh_edges(prefix: str, x_offset: float, *, rows: int = 4,
               columns: int = 4, directed: bool = False) -> str:
    connector = "->"
    direction = "" if directed else "dir=none, "
    lines = []
    for y in range(rows):
        for x in range(columns):
            src = f"{prefix}{y * columns + x}"
            if x + 1 < columns:
                lines.append(
                    f"{src} {connector} {prefix}{y * columns + x + 1} "
                    f'[{direction}color="#d5d9de", penwidth=1.0, '
                    'arrowsize=0.45];'
                )
            if y + 1 < rows:
                lines.append(
                    f"{src} {connector} {prefix}{(y + 1) * columns + x} "
                    f'[{direction}color="#d5d9de", penwidth=1.0, '
                    'arrowsize=0.45];'
                )
    return "\n".join(lines)


def curved_edge_geometry(src: int, dst: int, x_offset: float, bend: float):
    """Return endpoints and control points for a bowed stride-2 edge."""
    columns = 4
    sx = x_offset + src % columns
    sy = 3 - src // columns
    dx = x_offset + dst % columns
    dy = 3 - dst // columns
    sign = 1.0 if (src // columns + src % columns) % 2 == 0 else -1.0
    if sy == dy:  # horizontal link: bow above/below the skipped router
        c1 = (sx + (dx - sx) / 3.0, sy + sign * bend)
        c2 = (sx + 2.0 * (dx - sx) / 3.0, sy + sign * bend)
    else:  # vertical link: bow left/right around the skipped router
        c1 = (sx + sign * bend, sy + (dy - sy) / 3.0)
        c2 = (dx + sign * bend, sy + 2.0 * (dy - sy) / 3.0)
    return (sx, sy), c1, c2, (dx, dy)


def curved_edge_pos(src: int, dst: int, x_offset: float, bend: float) -> str:
    """Return a gently bowed cubic spline for a stride-2 candidate edge.

    ``neato -n2`` accepts explicit edge control points in points.  The node
    coordinates in this file are expressed in compact grid units and expanded
    by :func:`render`, so this helper performs that same 100x conversion for
    the edge geometry while keeping the topology definition readable.
    """
    p0, c1, c2, p3 = curved_edge_geometry(src, dst, x_offset, bend)

    def point(x: float, y: float) -> str:
        return f"{x * 100:.2f},{y * 100:.2f}"

    return (
        f'pos="s,{point(*p0)} e,{point(*p3)} '
        f"{point(*p0)} {point(*c1)} {point(*c2)} {point(*p3)}\""
    )


def straight_edge_pos(src: int, dst: int, x_offset: float) -> str:
    """Return an explicit straight cubic spline for an overlaid route."""
    columns = 4
    start = (x_offset + src % columns, 3 - src // columns)
    end = (x_offset + dst % columns, 3 - dst // columns)

    def point(value) -> str:
        return f"{value[0] * 100:.2f},{value[1] * 100:.2f}"

    c1 = (start[0] + (end[0] - start[0]) / 3.0,
          start[1] + (end[1] - start[1]) / 3.0)
    c2 = (start[0] + 2.0 * (end[0] - start[0]) / 3.0,
          start[1] + 2.0 * (end[1] - start[1]) / 3.0)
    return (
        f'pos="s,{point(start)} e,{point(end)} '
        f"{point(start)} {point(c1)} {point(c2)} {point(end)}\""
    )


def multicast_figure() -> str:
    # The 4x4 source-5 example uses the same X-first XY tree as the report's
    # correctness/performance cases.  Destinations are {3, 5, 10, 15}.
    baseline_paths = [
        ("L5", "L6", "#4c78a8"), ("L6", "L7", "#4c78a8"),
        ("L7", "L3", "#4c78a8"),
        ("L5", "L6", "#f28e2b"), ("L6", "L10", "#f28e2b"),
        ("L5", "L6", "#59a14f"), ("L6", "L7", "#59a14f"),
        ("L7", "L11", "#59a14f"), ("L11", "L15", "#59a14f"),
    ]
    tree_edges = [
        ("R5", "R6"), ("R6", "R7"), ("R7", "R3"),
        ("R6", "R10"), ("R7", "R11"), ("R11", "R15"),
    ]
    lines = [
        "digraph multicast {",
        'graph [outputorder=edgesfirst, overlap=false, pad=0.22, '
        'bgcolor="white", size="12,6!"];',
        'node [shape=circle, fixedsize=true, width=0.40, height=0.40, '
        'fontname="Helvetica", fontsize=9, style=filled, '
        'fillcolor="#f7f8fa", color="#68727d", penwidth=1.1];',
        'edge [fontname="Helvetica", fontsize=8, arrowsize=0.55];',
        mesh_nodes("L", 0.0),
        mesh_nodes("R", 6.4),
        mesh_edges("L", 0.0),
        mesh_edges("R", 6.4),
        'l_title [shape=plaintext, fixedsize=false, label="Naive replicated unicast", '
        'pos="1.5,4.05!"];',
        'r_title [shape=plaintext, fixedsize=false, label="Tree multicast", '
        'pos="7.9,4.05!"];',
        'l_note [shape=box, fixedsize=false, style="rounded,filled", fillcolor="#eef2f6", '
        'color="#a5adb7", margin="0.08,0.04", '
        'label="3 physical packets\\n(one for each remote destination)", '
        'pos="1.5,-0.82!"];',
        'r_note [shape=box, fixedsize=false, style="rounded,filled", fillcolor="#fff4e5", '
        'color="#d99a45", margin="0.08,0.04", '
        'label="1 bitmap packet\\nmask = {3, 5, 10, 15}", '
        'pos="7.9,-0.82!"];',
        'legend [shape=plaintext, fixedsize=false, label="orange = source 5   green = destinations   '
        'blue/orange/green = independent XY paths", pos="4.7,-1.43!"];',
    ]
    for src, dst, color in baseline_paths:
        lines.append(
            f'{src} -> {dst} [color="{color}", penwidth=2.7, arrowsize=0.6];'
        )
    for src, dst in tree_edges:
        lines.append(
            f'{src} -> {dst} [color="#1769aa", penwidth=3.2, arrowsize=0.65];'
        )
    # Branch routers are visually distinct from ordinary forwarding routers.
    lines.extend([
        'R6 [fillcolor="#9ecae1", color="#1769aa", penwidth=2.0];',
        'R7 [fillcolor="#9ecae1", color="#1769aa", penwidth=2.0];',
        'R11 [fillcolor="#9ecae1", color="#1769aa", penwidth=2.0];',
        "}",
    ])
    return "\n".join(lines)


def bypass_figure() -> str:
    diagonal = [(0, 5), (2, 5), (2, 7), (5, 8), (5, 10),
                (7, 10), (8, 13), (10, 13), (10, 15)]
    stride = [(0, 2), (0, 8), (1, 3), (1, 9), (2, 10), (3, 11),
              (4, 6), (4, 12), (5, 7), (5, 13), (6, 14), (7, 15),
              (8, 10), (9, 11), (12, 14), (13, 15)]
    lines = [
        "digraph bypass {",
        'graph [outputorder=edgesfirst, overlap=false, pad=0.22, '
        'bgcolor="white", size="12,6!"];',
        'node [shape=circle, fixedsize=true, width=0.40, height=0.40, '
        'fontname="Helvetica", fontsize=9, style=filled, '
        'fillcolor="#f7f8fa", color="#68727d", penwidth=1.1];',
        'edge [fontname="Helvetica", fontsize=8, arrowsize=0.55];',
        mesh_nodes("D", 0.0, source=0, destinations=(15,)),
        mesh_nodes("S", 7.0, source=0, destinations=(15,)),
        mesh_edges("D", 0.0),
        mesh_edges("S", 7.0),
        'd_title [shape=plaintext, fixedsize=false, label="Diagonal checkerboard (9 links)", '
        'pos="1.9,4.04!"];',
        's_title [shape=plaintext, fixedsize=false, label="Stride-2 symmetric (16 links)", '
        'pos="8.9,4.04!"];',
        'd_note [shape=box, fixedsize=false, style="rounded,filled", fillcolor="#fff4e5", '
        'color="#d99a45", margin="0.08,0.04", '
        'label="0 → 5 (express) → 6 → 7 → 11 → 15\\n'
        'source express hop + deterministic XY suffix", pos="1.9,-0.82!"];',
        's_note [shape=box, fixedsize=false, style="rounded,filled", fillcolor="#fff4e5", '
        'color="#d99a45", margin="0.08,0.04", '
        'label="0 → 2 (express) → 3 → 7 → 11 → 15\\n'
        'source express hop + deterministic XY suffix", pos="8.9,-0.82!"];',
        'legend [shape=plaintext, fixedsize=false, label="gray = ordinary Mesh edges   orange dashed = installed bidirectional express candidates   '
        'orange solid = oracle-selected express hop   blue solid = XY suffix   node orange/green = source/destination", '
        'pos="5.4,-1.43!"];',
    ]
    for src, dst in diagonal:
        edge_pos = ""
        if (src, dst) == (0, 5):
            edge_pos = f", {straight_edge_pos(src, dst, 0.0)}"
        lines.append(
            f'D{src} -> D{dst} [dir=none, color="#d95f02", '
            f'style=dashed, penwidth=2.0{edge_pos}];'
        )
    # Give the dense right-hand candidate set a white halo so crossings remain
    # legible against the ordinary Mesh and against neighboring candidates.
    stride_positions = []
    for src, dst in stride:
        edge_pos = curved_edge_pos(src, dst, 7.0, bend=0.30)
        stride_positions.append((src, dst, edge_pos))
        lines.append(
            f'S{src} -> S{dst} [dir=none, color="white", penwidth=4.6, '
            f'{edge_pos}];'
        )
    for src, dst, edge_pos in stride_positions:
        lines.append(
            f'S{src} -> S{dst} [dir=none, color="#d95f02", '
            f'style=dashed, penwidth=1.8, '
            f'{edge_pos}];'
        )
    # The selected source route is highlighted above the candidate links.
    for prefix, route, express in (
        ("D", [0, 5, 6, 7, 11, 15], (0, 5)),
        ("S", [0, 2, 3, 7, 11, 15], (0, 2)),
    ):
        for src, dst in zip(route, route[1:]):
            color = "#d95f02" if (src, dst) == express else "#1769aa"
            edge_pos = ""
            if prefix == "D" and (src, dst) == express:
                edge_pos = f", {straight_edge_pos(src, dst, 0.0)}"
            elif prefix == "S" and (src, dst) == express:
                edge_pos = f", {curved_edge_pos(src, dst, 7.0, bend=0.30)}"
            lines.append(
                f'{prefix}{src} -> {prefix}{dst} [color="{color}", '
                f'penwidth={3.5 if color == "#d95f02" else 2.8}, '
                f'arrowsize=0.65{edge_pos}];'
            )
    for prefix in ("D", "S"):
        lines.extend([
            f'{prefix}0 [fillcolor="#f6c177", color="#b36b00", penwidth=2.0];',
            f'{prefix}15 [fillcolor="#b9e3c6", color="#3a8f62", penwidth=2.0];',
        ])
    lines.append("}")
    return "\n".join(lines)


def tensor_figure() -> str:
    lines = [
        "digraph tensor {",
        'graph [outputorder=edgesfirst, overlap=false, pad=0.22, '
        'bgcolor="white", size="14,7!"];',
        'node [shape=box, style="rounded,filled", fontname="Helvetica", '
        'fontsize=10, color="#68727d", penwidth=1.1, margin="0.10,0.06"];',
        'edge [fontname="Helvetica", fontsize=8, color="#536172", '
        'penwidth=1.5, arrowsize=0.6];',
        # Left: actual Router-side reduce/broadcast datapath.
        'a [label="8 rank contributions\\n(each lane carries rank + lane)", '
        'fillcolor="#eef2f6", pos="2.0,3.45!"];',
        'b [label="XY convergence tree\\nRouter lane table keyed by\\n(collective_id, lane_id)", '
        'fillcolor="#d9ecf8", pos="2.0,2.15!"];',
        'c [label="Root Router 0\\nSUM after fan-in", fillcolor="#f6c177", '
        'color="#b36b00", penwidth=1.7, pos="2.0,0.82!"];',
        'd [label="Lane-wise tree broadcast\\none reduced flit per lane", fillcolor="#d9ecf8", '
        'pos="2.0,-0.47!"];',
        'e [label="8 ranks receive\\nall tensor lanes", fillcolor="#b9e3c6", '
        'color="#3a8f62", pos="2.0,-1.75!"];',
        'a -> b; b -> c; c -> d; d -> e;',
        'left_title [shape=plaintext, fillcolor="white", color="white", '
        'fontcolor="#263238", fixedsize=false, '
        'label="Tensor all-reduce datapath", '
        'pos="2.0,4.15!"];',
        # Right: scalar/tensor replay representations and equal work counts.
        'scalar_title [shape=plaintext, fillcolor="white", color="white", '
        'fontcolor="#263238", fixedsize=false, '
        'label="Scalar lowering", pos="7.3,4.15!"];',
        'tensor_title [shape=plaintext, fillcolor="white", color="white", '
        'fontcolor="#263238", fixedsize=false, '
        'label="Tensor lowering", pos="11.8,4.15!"];',
        's0 [label="lane 0", fillcolor="#e6d9f2", pos="6.0,3.35!"];',
        's1 [label="lane 1", fillcolor="#e6d9f2", pos="7.1,3.35!"];',
        's2 [label="…", fillcolor="#e6d9f2", pos="8.2,3.35!"];',
        's3 [label="lane 6,719", fillcolor="#e6d9f2", pos="9.3,3.35!"];',
        'sbox [label="6,720 logical requests\\nserialized scalar lanes", '
        'fillcolor="#f4eef8", color="#8c6bb1", pos="7.7,2.05!"];',
        't0 [label="HEAD", fillcolor="#bde5d3", pos="10.8,3.35!"];',
        't1 [label="BODY × 62", fillcolor="#bde5d3", pos="12.0,3.35!"];',
        't2 [label="TAIL", fillcolor="#bde5d3", pos="13.2,3.35!"];',
        'tbox [label="15 logical requests × 64 flits\\nlane_id remains attached to each flit", '
        'fillcolor="#e8f6ee", color="#3a8f62", pos="12.0,2.05!"];',
        'work [label="same network work\\n53,760 contribution flits\\n147,840 Router flits", '
        'fillcolor="#fff4e5", color="#d99a45", pos="9.8,0.50!"];',
        'window [label="measurement window\\nscalar 80.638 M ticks   →   tensor 17.055 M ticks\\n4.728× shorter", '
        'fillcolor="#fff4e5", color="#d99a45", penwidth=1.7, pos="9.8,-0.95!"];',
        's0 -> s1 [style=invis]; s1 -> s2 [style=invis]; s2 -> s3 [style=invis];',
        's1 -> sbox [color="#8c6bb1"]; t1 -> tbox [color="#3a8f62"];',
        'sbox -> work [color="#8c6bb1"]; tbox -> work [color="#3a8f62"];',
        'work -> window [color="#d95f02"];',
        'note [shape=plaintext, fillcolor="white", color="white", '
        'fontcolor="#263238", fixedsize=false, '
        'label="one flit = one 64-bit reduction lane", pos="7.95,-1.75!"];',
        "}",
    ]
    return "\n".join(lines)


def main() -> None:
    render("multicast_tree_flow", multicast_figure())
    render("bypass_topology_oracle", bypass_figure())
    render("tensor_allreduce_pipeline", tensor_figure())


if __name__ == "__main__":
    main()
