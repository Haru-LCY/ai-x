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

Version 1 lowers only `broadcast`, whose root and destination semantics match
the existing Topic 3 multicast mechanism. `all_reduce` remains in the source
trace but is rejected as a replay operation until its reduction and
distribution phases can be represented without changing semantics.

The replay JSON is not yet consumed by Garnet. Adding that consumer is the
next integration step; the source trace and compiler can be developed and
audited independently of the bypass topology work.
