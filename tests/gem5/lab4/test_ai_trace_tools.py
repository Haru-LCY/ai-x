#!/usr/bin/env python3

"""Unit tests for the versioned AI collective trace compiler."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
TOOLS = REPO_ROOT / "util" / "lab4_trace"
sys.path.insert(0, str(TOOLS))

from trace_schema import TRACE_SCHEMA, TraceValidationError, validate_trace
from validate_replay import validate_allreduce_replay, validate_replay


def example_trace():
    return {
        "schema": TRACE_SCHEMA,
        "clock": "monotonic_ns",
        "world_size": 4,
        "metadata": {"capture_kind": "unit_test"},
        "events": [
            {
                "id": "all-reduce-0", "sequence": 0, "iteration": 0,
                "phase": "measurement", "op": "all_reduce",
                "participants": [0, 1, 2, 3], "root": None,
                "tensor_bytes": 64, "start_ns": 100, "duration_ns": 20,
            },
            {
                "id": "broadcast-0", "sequence": 1, "iteration": 0,
                "phase": "measurement", "op": "broadcast",
                "participants": [0, 1, 2, 3], "root": 1,
                "tensor_bytes": 80, "start_ns": 200, "duration_ns": 30,
            },
        ],
    }


class TraceToolsTest(unittest.TestCase):
    def test_valid_trace(self):
        self.assertEqual(len(validate_trace(example_trace())["events"]), 2)

    def test_duplicate_participant_rejected(self):
        trace = example_trace()
        trace["events"][1]["participants"] = [0, 1, 1, 3]
        with self.assertRaises(TraceValidationError):
            validate_trace(trace)

    def test_compile_broadcast_chunks(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.json"
            output = Path(directory) / "replay.json"
            source.write_text(json.dumps(example_trace()), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable, str(TOOLS / "compile_replay.py"), str(source),
                    "--output", str(output), "--rank-map", "3,2,1,0",
                    "--flit-bytes", "16", "--chunk-bytes", "32",
                ],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            replay = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(replay["selected_broadcast_event_count"], 1)
            self.assertEqual(replay["request_count"], 3)
            self.assertEqual(replay["requests"][0]["source_router"], 2)
            self.assertEqual(replay["requests"][0]["destination_routers"], [0, 1, 3])
            self.assertEqual(
                [request["packet_flits"] for request in replay["requests"]],
                [2, 2, 1],
            )
            self.assertEqual(replay["total_packet_flits"], 5)
            self.assertEqual(validate_replay(replay)["total_packet_flits"], 5)

    def test_explicit_byte_scaling(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.json"
            output = Path(directory) / "replay.json"
            source.write_text(json.dumps(example_trace()), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable, str(TOOLS / "compile_replay.py"), str(source),
                    "--output", str(output), "--byte-scale", "0.5",
                    "--time-scale", "0.25",
                    "--flit-bytes", "16", "--chunk-bytes", "32",
                ],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            replay = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(replay["byte_scale"], 0.5)
            self.assertEqual(replay["time_scale"], 0.25)
            self.assertEqual(replay["request_count"], 2)
            self.assertEqual(replay["requests"][0]["source_tensor_bytes"], 80)
            self.assertEqual(replay["requests"][0]["scaled_event_bytes"], 40)

    def test_compile_allreduce_scalar_lanes(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.json"
            output = Path(directory) / "allreduce.json"
            source.write_text(json.dumps(example_trace()), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(TOOLS / "compile_allreduce_replay.py"), str(source),
                    "--output", str(output), "--rank-map", "3,2,1,0",
                    "--reduction-root-rank", "1", "--flit-bytes", "16",
                    "--byte-scale", "0.5", "--time-scale", "0.25",
                ],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            replay = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(replay["selected_all_reduce_event_count"], 1)
            self.assertEqual(replay["request_count"], 1)
            self.assertEqual(replay["reduction_root_router"], 2)
            self.assertEqual(replay["requests"][0]["participant_routers"], [0, 1, 2, 3])
            self.assertEqual(replay["requests"][0]["scaled_event_bytes"], 32)
            self.assertEqual(replay["total_lane_rounds"], 2)
            self.assertEqual(replay["total_contribution_flits"], 8)
            validate_allreduce_replay(replay)


if __name__ == "__main__":
    unittest.main()
