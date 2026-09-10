"""One-command reproduction of every Lab4 tensor gate (H6 companion gates).

Orchestrates, in order:
  1. legacy scalar collective regression (11 cases)
  2. multicast correctness matrix (240 executions / 120 mode-matched pairs)
  3. T3 H100 broadcast replay (30 requests, 6,720 flits)
  4. tensor correctness matrix H2+H4 (14 cases)
  5. tensor backpressure matrix H3 (32 cases, link-latency x router-latency
     x outstanding)
  6. tensor H100 trace replay H5 (15 logical requests, Mesh_XY + Mesh_Bypass)
  7. paired scalar-vs-tensor H6

Any failing gate fails the whole run; a summary CSV records each gate's
status and artifact location.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
TESTS = REPO_ROOT / "tests" / "gem5" / "lab4"
TRACES = REPO_ROOT / "traces"


def run_gate(name, script, arguments, expected, output):
    command = [sys.executable, str(TESTS / script), *arguments]
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    ok = result.returncode == 0 and expected in result.stdout
    tail = result.stdout.strip().splitlines()[-6:]
    print(f"{'PASS' if ok else 'FAIL'} {name}")
    for line in tail:
        print(f"  {line}")
    return {
        "gate": name,
        "script": script,
        "status": "PASS" if ok else "FAIL",
        "returncode": result.returncode,
        "expected": expected,
        "tail": " | ".join(tail),
        "artifacts": str(output / name) if output else "",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gem5", type=Path)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--collective-rounds", type=int, default=3)
    parser.add_argument("--multicast-rounds", type=int, default=5)
    args = parser.parse_args()
    gem5 = args.gem5 or REPO_ROOT / "build" / "Garnet_standalone" / "gem5.opt"
    if not gem5.is_file():
        parser.error(f"gem5 binary does not exist: {gem5}")
    output = args.output or Path(tempfile.mkdtemp(prefix="lab4-full-gate-"))
    output.mkdir(parents=True, exist_ok=True)

    gates = [
        run_gate(
            "legacy_collective_11",
            "run_collective_matrix.py",
            ["--rounds", str(args.collective_rounds),
             "--jobs", str(args.jobs)],
            "PASS: all 11 Lab4 collective cases",
            output,
        ),
        run_gate(
            "multicast_240",
            "run_multicast_matrix.py",
            ["--jobs", str(args.jobs),
             "--rounds", str(args.multicast_rounds),
             "--packet-flits", "1", "4", "16", "64"],
            "PASS: all 240 executions",
            output,
        ),
        run_gate(
            "t3_broadcast_30",
            "run_trace_replay.py",
            ["--gem5", str(gem5),
             "--source-trace", str(TRACES / "h100_8gpu_collectives.json"),
             "--replay", str(TRACES / "h100_8gpu_broadcast_replay.json"),
             "--output", str(output / "t3_broadcast"),
             "--sim-cycles", "50000000"],
            "PASS: paired trace replay artifacts",
            output,
        ),
        run_gate(
            "tensor_matrix_14",
            "run_tensor_allreduce_matrix.py",
            ["--gem5", str(gem5), "--jobs", str(args.jobs)],
            "PASS: all 14 Lab4 tensor cases",
            output,
        ),
        run_gate(
            "tensor_backpressure_32",
            "run_tensor_allreduce_backpressure.py",
            ["--gem5", str(gem5), "--jobs", str(args.jobs)],
            "PASS: all 32 Lab4 backpressure cases",
            output,
        ),
        run_gate(
            "tensor_trace_replay_h5",
            "run_tensor_allreduce_trace_replay.py",
            ["--gem5", str(gem5)],
            "PASS mesh_xy",
            output,
        ),
        run_gate(
            "tensor_paired_h6",
            "run_tensor_allreduce_paired.py",
            ["--gem5", str(gem5)],
            "measurement speedup",
            output,
        ),
    ]

    (output / "full_gate_summary.csv").write_text(
        "gate,script,status,returncode,expected,tail,artifacts\n"
        + "".join(
            f"{g['gate']},{g['script']},{g['status']},{g['returncode']},"
            f"\"{g['expected']}\",\"{g['tail']}\",{g['artifacts']}\n"
            for g in gates
        ),
        encoding="utf-8",
    )
    print(f"artifacts: {output}")
    failed = [g["gate"] for g in gates if g["status"] == "FAIL"]
    if failed:
        print(f"FAIL: {len(failed)} of {len(gates)} gates: {', '.join(failed)}")
        return 1
    print(f"PASS: all {len(gates)} Lab4 gates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
