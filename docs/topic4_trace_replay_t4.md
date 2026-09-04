# T4 — Real-trace in-network all-reduce acceptance

## Status

PASS on 2026-08-07. The 15 measured all-reduce events in the executed
eight-H100 trace were replayed as 6,720 scalar reduction lanes on both Mesh_XY
and Mesh_Bypass.

## Semantics and scope

The existing router datapath performs a real convergence-tree sum and then
broadcasts the result to every rank. It supports one scalar flit per rank per
active lane. T4 therefore lowers each scaled tensor into
`ceil(scaled_bytes / 16)` independent lanes. This is not a unicast
decomposition, but it is also not a wide/vector tensor reduction unit. Lanes
retain the source event release cycle and serialize when the scalar datapath is
busy.

Each rank contributes the deterministic value `rank + 1`; for eight ranks the
network interfaces assert that every delivered lane equals 36. A wrong sum,
reduce flit ejection, duplicate delivery, or timeout aborts/fails the run.

## Input provenance

- Source SHA-256:
  `c65857924f2a4be0958124a480d60e4f402df5684e5a9b04b7e44427d4933afd`
- All-reduce replay SHA-256:
  `ebd8386732b93e38c9be462fa48e66d16f46a29e42a9b457e5db5ba76dcbadad`
- Replay schema: `lab4.garnet_allreduce_replay.v1`
- Byte/time scale: `1/1024`, `1/1024`
- Events: 15; scalar lanes: 6,720
- Expected rank contributions: 53,760 flits

The source is a real NCCL collective microbenchmark executed on eight H100s,
not a full-model training trace. The scaled traffic is not native H100 volume.

## Final paired result

| metric | Mesh_XY | Mesh_Bypass |
|---|---:|---:|
| completed lanes | 6,720 | 6,720 |
| source contribution flits | 53,760 | 53,760 |
| router reduce merges | 53,760 | 53,760 |
| rank deliveries | 53,760 | 53,760 |
| collective router flits | 147,840 | 147,840 |
| replay measurement ticks | 80,638,000 | 80,638,000 |
| p95 lane ticks | 10,000 | 10,000 |
| wire-flit distance | 94,080 | 94,080 |
| express flits | 0 | 0 |

The count identities are structural: each lane has eight contributions, eight
router merges, eight deliveries, and `3N-2 = 22` collective router flits. The
wire count is `2(N-1) = 14` ordinary edge traversals per lane.

Mesh_Bypass ties Mesh_XY because the all-reduce convergence tree currently
uses ordinary XY parent/child edges and does not select express links. This is
a valid neutral baseline result, not evidence that bypass accelerates
all-reduce.

## Reproduction

```sh
LD_LIBRARY_PATH=/path/to/python/lib \
python3 tests/gem5/lab4/run_allreduce_trace_replay.py \
  --gem5 build/Garnet_standalone/gem5.opt \
  --source-trace traces/h100_8gpu_collectives.json \
  --replay traces/h100_8gpu_allreduce_replay.json \
  --output /tmp/lab4-t4-final-r2 --sim-cycles 100000000
```

Artifacts include `raw.csv`, `summary.json`, `provenance.json`, and per-design
`sim.log`/`stats.txt`. Provenance records the current revision and explicitly
marks the worktree dirty; it must not be represented as a clean committed run.
