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
        'l_title [shape=plaintext, fixedsize=false, label="(a) Replicated-unicast baseline", '
        'pos="1.5,4.05!"];',
        'r_title [shape=plaintext, fixedsize=false, label="(b) Proposed tree multicast", '
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


def multicast_panel(kind: str) -> str:
    """Return one compact 4x4 multicast panel for LaTeX subfigures."""
    lines = [
        "digraph multicast_panel {",
        'graph [outputorder=edgesfirst, overlap=false, pad=0.10, '
        'bgcolor="white", size="4.8,4.2!"];',
        'node [shape=circle, fixedsize=true, width=0.38, height=0.38, '
        'fontname="Helvetica", fontsize=9, style=filled, '
        'fillcolor="#f7f8fa", color="#68727d", penwidth=1.1];',
        'edge [fontname="Helvetica", fontsize=8, arrowsize=0.55];',
        mesh_nodes("M", 0.0, source=5, destinations=(3, 10, 15)),
        mesh_edges("M", 0.0),
    ]
    if kind == "baseline":
        paths = [
            ("M5", "M6", "#4c78a8"), ("M6", "M7", "#4c78a8"),
            ("M7", "M3", "#4c78a8"),
            ("M5", "M6", "#f28e2b"), ("M6", "M10", "#f28e2b"),
            ("M5", "M6", "#59a14f"), ("M6", "M7", "#59a14f"),
            ("M7", "M11", "#59a14f"), ("M11", "M15", "#59a14f"),
        ]
        lines.extend(
            f'{src} -> {dst} [color="{color}", penwidth=2.7, arrowsize=0.6];'
            for src, dst, color in paths
        )
    elif kind == "tree":
        for src, dst in ((5, 6), (6, 7), (7, 3), (6, 10), (7, 11), (11, 15)):
            lines.append(
                f'M{src} -> M{dst} [color="#1769aa", penwidth=3.2, arrowsize=0.65];'
            )
        for node in (6, 7, 11):
            lines.append(f'M{node} [fillcolor="#9ecae1", color="#1769aa", penwidth=2.0];')
    else:
        raise ValueError(f"unknown multicast panel: {kind}")
    lines.append("}")
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
        # Invisible waypoint used only to give the curved S0 -> S2 overlay a
        # normal Graphviz-clipped arrowhead at S2, matching the multicast
        # figure's directed-edge treatment.
        's_express_arrow_tail [shape=point, fixedsize=true, width=0.01, '
        'height=0.01, label="", style=invis, pos="8.45,3.18!"];',
        mesh_edges("D", 0.0),
        mesh_edges("S", 7.0),
        'd_title [shape=plaintext, fixedsize=false, label="(a) Diagonal checkerboard (9 links)", '
        'pos="1.9,4.04!"];',
        's_title [shape=plaintext, fixedsize=false, label="(b) Stride-2 symmetric (16 links)", '
        'pos="8.9,4.04!"];',
        'd_note [shape=box, fixedsize=false, style="rounded,filled", fillcolor="#fff4e5", '
        'color="#d99a45", margin="0.08,0.04", '
        'label="0 → 5 (express) → 6 → 7 → 11 → 15\\n'
        'source express hop + deterministic XY suffix", pos="1.9,-0.82!"];',
        's_note [shape=box, fixedsize=false, style="rounded,filled", fillcolor="#fff4e5", '
        'color="#d99a45", margin="0.08,0.04", '
        'label="0 → 2 (express) → 3 → 7 → 11 → 15\\n'
        'source express hop + deterministic XY suffix", pos="8.9,-0.82!"];',
        'legend [shape=plaintext, fixedsize=false, label="gray = ordinary Mesh edges   orange dashed = installed bidirectional bypass links   '
        'orange solid arrow = oracle-selected express hop   blue solid = XY suffix   node orange/green = source/destination", '
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
            if prefix == "S" and (src, dst) == express:
                # Keep the installed link's bowed geometry clear of Router 1,
                # then let Graphviz place and clip the final arrow exactly as
                # it does for the multicast figure's ordinary directed edges.
                edge_pos = curved_edge_pos(src, dst, 7.0, bend=0.30)
                lines.append(
                    f'{prefix}{src} -> {prefix}{dst} [dir=none, '
                    f'color="{color}", penwidth=3.5, {edge_pos}];'
                )
                lines.append(
                    f's_express_arrow_tail -> {prefix}{dst} '
                    f'[color="{color}", penwidth=3.5, arrowsize=0.65];'
                )
                continue
            lines.append(
                f'{prefix}{src} -> {prefix}{dst} [color="{color}", '
                f'penwidth={3.5 if color == "#d95f02" else 2.8}, '
                f'arrowsize=0.65];'
            )
    for prefix in ("D", "S"):
        lines.extend([
            f'{prefix}0 [fillcolor="#f6c177", color="#b36b00", penwidth=2.0];',
            f'{prefix}15 [fillcolor="#b9e3c6", color="#3a8f62", penwidth=2.0];',
        ])
    lines.append("}")
    return "\n".join(lines)


def bypass_panel(kind: str) -> str:
    """Return one compact 4x4 bypass panel; captions and legends live in LaTeX."""
    diagonal = [(0, 5), (2, 5), (2, 7), (5, 8), (5, 10),
                (7, 10), (8, 13), (10, 13), (10, 15)]
    stride = [(0, 2), (0, 8), (1, 3), (1, 9), (2, 10), (3, 11),
              (4, 6), (4, 12), (5, 7), (5, 13), (6, 14), (7, 15),
              (8, 10), (9, 11), (12, 14), (13, 15)]
    candidates = diagonal if kind == "diagonal" else stride
    route = [0, 5, 10, 15] if kind == "diagonal" else [0, 2, 3, 11, 15]
    express_edges = ({(0, 5), (5, 10), (10, 15)} if kind == "diagonal"
                     else {(0, 2), (3, 11)})
    lines = [
        "digraph bypass_panel {",
        'graph [outputorder=edgesfirst, overlap=false, pad=0.10, '
        'bgcolor="white", size="4.8,4.2!"];',
        'node [shape=circle, fixedsize=true, width=0.38, height=0.38, '
        'fontname="Helvetica", fontsize=9, style=filled, '
        'fillcolor="#f7f8fa", color="#68727d", penwidth=1.1];',
        'edge [fontname="Helvetica", fontsize=8, arrowsize=0.55];',
        mesh_nodes("M", 0.0, source=0, destinations=(15,)),
        mesh_edges("M", 0.0),
    ]
    for src, dst in candidates:
        pos = ""
        if kind == "diagonal" and (src, dst) == (0, 5):
            pos = ", " + straight_edge_pos(src, dst, 0.0)
        elif kind == "stride":
            pos = ", " + curved_edge_pos(src, dst, 0.0, bend=0.30)
        lines.append(
            f'M{src} -> M{dst} [dir=none, color="#d95f02", '
            f'style=dashed, penwidth=1.8{pos}];'
        )
    for src, dst in zip(route, route[1:]):
        color = "#d95f02" if (src, dst) in express_edges else "#1769aa"
        if (src, dst) in express_edges:
            if kind == "stride":
                p0, c1, c2, p3 = curved_edge_geometry(
                    src, dst, 0.0, bend=0.30
                )
                pos = curved_edge_pos(src, dst, 0.0, bend=0.30)
            else:
                p0 = (src % 4, 3 - src // 4)
                p3 = (dst % 4, 3 - dst // 4)
                c1 = (p0[0] + (p3[0] - p0[0]) / 3.0,
                      p0[1] + (p3[1] - p0[1]) / 3.0)
                c2 = (p0[0] + 2.0 * (p3[0] - p0[0]) / 3.0,
                      p0[1] + 2.0 * (p3[1] - p0[1]) / 3.0)
                pos = straight_edge_pos(src, dst, 0.0)
            # Match the reference figure: draw the full express curve without
            # an arrow, then overlay its final quarter with the same ordinary
            # Graphviz-clipped arrow used by the blue route segments.
            t = 0.75
            u = 1.0 - t
            anchor = (
                u**3 * p0[0] + 3 * u**2 * t * c1[0]
                + 3 * u * t**2 * c2[0] + t**3 * p3[0],
                u**3 * p0[1] + 3 * u**2 * t * c1[1]
                + 3 * u * t**2 * c2[1] + t**3 * p3[1],
            )
            marker = f"express_arrow_{kind}_{src}_{dst}"
            lines.append(
                f'{marker} [shape=point, fixedsize=true, width=0.01, '
                f'height=0.01, label="", style=invis, '
                f'pos="{anchor[0]},{anchor[1]}!"];'
            )
            lines.append(
                f'M{src} -> M{dst} [dir=none, color="{color}", '
                f'penwidth=3.2, {pos}];'
            )
            lines.append(
                f'{marker} -> M{dst} [color="{color}", penwidth=3.2, '
                f'arrowsize=0.65];'
            )
        else:
            lines.append(
                f'M{src} -> M{dst} [color="{color}", penwidth=3.2, '
                f'arrowsize=0.65];'
            )
    lines.extend([
        'M0 [fillcolor="#f6c177", color="#b36b00", penwidth=2.0];',
        'M15 [fillcolor="#b9e3c6", color="#3a8f62", penwidth=2.0];',
        "}",
    ])
    return "\n".join(lines)


def tensor_figure() -> str:
    lines = [
        "digraph tensor {",
        'graph [outputorder=edgesfirst, overlap=false, pad=0.18, '
        'bgcolor="white", size="10,6.2!"];',
        'node [shape=box, style="rounded,filled", fontname="Helvetica", '
        'fontsize=14, fontcolor="#25313c", color="#68727d", '
        'penwidth=1.15, margin="0.16,0.10"];',
        'edge [fontname="Helvetica", fontsize=11, fontcolor="#4d5965", '
        'color="#68727d", penwidth=1.45, arrowsize=0.65];',
        # Recorded input and the exact scaling performed by the compiler.
        'trace [label="Measured all-reduce stream\\n5 repetitions of 1 / 4 / 16 MiB\\n15 measurement events", '
        'fillcolor="#f3f5f7", pos="1.1,3.9!"];',
        'scale [label="Replay compiler\\nbytes and release times / 1024\\n16-byte Garnet flits", '
        'fillcolor="#e8f0f7", color="#4c78a8", pos="3.65,3.9!"];',
        'events [label="Each event, per rank\\n1 / 4 / 16 KiB -> 64 / 256 / 1,024 flits\\n6,720 lanes per rank in total", '
        'fillcolor="#e8f0f7", color="#4c78a8", pos="6.85,3.9!"];',
        'trace -> scale;',
        'scale -> events;',
        # The only manipulated variable in the paired comparison.
        'scalar [label="SCALAR LOWERING\\nN independent one-flit collectives per event\\n6,720 serialized collective rounds", '
        'fillcolor="#f4eef8", color="#8c6bb1", penwidth=1.55, '
        'pos="3.45,2.4!"];',
        'tensor [label="TENSOR LOWERING\\none N-flit packet per event and rank\\n15 collective requests; N = 64 / 256 / 1,024", '
        'fillcolor="#e8f6ee", color="#3a8f62", penwidth=1.55, '
        'pos="7.3,2.4!"];',
        'events -> scalar [label="same release cycles", color="#8c6bb1"];',
        'events -> tensor [label="same release cycles", color="#3a8f62"];',
        # Both representations execute the same lane-wise operation.
        'router [label="ROUTER COLLECTIVE FAST PATH\\nkey = (collective_id, lane_id)\\n8 rank contributions -> tree reduction -> root\\nroot -> one reduced flit per lane down the tree", '
        'fillcolor="#fff3df", color="#c27a16", penwidth=1.55, '
        'pos="5.4,0.85!"];',
        'scalar -> router [label="one lane at a time", color="#8c6bb1"];',
        'tensor -> router [label="stream lanes", color="#3a8f62"];',
        'validate [label="Validation at all 8 ranks\\nexact lane ID and deterministic sum\\nno missing, duplicate, or residual state", '
        'fillcolor="#e8f6ee", color="#3a8f62", pos="8.1,-0.5!"];',
        'router -> validate;',
        # Physical-count invariant and observed dependent metric.
        'counts [label="IDENTICAL COUNTED NETWORK WORK\\n53,760 source flits | 147,840 Router-forwarded flits", '
        'fillcolor="#f3f5f7", color="#68727d", pos="2.65,-0.5!"];',
        'window [label="OBSERVED SCALED REPLAY WINDOW\\nscalar 80.638 M ticks | tensor 17.055 M ticks | ratio 4.728x", '
        'fillcolor="#fff3df", color="#c27a16", penwidth=1.65, '
        'pos="5.4,-1.7!"];',
        'router -> counts;',
        'counts -> window [color="#c27a16"];',
        'validate -> window [color="#c27a16"];',
        "}",
    ]
    return "\n".join(lines)


def main() -> None:
    render("multicast_baseline_4x4", multicast_panel("baseline"))
    render("multicast_tree_4x4", multicast_panel("tree"))
    render("bypass_diagonal_4x4", bypass_panel("diagonal"))
    render("bypass_stride_4x4", bypass_panel("stride"))
    render("tensor_allreduce_pipeline", tensor_figure())


if __name__ == "__main__":
    main()
