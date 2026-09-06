"""Deterministic, cycle-aware bypass route oracle and dependency audit."""

from collections import deque
from functools import lru_cache


def build_oracle(topology):
    columns = topology["columns"]
    rows = topology["rows"]
    routers = columns * rows
    mode = topology.get("mode", "diagonal")
    multi_hop = mode == "stride"
    link_latency = int(topology.get("link_latency", 1))
    router_latency = int(topology.get("router_latency", 1))
    express = topology.get("express_links", [])
    outgoing = [[] for _ in range(routers)]
    for link in express:
        outgoing[link["src"]].append(link)
    for links in outgoing:
        links.sort(key=lambda link: (link["dst"], link["name"]))

    def distance(src, dst):
        return abs(src % columns - dst % columns) + abs(
            src // columns - dst // columns
        )

    def xy_step(current, destination):
        current_x, destination_x = current % columns, destination % columns
        if current_x != destination_x:
            return current + (1 if destination_x > current_x else -1)
        return current + (columns if destination > current else -columns)

    def dor_express(link, destination):
        """Return whether a stride link preserves monotonic XY routing."""
        src, dst = link["src"], link["dst"]
        src_x, src_y = src % columns, src // columns
        dst_x, dst_y = dst % columns, dst // columns
        target_x, target_y = destination % columns, destination // columns
        if src_x != target_x:
            return (
                src_y == dst_y
                and (src_x < dst_x <= target_x or target_x <= dst_x < src_x)
            )
        return (
            src_x == dst_x
            and (src_y < dst_y <= target_y or target_y <= dst_y < src_y)
        )

    ordinary_edge_cost = link_latency + router_latency

    @lru_cache(maxsize=None)
    def best_stride_step(current, destination):
        """Minimum static cycle-cost DOR suffix and its first express link."""
        if current == destination:
            return 0, None
        ordinary_next = xy_step(current, destination)
        suffix_cost, _ = best_stride_step(ordinary_next, destination)
        choices = [
            (ordinary_edge_cost + suffix_cost, 0, ordinary_next, "", None)
        ]
        for link in outgoing[current]:
            if not dor_express(link, destination):
                continue
            suffix_cost, _ = best_stride_step(link["dst"], destination)
            cost = int(link["latency"]) + router_latency + suffix_cost
            # Prefer an ordinary hop on an exact cost tie. A bypass must
            # remove a modeled cycle rather than only one graph hop.
            choices.append((cost, 1, link["dst"], link["name"], link))
        cost, _, _, _, selected = min(choices)
        return cost, selected

    def source_express(current, destination):
        """Cycle-aware legacy diagonal choice: one express hop, then XY."""
        baseline = distance(current, destination) * ordinary_edge_cost
        candidates = []
        for link in outgoing[current]:
            remaining = distance(link["dst"], destination)
            if remaining >= distance(current, destination):
                continue
            cost = (
                int(link["latency"])
                + router_latency
                + remaining * ordinary_edge_cost
            )
            if cost < baseline:
                candidates.append((cost, link["dst"], link["name"], link))
        return min(candidates, default=(0, 0, "", None))[-1]

    next_links = [None] * (routers * routers)
    first_hops = ["XY"] * (routers * routers)
    next_hop_destinations = [-1] * (routers * routers)
    for current in range(routers):
        for destination in range(routers):
            if current == destination:
                continue
            selected = (
                best_stride_step(current, destination)[1]
                if multi_hop
                else source_express(current, destination)
            )
            if selected is not None:
                index = current * routers + destination
                next_links[index] = selected
                first_hops[index] = selected["name"]
                next_hop_destinations[index] = selected["dst"]

    routes = []
    dependency_graph = {}
    bypass_pairs = 0
    bypass_hops = 0
    for source in range(routers):
        for destination in range(routers):
            path = [source]
            channels = []
            current = source
            express_allowed = True
            while current != destination:
                selected = next_links[current * routers + destination]
                if selected is not None and (multi_hop or express_allowed):
                    next_router = selected["dst"]
                    channels.append(selected["name"])
                    express_allowed = multi_hop
                else:
                    next_router = xy_step(current, destination)
                    channels.append(f"XY_{current}_to_{next_router}")
                    if not multi_hop:
                        express_allowed = False
                path.append(next_router)
                current = next_router
                if len(path) > routers:
                    raise ValueError(
                        f"route does not converge for {source}->{destination}: {path}"
                    )
            if len(path) != len(set(path)):
                raise ValueError(f"route loop for {source}->{destination}: {path}")
            express_count = sum(
                channel.startswith("Bypass_") for channel in channels
            )
            bypass_pairs += int(express_count > 0)
            bypass_hops += express_count
            remaining = list(range(len(channels), 0, -1))
            for channel in channels:
                dependency_graph.setdefault(channel, set())
            for channel, next_channel in zip(channels, channels[1:]):
                dependency_graph[channel].add(next_channel)
            routes.append(
                {
                    "source": source,
                    "destination": destination,
                    "path": path,
                    "channels": channels,
                    "remaining_route_rank": remaining,
                    "uses_bypass": express_count > 0,
                    "express_hops": express_count,
                }
            )

    indegree = {channel: 0 for channel in dependency_graph}
    for successors in dependency_graph.values():
        for successor in successors:
            indegree[successor] += 1
    ready = deque(
        sorted(channel for channel, degree in indegree.items() if degree == 0)
    )
    topological_order = []
    while ready:
        channel = ready.popleft()
        topological_order.append(channel)
        for successor in sorted(dependency_graph[channel]):
            indegree[successor] -= 1
            if indegree[successor] == 0:
                ready.append(successor)
    dag = len(topological_order) == len(dependency_graph)
    if not dag:
        cyclic = sorted(
            channel for channel, degree in indegree.items() if degree > 0
        )
        raise ValueError(f"channel dependency graph is cyclic: {cyclic}")

    return {
        "policy": "multi_hop_dor" if multi_hop else "source_express_then_xy",
        "multi_hop": multi_hop,
        "cost_model": {
            "ordinary_link_latency": link_latency,
            "router_latency": router_latency,
        },
        "routers": routers,
        "all_pairs": routers * routers,
        "nonlocal_pairs": routers * (routers - 1),
        "bypass_pairs": bypass_pairs,
        "bypass_hops": bypass_hops,
        "first_hops": first_hops,
        "next_hop_destinations": next_hop_destinations,
        "routes": routes,
        "channel_dependency": {
            "channels": len(dependency_graph),
            "dependencies": sum(
                len(value) for value in dependency_graph.values()
            ),
            "dag": dag,
            "topological_order": topological_order,
            "edges": [
                [channel, successor]
                for channel in sorted(dependency_graph)
                for successor in sorted(dependency_graph[channel])
            ],
        },
    }
