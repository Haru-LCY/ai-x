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
    scalar_rows = {row["design"]: row for row in scalar["rows"]}
    tensor = json.loads(
        (tensor_dir / "summary.json").read_text(encoding="utf-8"))
    tensor_rows = {row["design"]: row for row in tensor["rows"]}

    designs = ["mesh_xy", "mesh_bypass"]
    comparisons = {}
    for design in designs:
        s = scalar_rows[design]
        t = tensor_rows[design]
        scalar_ticks = int(s["measurement_ticks"])
        tensor_ticks = int(t["measurement_ticks"])
        comparisons[design] = {
            "scalar_measurement_ticks": scalar_ticks,
            "tensor_measurement_ticks": tensor_ticks,
            "measurement_speedup": scalar_ticks / tensor_ticks,
            "scalar_p95_ticks": int(s["p95_lane_ticks"]),
            "tensor_p95_ticks": int(t["p95_ticks"]),
            "scalar_source_flits": int(s["collective_source_flits"]),
            "tensor_source_flits": int(t["collective_source_flits"]),
            "scalar_router_flits": int(s["collective_router_flits"]),
            "tensor_router_flits": int(t["collective_router_flits"]),
        }

    paired = {
        "git_revision": scalar["provenance"]["git_revision"],
        "designs": comparisons,
        "p95_note": (
            "granularity differs: scalar p95 is per serialized lane, tensor "
            "p95 is per logical request; not directly comparable"
        ),
        "note": (
            "scaled Garnet trace simulation on 1/1024 byte/time scales; "
            "not native H100/NVLink performance"
        ),
    }
    (output / "paired_summary.json").write_text(
        json.dumps(paired, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    csv_lines = [
        "design,scalar_measurement_ticks,tensor_measurement_ticks,"
        "measurement_speedup,scalar_p95_ticks,tensor_p95_ticks,"
        "scalar_source_flits,tensor_source_flits,scalar_router_flits,"
        "tensor_router_flits"
    ]
    for design, c in comparisons.items():
        csv_lines.append(
            f"{design},{c['scalar_measurement_ticks']},"
            f"{c['tensor_measurement_ticks']},"
            f"{c['measurement_speedup']:.3f},{c['scalar_p95_ticks']},"
            f"{c['tensor_p95_ticks']},{c['scalar_source_flits']},"
            f"{c['tensor_source_flits']},{c['scalar_router_flits']},"
            f"{c['tensor_router_flits']}"
        )
    (output / "paired_summary.csv").write_text(
        "\n".join(csv_lines) + "\n", encoding="utf-8")

    for design in designs:
        c = comparisons[design]
        print(
            f"{design}: scalar measurement_ticks="
            f"{c['scalar_measurement_ticks']} tensor="
            f"{c['tensor_measurement_ticks']} "
            f"measurement speedup={c['measurement_speedup']:.3f}x"
        )
    print(f"artifacts: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
