# Audited 8-H100 trace snapshot

`h100_8gpu_collectives.json` was captured on 2026-08-07 by executing NCCL
collectives with PyTorch 2.8.0, CUDA 12.8, and NCCL 2.27.3 on eight NVIDIA H100
80GB HBM3 GPUs. It contains 48 events: two warmup, five measurement, and one
cooldown iteration, each with three `all_reduce` and three `broadcast`
operations at 1, 4, and 16 MiB.

This is an executed training-style collective microbenchmark. It is not a
trace of a complete model or optimizer and must not be described as one.

`h100_8gpu_broadcast_replay.json` contains only the 15 measured broadcast
events. It maps ranks 0--7 to Routers 0--7, divides each tensor into 4 KiB
chunks, and applies explicit 1/1024 byte and time scales. The resulting 30
requests contain 6,720 simulated flits while retaining source event ids and
native tensor byte counts.

SHA-256 snapshot identifiers:

```text
c65857924f2a4be0958124a480d60e4f402df5684e5a9b04b7e44427d4933afd  h100_8gpu_collectives.json
7745c3f0f2b282c42e062998159e5d1ef21e9af032ac96f394c3e133d5b2a87f  h100_8gpu_broadcast_replay.json
```

Validation and regeneration commands are documented in
`util/lab4_trace/README.md`. The compiled request stream is an intermediate
representation; Garnet consumption is the next integration step.
