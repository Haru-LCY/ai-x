# Lab4 8-GPU collective trace pipeline

This directory separates real-GPU capture from Garnet replay. The source trace
records collective operations that were actually executed by NCCL. A compiler
then lowers supported operations into an architecture-neutral replay request
stream. Keeping both files prevents the simulator from silently changing the
meaning of unsupported collectives.

## Capture on the local eight-H100 node

```sh
PY=/mnt/einsia/aws02-nvme/einsia-shared/homes/kaisen/miniforge3/envs/void/bin/python
$PY -m torch.distributed.run --standalone --nproc-per-node=8 \
  util/lab4_trace/capture_collectives.py \
  --output traces/h100_8gpu_collectives.json

$PY util/lab4_trace/validate_trace.py traces/h100_8gpu_collectives.json
```

The controlled workload executes gradient-style `all_reduce` operations and
root-to-all `broadcast` operations at several tensor sizes. It is deliberately
described as an executed training-style collective microbenchmark, not as a
full PyTorch model trace.

## Compile multicast replay requests

```sh
$PY util/lab4_trace/compile_replay.py \
  traces/h100_8gpu_collectives.json \
  --output traces/h100_8gpu_broadcast_replay.json \
  --rank-map 0,1,2,3,4,5,6,7 \
  --network-clock-ghz 1.0 --flit-bytes 16 --chunk-bytes 4096 \
  --byte-scale 0.0009765625 --time-scale 0.0009765625
```

The example uses explicit 1/1024 payload and inter-event time scales because
cycle-accurate gem5 cannot practically replay hundreds of MiB at native size.
Scaling both by the same factor preserves the trace's offered-byte-rate ratio.
The source trace retains exact measured sizes and times, and every replay file
records both scale factors. Sensitivity runs may deliberately vary them, but
results must never present scaled simulation traffic as native H100 traffic.

Broadcast replay lowers payload chunks into variable-length tree multicast
packets. All-reduce uses a separate, explicit scalar-lane contract because the
implemented in-router reduction datapath accepts one flit per rank and lane.
It is a true reduce-then-broadcast tree, not a unicast decomposition.

```sh
$PY util/lab4_trace/compile_allreduce_replay.py \
  traces/h100_8gpu_collectives.json \
  --output traces/h100_8gpu_allreduce_replay.json \
  --byte-scale 0.0009765625 --time-scale 0.0009765625
```

At these scales the checked-in trace yields 15 all-reduce events, 6,720
scalar lanes, and 53,760 rank contribution flits. Lanes retain their source
event's release eligibility but serialize through the one-active-lane router
accumulator; this is a functional trace replay, not a wide/vector reduction
throughput model.

## Audit a compiled replay

Before a replay is handed to a Garnet consumer, validate its request-level
contract and independently recompute the flit total:

```sh
$PY util/lab4_trace/validate_replay.py traces/h100_8gpu_broadcast_replay.json
# PASS: ... requests=30 total_work_flits=6720
$PY util/lab4_trace/validate_replay.py traces/h100_8gpu_allreduce_replay.json
# PASS: ... requests=15 total_work_flits=53760
```

The validator rejects duplicate IDs, non-monotonic release cycles, invalid
source/destination sets, and payload/flit arithmetic mismatches.

## Garnet replay smoke run

The first consumer supports replay v1 files with one fixed source and
destination set (the checked-in broadcast replay has this shape). It preserves
per-request release cycles and packet flit counts:

```sh
$GEM5 -d /tmp/replay-run configs/example/garnet_synth_traffic.py \
  --network=garnet --topology=Mesh_XY --num-cpus=4 --num-dirs=4 \
  --mesh-rows=2 --routing-algorithm=1 \
  --multicast-mode=tree_multicast \
  --multicast-replay-file=/tmp/replay.json
```

The consumer intentionally rejects traces with changing source or destination
sets; supporting those requires per-request destination masks in the network
protocol rather than silently changing the collective semantics.

Run the all-reduce replay with `--lab4-all-reduce` and
`--all-reduce-replay-file=traces/h100_8gpu_allreduce_replay.json`. The strict
paired runner is `tests/gem5/lab4/run_allreduce_trace_replay.py`.
