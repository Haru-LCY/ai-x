"""Paired performance comparison: serialized scalar lanes vs tensor (H6).

Runs the same eight-H100 all-reduce trace through the legacy scalar-lane
lowering and the new tensor streaming datapath (both on Mesh_XY, same root,
same 1/1024 byte/time scales, same sim budget) and reports absolute numbers
plus the observed speedup. The result is a scaled Garnet trace simulation,
not native H100/NVLink performance.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCALAR_RUNNER = REPO_ROOT / "tests" / "gem5" / "lab4" / \
    "run_allreduce_trace_replay.py"
TENSOR_RUNNER = REPO_ROOT / "tests" / "gem5" / "lab4" / \
    "run_tensor_allreduce_trace_replay.py"
SOURCE_TRACE = REPO_ROOT / "traces" / "h100_8gpu_collectives.json"
SCALAR_REPLAY = REPO_ROOT / "traces" / "h100_8gpu_allreduce_replay.json"


def run_runner(runner, arguments):
    result = subprocess.run(
        [sys.executable, str(runner), *arguments],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(f"{runner.name} failed:\n{result.stdout[-2000:]}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gem5", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--sim-cycles", type=int, default=100_000_000)
    args = parser.parse_args()
    gem5 = args.gem5 or REPO_ROOT / "build" / "Garnet_standalone" / "gem5.opt"
    if not gem5.is_file():
        parser.error(f"gem5 binary does not exist: {gem5}")
    output = args.output or Path(tempfile.mkdtemp(prefix="lab4-tensor-paired-"))

    scalar_dir = output / "scalar"
    tensor_dir = output / "tensor"
    run_runner(SCALAR_RUNNER, [
        "--gem5", str(gem5),
        "--source-trace", str(SOURCE_TRACE),
        "--replay", str(SCALAR_REPLAY),
        "--output", str(scalar_dir),
        "--sim-cycles", str(args.sim_cycles),
    ])
    run_runner(TENSOR_RUNNER, [
        "--gem5", str(gem5),
        "--output", str(tensor_dir),
        "--sim-cycles", str(args.sim_cycles),
    ])

    scalar = json.loads(
        (scalar_dir / "summary.json").read_text(encoding="utf-8"))
    scalar_row = next(row for row in scalar["rows"]
                      if row["design"] == "mesh_xy")
    tensor = json.loads(
        (tensor_dir / "summary.json").read_text(encoding="utf-8"))
    tensor_row = tensor["row"]

    scalar_ticks = int(scalar_row["measurement_ticks"])
    tensor_ticks = int(tensor_row["measurement_ticks"])
    scalar_p95 = int(scalar_row["p95_lane_ticks"])
    tensor_p95 = int(tensor_row["p95_ticks"])
    paired = {
        "git_revision": scalar["provenance"]["git_revision"],
        "scalar_measurement_ticks": scalar_ticks,
        "tensor_measurement_ticks": tensor_ticks,
        "measurement_speedup": scalar_ticks / tensor_ticks,
        "scalar_p95_ticks": scalar_p95,
        "tensor_p95_ticks": tensor_p95,
        "p95_note": (
            "granularity differs: scalar p95 is per serialized lane, tensor "
            "p95 is per logical request; not directly comparable"
        ),
        "scalar_source_flits": int(scalar_row["collective_source_flits"]),
        "tensor_source_flits": int(tensor_row["collective_source_flits"]),
        "scalar_router_flits": int(scalar_row["collective_router_flits"]),
        "tensor_router_flits": int(tensor_row["collective_router_flits"]),
        "note": (
            "scaled Garnet trace simulation on 1/1024 byte/time scales; "
            "not native H100/NVLink performance"
        ),
    }
    (output / "paired_summary.json").write_text(
        json.dumps(paired, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    (output / "paired_summary.csv").write_text(
        "git_revision,scalar_measurement_ticks,tensor_measurement_ticks,"
        "measurement_speedup,scalar_p95_ticks,tensor_p95_ticks,"
        "scalar_source_flits,tensor_source_flits,scalar_router_flits,"
        "tensor_router_flits\n"
        f"{paired['git_revision']},{scalar_ticks},{tensor_ticks},"
        f"{paired['measurement_speedup']:.3f},{scalar_p95},{tensor_p95},"
        f"{paired['scalar_source_flits']},{paired['tensor_source_flits']},"
        f"{paired['scalar_router_flits']},{paired['tensor_router_flits']}\n",
        encoding="utf-8")

    print(
        f"scalar: measurement_ticks={scalar_ticks} p95={scalar_p95}\n"
        f"tensor: measurement_ticks={tensor_ticks} p95={tensor_p95}\n"
        f"measurement speedup: {paired['measurement_speedup']:.3f}x"
    )
    print(f"artifacts: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
