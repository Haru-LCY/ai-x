# Lab4 collective and multicast regression

Current multicast status (2026-08-07): both `naive_unicast` and
`tree_multicast` are implemented. The implementation is not restricted to a
single flit: the expanded correctness matrix passes all 240 executions at 1,
4, 16, and 64 flits, including 8x8 local, sparse, random, and full-group cases.
The legacy collective matrix passes 11/11.  The performance study passes all
432 paired cases and 864 raw runs: 324 balanced 4x4/8x8 comparisons at fanouts
4/8/16, plus 108 8x8 scale-out comparisons at fanouts 32/64.

`run_collective_matrix.py` validates scalar all-reduce and multicast on 2x2,
3x3, and 4x4 `Mesh_XY` networks. `run_multicast_matrix.py` extends multicast
validation through 8x8. The matrices cover corner and interior roots,
uses completion-driven multi-round execution, and checks exact collective
statistics rather than accepting a timeout-based exit.

`run_allreduce_trace_replay.py` extends that scalar datapath to the audited
eight-H100 trace. It checks exact lane, contribution, reduction-merge,
router-flit, and delivery counts on paired Mesh_XY/Mesh_Bypass runs and writes
CSV/JSON plus full command and hash provenance. The implementation is scalar
per lane; it must not be reported as a vector/tensor-width reduction unit.

Build and run from the repository root:

```sh
LD_LIBRARY_PATH=/path/to/python/lib \
  scons build/Garnet_standalone/gem5.opt -j32 PROTOC=/bin/false
LD_LIBRARY_PATH=/path/to/python/lib \
  python3 tests/gem5/lab4/run_collective_matrix.py --jobs 4 --rounds 5
```

The runner creates a unique directory under `/tmp` and prints its path. Each
case retains `sim.log`, `stats.txt`, and the standard gem5 configuration files.
It fails if any round misses or duplicates a destination, if completion is not
the exit cause, or if source, Router-generated, delivery, and reduction counts
do not match the tree protocol.

Run the full paired multicast correctness matrix with:

```sh
LD_LIBRARY_PATH=/path/to/python/lib \
  python3 tests/gem5/lab4/run_multicast_matrix.py \
    --jobs 32 --rounds 10 --packet-flits 1 4 16 64 \
    --output report/raw-results/multicast-correctness-8x8
```

The multicast matrix covers both `naive_unicast` and `tree_multicast`,
exhaustively checks all non-empty 2x2 destination sets, exercises the 64-bit
destination mask with a full 8x8 group, and accepts one or more packet sizes
through `--packet-flits`. With `--output`, it also writes a persistent
`summary.json` that records the execution/comparison counts and parameters.

Run paired throughput experiments and emit `summary.csv` plus `summary.json`:

```sh
LD_LIBRARY_PATH=/path/to/python/lib \
  python3 tests/gem5/lab4/run_multicast_performance.py --jobs 32
```

Every paired case uses the same source, destination seed, packet size,
injection rate, phase lengths, and background rate. A run that reaches its
tick limit without completion is rejected. By default the runner uses source 5
on 4x4 and source 27 on 8x8, common fanouts 4/8/16, and 8x8-only fanouts 32/64.

Bypass/express links G1--G10 are implemented and accepted. Run the full paired
study with `run_bypass_performance.py`; its JSON/CSV artifacts and the
cost-aware conclusion are recorded under `/tmp/lab4-bypass-g8-*` and
`report/bypass_g9.md` and `report/bypass_g10.md`.

## Real H100 trace replay

The checked-in source trace is an executed eight-H100 NCCL collective
microbenchmark, not a complete model-training trace. Validate all three files
before simulation:

```sh
python3 util/lab4_trace/validate_trace.py traces/h100_8gpu_collectives.json
python3 util/lab4_trace/validate_replay.py traces/h100_8gpu_broadcast_replay.json
python3 util/lab4_trace/validate_replay.py traces/h100_8gpu_allreduce_replay.json
```

`run_trace_replay.py` validates 30 broadcast requests and 6,720 source flits.
`run_allreduce_trace_replay.py` validates 15 source events lowered into 6,720
scalar lanes, 53,760 rank contributions, 53,760 Router merges and deliveries,
and 147,840 collective Router flits. Both runners retain hashes, commands,
revision/dirty state, raw CSV/JSON, logs, and stats. All-reduce lanes are
serialized scalar operations and must not be described as vector hardware.
