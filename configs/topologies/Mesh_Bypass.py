# Copyright (c) 2026
# All rights reserved.

"""Express-link augmented Mesh topology.

The ordinary graph and Lab4 collective metadata always come from Mesh_XY.
This module only appends explicitly named bidirectional express links, leaving
the runnable baseline untouched.
"""

import json
from pathlib import Path

from topologies.bypass_oracle import build_oracle
from topologies.Mesh_XY import Mesh_XY


class _ExpressLinkNetworkProxy:
    """Append links on the network's first and only int_links assignment.

    SimObjects acquire a parent when assigned to a SimObject vector.  Replacing
    that vector after Mesh_XY returns would orphan the newly created links, so
    the augmented vector must be installed atomically.
    """

    def __init__(self, network, append_links):
        object.__setattr__(self, "_network", network)
        object.__setattr__(self, "_append_links", append_links)

    def __getattr__(self, name):
        return getattr(self._network, name)

    def __setattr__(self, name, value):
        if name == "int_links":
            value = self._append_links(value)
        setattr(self._network, name, value)


class Mesh_Bypass(Mesh_XY):
    description = "Mesh_Bypass"

    def makeTopology(self, options, network, IntLink, ExtLink, Router):
        mode = getattr(options, "bypass_mode", "none")
        rows = options.mesh_rows
        routers_count = options.num_cpus
        columns = routers_count // rows
        stride = options.bypass_stride
        budget = options.bypass_link_budget
        if stride < 2:
            raise ValueError("--bypass-stride must be at least 2")
        if budget < 0:
            raise ValueError("--bypass-link-budget must be non-negative")
        if options.bypass_link_latency < 0:
            raise ValueError("--bypass-link-latency must be non-negative")

        candidates = self._placement(
            mode, options.bypass_placement, columns, rows, stride
        )
        if budget:
            candidates = candidates[:budget]

        express_records = []
        base_latency = options.bypass_link_latency or options.link_latency

        def append_express_links(ordinary_links):
            next_link_id = max(int(link.link_id) for link in ordinary_links) + 1
            express_links = []
            for src, dst in candidates:
                src_x, src_y = src % columns, src // columns
                dst_x, dst_y = dst % columns, dst // columns
                span = abs(dst_x - src_x) + abs(dst_y - src_y)
                latency = (
                    base_latency
                    if options.bypass_wire_model == "optimistic"
                    else base_latency * span
                )
                for direction_src, direction_dst in ((src, dst), (dst, src)):
                    stable_name = f"Bypass_{direction_src}_to_{direction_dst}"
                    express_links.append(
                        IntLink(
                            link_id=next_link_id,
                            src_node=network.routers[direction_src],
                            dst_node=network.routers[direction_dst],
                            src_outport=stable_name,
                            dst_inport=stable_name,
                            latency=latency,
                            weight=1,
                        )
                    )
                    express_records.append(
                        {
                            "link_id": int(next_link_id),
                            "name": stable_name,
                            "src": direction_src,
                            "dst": direction_dst,
                            "physical_span": span,
                            "latency": latency,
                        }
                    )
                    next_link_id += 1
            return list(ordinary_links) + express_links

        proxy = _ExpressLinkNetworkProxy(network, append_express_links)
        super().makeTopology(options, proxy, IntLink, ExtLink, Router)

        oracle_input = {
            "columns": columns,
            "rows": rows,
            "express_links": express_records,
        }
        routing_oracle = build_oracle(oracle_input)
        network.bypass_first_hops = routing_oracle["first_hops"]
        network.bypass_link_ids = [record["link_id"] for record in express_records]
        network.bypass_link_spans = [
            record["physical_span"] for record in express_records
        ]

        if options.bypass_topology_dump:
            self._dump_topology(
                options,
                columns,
                rows,
                candidates,
                express_records,
                routing_oracle,
            )

    @staticmethod
    def _placement(mode, placement, columns, rows, stride):
        if mode == "none":
            if placement.startswith("file:"):
                raise ValueError("file placement requires a bypass link family")
            return []
        if placement.startswith("file:"):
            return Mesh_Bypass._file_placement(
                Path(placement.split(":", 1)[1]), columns * rows
            )
        expected = "checkerboard" if mode == "diagonal" else "symmetric"
        if placement != expected:
            raise ValueError(
                f"{mode} mode requires --bypass-placement={expected} or file:PATH"
            )
        if mode == "diagonal":
            links = []
            for y in range(rows - 1):
                for x in range(columns - 1):
                    if (x + y) % 2 == 0:
                        src = y * columns + x
                        dst = (y + 1) * columns + x + 1
                    else:
                        src = y * columns + x + 1
                        dst = (y + 1) * columns + x
                    links.append((min(src, dst), max(src, dst)))
            return sorted(set(links))
        links = []
        for y in range(rows):
            for x in range(columns - stride):
                src = y * columns + x
                links.append((src, src + stride))
        for x in range(columns):
            for y in range(rows - stride):
                src = y * columns + x
                links.append((src, src + stride * columns))
        return sorted(set(links))

    @staticmethod
    def _file_placement(path, routers_count):
        data = json.loads(path.read_text(encoding="utf-8"))
        raw_links = data.get("links") if isinstance(data, dict) else data
        if not isinstance(raw_links, list):
            raise ValueError("bypass placement JSON must be a list or contain 'links'")
        links = []
        for item in raw_links:
            if isinstance(item, dict):
                src, dst = item.get("src"), item.get("dst")
            elif isinstance(item, list) and len(item) == 2:
                src, dst = item
            else:
                raise ValueError("each bypass placement entry must name src and dst")
            if not isinstance(src, int) or not isinstance(dst, int):
                raise ValueError("bypass endpoints must be integer Router ids")
            if not 0 <= src < routers_count or not 0 <= dst < routers_count:
                raise ValueError("bypass endpoint lies outside the Mesh")
            if src == dst:
                raise ValueError("bypass link cannot be a self-loop")
            links.append((min(src, dst), max(src, dst)))
        if len(set(links)) != len(links):
            raise ValueError("duplicate undirected bypass link in placement JSON")
        return sorted(links)

    @staticmethod
    def _dump_topology(
        options, columns, rows, links, express_records, routing_oracle
    ):
        ordinary_undirected = rows * (columns - 1) + columns * (rows - 1)
        radix = [0] * (columns * rows)
        for y in range(rows):
            for x in range(columns):
                router = y * columns + x
                radix[router] = (
                    int(x > 0) + int(x + 1 < columns)
                    + int(y > 0) + int(y + 1 < rows)
                )
        for src, dst in links:
            radix[src] += 1
            radix[dst] += 1
        dump = {
            "schema_version": 1,
            "mode": options.bypass_mode,
            "placement": options.bypass_placement,
            "wire_model": options.bypass_wire_model,
            "rows": rows,
            "columns": columns,
            "routers": columns * rows,
            "ordinary_unidirectional_links": 2 * ordinary_undirected,
            "express_undirected_links": len(links),
            "express_unidirectional_links": len(express_records),
            "total_express_manhattan_wire_length": sum(
                record["physical_span"] for record in express_records
            ) // 2,
            "router_radix": radix,
            "maximum_router_radix": max(radix),
            "average_router_radix": sum(radix) / len(radix),
            "express_links": express_records,
            "routing_oracle": routing_oracle,
        }
        path = Path(options.bypass_topology_dump)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(dump, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
