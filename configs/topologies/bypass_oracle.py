"""Deterministic source-express/XY route oracle and dependency audit."""

from collections import deque


def build_oracle(topology):
    columns = topology["columns"]
    rows = topology["rows"]
    routers = columns * rows
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

    first_hops = ["XY"] * (routers * routers)
    routes = []
    dependency_graph = {}
    bypass_pairs = 0
    for source in range(routers):
        for destination in range(routers):
            if source == destination:
                routes.append(
                    {
                        "source": source,
                        "destination": destination,
                        "path": [source],
                        "channels": [],
                        "uses_bypass": False,
                    }
                )
                continue
            candidates = [
                link
                for link in outgoing[source]
                if 1 + distance(link["dst"], destination)
                < distance(source, destination)
            ]
            selected = min(
                candidates,
                key=lambda link: (
                    1 + distance(link["dst"], destination),
                    link["dst"],
                    link["name"],
                ),
                default=None,
            )
            path = [source]
            channels = []
            if selected is not None:
                path.append(selected["dst"])
                channels.append(selected["name"])
                first_hops[source * routers + destination] = selected["name"]
                bypass_pairs += 1
            current = path[-1]
            while current != destination:
                next_router = xy_step(current, destination)
                channels.append(f"XY_{current}_to_{next_router}")
                path.append(next_router)
                current = next_router
            if len(path) != len(set(path)):
                raise ValueError(f"route loop for {source}->{destination}: {path}")
            if path[-1] != destination:
                raise ValueError(f"misroute for {source}->{destination}: {path}")
            remaining = list(range(len(channels), 0, -1))
            if any(a <= b for a, b in zip(remaining, remaining[1:])):
                raise ValueError(
                    f"route rank does not decrease for {source}->{destination}"
                )
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
                    "uses_bypass": selected is not None,
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
        cyclic = sorted(channel for channel, degree in indegree.items() if degree > 0)
        raise ValueError(f"channel dependency graph is cyclic: {cyclic}")

    return {
        "policy": "source_express_then_xy",
        "routers": routers,
        "all_pairs": routers * routers,
        "nonlocal_pairs": routers * (routers - 1),
        "bypass_pairs": bypass_pairs,
        "first_hops": first_hops,
        "routes": routes,
        "channel_dependency": {
            "channels": len(dependency_graph),
            "dependencies": sum(len(value) for value in dependency_graph.values()),
            "dag": dag,
            "topological_order": topological_order,
            "edges": [
                [channel, successor]
                for channel in sorted(dependency_graph)
                for successor in sorted(dependency_graph[channel])
            ],
        },
    }
