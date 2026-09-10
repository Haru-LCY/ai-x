#!/usr/bin/env python3

"""Keep the report's rendered figures identical to the Slidev assets."""

from __future__ import annotations

import argparse
import filecmp
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT_FIGURES = ROOT / "report" / "figures"
PRESENTATION_FIGURES = ROOT / "presentation2" / "public"

SHARED_FIGURES = (
    "training_to_network.png",
    "multicast_baseline_4x4.png",
    "multicast_tree_4x4.png",
    "latency_speedup_by_group.png",
    "internal_link_flit_reduction_by_group_packet.png",
    "throughput_change_by_group_packet.png",
    "bypass_diagonal_4x4.png",
    "bypass_stride_4x4.png",
    "bypass_traffic_pattern_structure.png",
    "bypass_latency_speedup_by_traffic_pattern.png",
    "throughput_by_traffic_packet_avg.png",
    "tensor_allreduce_pipeline.png",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify equality without copying files",
    )
    args = parser.parse_args()

    missing = [
        name for name in SHARED_FIGURES
        if not (REPORT_FIGURES / name).is_file()
    ]
    if missing:
        raise SystemExit(f"missing report figures: {', '.join(missing)}")

    PRESENTATION_FIGURES.mkdir(parents=True, exist_ok=True)
    if not args.check:
        for name in SHARED_FIGURES:
            shutil.copy2(REPORT_FIGURES / name, PRESENTATION_FIGURES / name)

    drifted = [
        name for name in SHARED_FIGURES
        if not (PRESENTATION_FIGURES / name).is_file()
        or not filecmp.cmp(
            REPORT_FIGURES / name,
            PRESENTATION_FIGURES / name,
            shallow=False,
        )
    ]
    if drifted:
        raise SystemExit(f"figure copies differ: {', '.join(drifted)}")

    print(f"PASS: {len(SHARED_FIGURES)} shared figures are byte-identical")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
