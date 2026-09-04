# T3 — Paired real-GPU trace replay acceptance

## Status

PASS on 2026-08-07. The completion-driven runner replayed all 30 compiled
broadcast requests on both Mesh_XY and cost-aware Mesh_Bypass.

## Input provenance

- Source trace SHA-256:
  `c65857924f2a4be0958124a480d60e4f402df5684e5a9b04b7e44427d4933afd`
- Replay SHA-256:
  `7745c3f0f2b282c42e062998159e5d1ef21e9af032ac96f394c3e133d5b2a87f`
- Replay schema: `lab4.garnet_collective_replay.v1`
- Byte scale: `1/1024`
- Time scale: `1/1024`
- Expected requests: 30
- Expected source flits: 6,720

The source is an executed eight-H100 NCCL collective microbenchmark, not a
complete model-training trace. Scaled simulation traffic is not presented as
native H100 traffic.

## Final paired result

| design | completed | requests | source flits | measurement ticks | p95 ticks | express flits | wire-flit distance | credit stalls |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Mesh_XY | yes | 30 | 6,720 | 17,047,500 | 643,500 | 0 | 47,040 | 0 |
| cost-aware Mesh_Bypass | yes | 30 | 6,720 | 17,047,500 | 643,500 | 0 | 47,040 | 0 |

The full broadcast contains every rank. The cost-aware policy detects that the
ordinary XY edges are shared by other destinations and retains that tree,
eliminating the forced-bypass regression.

## Directed mechanism evidence

- Shared destination set `[1,2,3]`: zero express flits, 4,000 ticks/request.
- Sparse diagonal destination `[3]`: two express flits, 3,500 ticks/request.
- Forced-bypass full replay (diagnostic variant): 6,720 express flits,
  20,346,500 ticks, 53,760 wire-flit distance, and 13,380 credit stalls.

Thus bypass is active for a sparse multicast group, but is rejected when it
would destroy tree sharing. The final policy removes the measured 19.4%
forced-bypass latency regression.

## Reproduction

```sh
LD_LIBRARY_PATH=/mnt/einsia/aws02-nvme/einsia-shared/homes/kaisen/miniforge3/lib \
python3 tests/gem5/lab4/run_trace_replay.py \
  --gem5 build/Garnet_standalone/gem5.opt \
  --source-trace traces/h100_8gpu_collectives.json \
  --replay traces/h100_8gpu_broadcast_replay.json \
  --output /tmp/lab4-t3-final-p95 \
  --sim-cycles 30000000
```

Final artifacts:

- `/tmp/lab4-t3-final-p95/raw.csv`
- `/tmp/lab4-t3-final-p95/summary.json`
- `/tmp/lab4-t3-final-p95/provenance.json`
- `/tmp/lab4-t3-final-p95/mesh_xy/{sim.log,stats.txt}`
- `/tmp/lab4-t3-final-p95/mesh_bypass/{sim.log,stats.txt}`

The provenance records revision
`b7045e41e0aa0742d76ed529f800856440a4115c` and explicitly marks the worktree
dirty, so this run must not be represented as a clean committed revision.
