#!/usr/bin/env python3

"""Rebuild and audit deterministic bypass routes from a topology dump."""

import argparse
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "configs"))

from topologies.bypass_oracle import build_oracle  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("topology", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    topology = json.loads(args.topology.read_text(encoding="utf-8"))
    oracle = build_oracle(topology)
    embedded = topology.get("routing_oracle")
    if embedded is not None and embedded != oracle:
        print("FAIL: embedded route oracle differs from independent rebuild")
        return 1
    output = args.output or args.topology.with_name("route-oracle.json")
    output.write_text(
        json.dumps(oracle, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    dependency = oracle["channel_dependency"]
    print(
        f"PASS: pairs={oracle['all_pairs']} nonlocal={oracle['nonlocal_pairs']} "
        f"bypass_pairs={oracle['bypass_pairs']} "
        f"channels={dependency['channels']} "
        f"dependencies={dependency['dependencies']} dag={dependency['dag']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
