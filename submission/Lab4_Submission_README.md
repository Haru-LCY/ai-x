# Lab 4 submission package

Team: Chunyu Liu and Boyan Pu

Project: Topic 3 (Microarchitecture) -- Bypass and Multicast, with a Topic 4
trace-driven tensor all-reduce extension.

## Package layout

- `report/ai_collectives_report.pdf`: final report.
- `source/`: only project-related files added or modified relative to the
  original gem5 base revision `15d01a23fed9773114ef1f46f21fb1f27d948d64`.
- `source/tests/gem5/lab4/`: correctness, performance, and replay runners.
- `source/util/lab4_trace/` and `source/traces/`: trace tooling and replay
  inputs used by the Topic 4 extension.
- `source/report/scripts/`: analysis and figure-generation source used for the
  current report.

Generated build products, raw simulation directories, presentation authoring
assets, unrelated repository files, and the unreported experimental `Ring.py`
topology are intentionally excluded.

## Quick validation

From a matching gem5 source tree, copy the contents of `source/` over the same
relative paths, build `build/Garnet_standalone/gem5.opt`, and run:

```sh
python3 tests/gem5/lab4/test_ai_trace_tools.py
python3 util/lab4_trace/validate_trace.py traces/h100_8gpu_collectives.json
python3 util/lab4_trace/validate_replay.py traces/h100_8gpu_broadcast_replay.json
python3 util/lab4_trace/validate_replay.py traces/h100_8gpu_allreduce_replay.json
python3 util/lab4_trace/validate_replay.py traces/h100_8gpu_tensor_allreduce_replay.json
```

The complete simulator gate is:

```sh
LD_LIBRARY_PATH=/path/to/python/lib \
  python3 tests/gem5/lab4/run_lab4_full_gate.py --jobs 8
```
