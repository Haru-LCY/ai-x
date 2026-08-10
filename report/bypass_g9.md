# Bypass G9 — cost-aware performance conclusion

Artifact: `report/raw-results/head-77fcf26d/bypass-performance`
Git revision: `77fcf26d57a1a6cf402b40fe748d500746f6578c`
Validated runs: 7680 gem5 runs, 6144 paired seed cases, 2048 aggregate points. Offered-vector mismatches: 0.

## Gate evidence

- All raw result error arrays are empty; every curve has at least 4 points after the detected saturation point.
- The experiment contains 4×4 and 8×8 meshes, four traffic patterns, four packet sizes, 16 offered-load points, and seeds 1/7/17.
- The 17 cases that required a longer cooldown are recorded in `manifest.json` with their actual one-million-cycle window.

## Mean paired result by design

| design | points | latency speedup | throughput change | traversal change | regressions |
|---|---:|---:|---:|---:|---:|
| diagonal-distance_scaled | 512 | 1.629× | 6.41% | -2.82% | 225 |
| diagonal-optimistic | 512 | 1.723× | 10.61% | -7.03% | 48 |
| stride-distance_scaled | 512 | 0.981× | -1.94% | 15.50% | 319 |
| stride-optimistic | 512 | 1.103× | 3.68% | 10.10% | 99 |

The optimistic model is an upper bound: it gives small average gains, while distance-scaled latency can erase them. Router traversal reduction therefore does not imply lower end-to-end latency.

## Low-load and distance-scaled evidence

The table below averages offered load ≤0.1, where queue saturation does not dominate the latency comparison.

| design | bypass latency (cycles) | latency speedup | p95 speedup | regressions / 128 |
|---|---:|---:|---:|---:|
| diagonal-distance_scaled | 150.296 | 0.962× | 0.928× | 97 / 128 |
| diagonal-optimistic | 138.750 | 1.021× | 1.017× | 5 / 128 |
| stride-distance_scaled | 158.112 | 0.936× | 0.911× | 97 / 128 |
| stride-optimistic | 137.710 | 1.042× | 1.041× | 5 / 128 |

Distance-scaled diagonal and stride are the hardware-relevant results. Their low-load mean speedups are respectively below 1×; these are regressions, not missing data.

## Hotspot transfer

At offered load ≤0.1, hotspot traffic is compared with uniform_random using the same size, packet, seed, and design groups.

| design | hotspot latency speedup | uniform latency speedup | hotspot throughput change |
|---|---:|---:|---:|
| diagonal-distance_scaled | 0.942× | 0.972× | -0.63% |
| diagonal-optimistic | 1.011× | 1.023× | 0.14% |
| stride-distance_scaled | 0.907× | 0.945× | -1.33% |
| stride-optimistic | 1.035× | 1.053× | 0.04% |

## Worst and best paired points

| design | case | speedup | interpretation |
|---|---|---:|---|
| diagonal-distance_scaled | 4×4 bit_complement f1 load=1.0 | 0.031× | worst |
| diagonal-distance_scaled | 4×4 transpose f1 load=1.0 | 37.061× | best |
| diagonal-optimistic | 4×4 bit_complement f1 load=1.0 | 0.031× | worst |
| diagonal-optimistic | 4×4 transpose f1 load=1.0 | 37.536× | best |
| stride-distance_scaled | 4×4 bit_complement f1 load=1.0 | 0.026× | worst |
| stride-distance_scaled | 4×4 uniform_random f1 load=1.5 | 6.828× | best |
| stride-optimistic | 4×4 bit_complement f1 load=1.0 | 0.026× | worst |
| stride-optimistic | 4×4 uniform_random f1 load=1.5 | 8.058× | best |

## Static hardware cost

| size | placement | extra undirected links | wire length | max radix | buffer-slot proxy |
|---:|---|---:|---:|---:|---:|
| 4×4 | diagonal-distance_scaled | 9 | 18 | 8 | 432 |
| 4×4 | diagonal-optimistic | 9 | 18 | 8 | 432 |
| 4×4 | stride-distance_scaled | 16 | 32 | 6 | 768 |
| 4×4 | stride-optimistic | 16 | 32 | 6 | 768 |
| 8×8 | diagonal-distance_scaled | 49 | 98 | 8 | 2352 |
| 8×8 | diagonal-optimistic | 49 | 98 | 8 | 2352 |
| 8×8 | stride-distance_scaled | 96 | 192 | 8 | 4608 |
| 8×8 | stride-optimistic | 96 | 192 | 8 | 4608 |

## G9 conclusion and limits

1. The implementation is correct and reproducible, but the existing express placements are not universally beneficial.
2. Optimistic one-cycle links show the Router-hop upper bound only; distance-scaled links must be used for hardware claims and show mean low-load regressions in this matrix.
3. Diagonal uses fewer links than stride, while stride removes more Router traversals; both add radix, ports, buffers, and wire length.
4. Results are synthetic unicast Garnet traffic. They do not model energy, repeaters, physical timing closure, area, or application traces.
5. The next architectural iteration should optimize placement under a wire/radix budget or add a capacity-matched baseline; it should not claim a general speedup from hop count alone.
