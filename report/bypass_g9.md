# Bypass G9 — cost-aware performance conclusion

Artifact: `report/raw-results/head-77fcf26d/bypass-performance`
Git revision: `135768001a976fb74e9693446630d71b82992102`
Validated runs: 7680 gem5 runs, 6144 paired seed cases, 2048 aggregate points. Offered-vector mismatches: 0.

## Validation evidence

- All raw result error arrays are empty; every curve has at least 4 points after the detected saturation point.
- The experiment contains 4×4 and 8×8 meshes, four traffic patterns, four packet sizes, 16 offered-load points, and seeds 1/7/17.
- Every run used the warm-up, measurement, drain, and cooldown windows recorded in `manifest.json`.

## Paired result by design

| design | seed pairs | latency geomean | median | throughput change | traversal change | regressions |
|---|---:|---:|---:|---:|---:|---:|
| diagonal-distance_scaled | 1,536 | 1.131× | 1.046× | 9.41% | -5.49% | 350 |
| diagonal-optimistic | 1,536 | 1.148× | 1.064× | 9.44% | -5.53% | 164 |
| stride-distance_scaled | 1,536 | 0.999× | 1.041× | 2.72% | 11.35% | 539 |
| stride-optimistic | 1,536 | 1.024× | 1.064× | 2.81% | 11.26% | 321 |

Latency ratios use geometric means; additive changes use arithmetic means. The optimistic model is an upper bound, while distance-scaled latency can erase shortcut gains. Router traversal reduction therefore does not imply lower end-to-end latency.

## Low-load and distance-scaled evidence

The table below averages offered load ≤0.1, where queue saturation does not dominate the latency comparison.

| design | latency geomean | median | regressions / 384 |
|---|---:|---:|---:|
| diagonal-distance_scaled | 0.999× | 1.015× | 179 / 384 |
| diagonal-optimistic | 1.036× | 1.041× | 15 / 384 |
| stride-distance_scaled | 0.993× | 0.996× | 193 / 384 |
| stride-optimistic | 1.060× | 1.059× | 21 / 384 |

Distance-scaled diagonal and stride are the hardware-relevant results. Their low-load geometric means are approximately neutral; gains in the full sweep come from favorable loaded cases.

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
| stride-distance_scaled | 4×4 uniform_random f4 load=1.5 | 14.625× | best |
| stride-optimistic | 4×4 bit_complement f1 load=1.0 | 0.026× | worst |
| stride-optimistic | 4×4 uniform_random f4 load=1.5 | 15.716× | best |

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

## Multi-hop stride refinement

The follow-up implements that architectural iteration without changing the
distance-scaled wire model.  A cycle-aware dynamic program selects a monotonic
stride express link at every Router, rather than at the source only.  An
all-pairs channel-dependency audit rejects cyclic route tables, while
conservative runtime admission falls back to XY for blocked/congested express
outputs and sustained hotspots.  Packets above 32 flits deliberately use XY.

Artifact: `report/data/bypass_multihop_manifest.json`

Compact results: `report/data/bypass_multihop_summary.csv`

Validated runs: 3,072/3,072 gem5 runs, 1,536 paired seed cases.

| group | pairs | latency geomean | throughput change | Router/flit reduction | >5% regressions |
|---|---:|---:|---:|---:|---:|
| overall | 1,536 | 1.385x | +18.52% | 16.79% | 4 |
| 4x4 | 768 | 1.264x | +3.91% | 15.98% | 1 |
| 8x8 | 768 | 1.518x | +33.13% | 17.59% | 3 |
| uniform random | 384 | 1.722x | +16.43% | 22.43% | 0 |
| transpose | 384 | 1.176x | +5.51% | 14.06% | 0 |
| bit complement | 384 | 1.808x | +51.62% | 13.89% | 0 |
| hotspot | 384 | 1.006x | +0.52% | 16.76% | 4 |

The refinement raises distance-scaled stride latency speedup from 0.999x to
1.385x.  This is not universal: its median is 1.038x, and the worst 8x8,
16-flit hotspot point is 0.787x.  The strong mean is chiefly a loaded-network
result; the low-load (offered load <= 0.1) geometric mean is 1.047x.
