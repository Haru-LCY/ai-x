# G10 — multicast interaction with bypass

Artifact: `report/raw-results/head-77fcf26d/multicast-bypass`
Validated factorial: 624 runs, 416 mesh/bypass pairs, 100 rounds per case; all raw errors are empty.

## Factorial result

| multicast mode | link model | pairs | latency speedup | p95 speedup | link-flit change | wire-distance change | regressions |
|---|---|---:|---:|---:|---:|---:|---:|
| naive_unicast | distance_scaled | 104 | 0.965× | 0.965× | 16.10% | 0.00% | 39 |
| naive_unicast | optimistic | 104 | 1.029× | 1.029× | 16.10% | 0.00% | 0 |
| tree_multicast | distance_scaled | 104 | 0.988× | 0.988× | 8.33% | 0.00% | 15 |
| tree_multicast | optimistic | 104 | 1.022× | 1.022× | 8.33% | 0.00% | 0 |

## Packet-size sensitivity

| mode | model | packet flits | latency speedup | link-flit change |
|---|---|---:|---:|---:|
| naive_unicast | distance_scaled | 1 | 1.034× | 16.10% |
| naive_unicast | distance_scaled | 4 | 0.968× | 16.10% |
| naive_unicast | distance_scaled | 16 | 0.934× | 16.10% |
| naive_unicast | distance_scaled | 64 | 0.923× | 16.10% |
| naive_unicast | optimistic | 1 | 1.073× | 16.10% |
| naive_unicast | optimistic | 4 | 1.031× | 16.10% |
| naive_unicast | optimistic | 16 | 1.010× | 16.10% |
| naive_unicast | optimistic | 64 | 1.003× | 16.10% |
| tree_multicast | distance_scaled | 1 | 1.027× | 8.33% |
| tree_multicast | distance_scaled | 4 | 0.985× | 8.33% |
| tree_multicast | distance_scaled | 16 | 0.972× | 8.33% |
| tree_multicast | distance_scaled | 64 | 0.969× | 8.33% |
| tree_multicast | optimistic | 1 | 1.064× | 8.33% |
| tree_multicast | optimistic | 4 | 1.018× | 8.33% |
| tree_multicast | optimistic | 16 | 1.005× | 8.33% |
| tree_multicast | optimistic | 64 | 1.001× | 8.33% |

## Interpretation

- Tree multicast bypass express-flit total is `85000` across paired runs; naive-unicast bypass express-flit total is `357000`.
- Tree multicast preserves the ordinary XY convergence tree; the bypass topology does not silently change multicast branch semantics.
- Naive unicast can use express links, so any interaction benefit must be separated from tree replication savings.
- This is a correctness/interaction study, not a replacement for the G8 unicast performance sweep or the G9 hardware-cost conclusion.
