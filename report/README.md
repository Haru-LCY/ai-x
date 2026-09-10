# Topic 3/4 report artifacts

This directory contains the final current-revision evaluation of router-level
multicast, bypass express links, real-H100 trace replay, and tensor all-reduce.
The gem5 base revision is `77fcf26d57`; manifests additionally record hashes
for every modified source used by the simulator binary.  The original
multicast/tensor snapshot was run on August 10, 2026, and the expanded
4x4/8x8 multicast study was run on September 7, 2026.  The original
geometric-mean bypass screen
and the subsequent multi-hop stride refinement were run on September 6, 2026.
The refinement was launched from `1e8764cde7`; the manifest's source hashes
match the pressure-aware implementation committed as `ea4c3c9b0f`. Raw outputs
are git-ignored, while compact CSV/JSON snapshots and generated figures are
retained.

## Contents

- `ai_collectives_report.tex/pdf`: final Topic 3/4 report;
- `multicast_report.tex`: earlier standalone multicast/tensor report;
- `data/multicast_paired.csv`: 432 paired comparisons across 4x4 and 8x8;
- `data/multicast_results.json`: 432 paired rows and 864 raw runs;
- `data/aggregate_*.csv`: generated summary tables;
- `data/bypass_optimization_*.csv`: static/adaptive data-VNet A/B summaries;
- `data/bypass_multihop_summary.csv`: compact 1,536-pair multi-hop refinement;
- `data/bypass_multihop_manifest.json`: exact arguments and source hashes for
  the 3,072-run refinement;
- `data/bypass_refinement_pilot.csv`: like-for-like 96-pair policy selection;
- `data/bypass_hotspot_radius_pilot.csv`: rejected radius 0/1/2/3 hotspot-guard
  follow-up on the same 96-pair pilot plus the known worst case;
- `data/worst_throughput_cases.csv`: ten lowest-throughput comparisons;
- `data/trace_replay_summary.csv`: compact T3/T4 accepted measurements;
- `data/trace_replay_provenance.txt`: trace hashes, semantics, and artifact paths;
- `bypass_g9.md`, `bypass_g10.md`: bypass cost and interaction validation reports;
- `figures/*.pdf`: vector figures used by LaTeX;
- `figures/*.png`: preview-friendly copies;
- `scripts/plot_multicast.py`: multicast validation and plotting;
- `scripts/plot_bypass_topology.py`: final 4x4/8x8 bypass comparison figure;
- `scripts/build_final_report_data.py`: cross-artifact validation and
  bypass/tensor plotting.
- `scripts/generate_architecture_figures.py`: reproducible Graphviz diagrams
  for multicast replication, bypass topology/oracle routing, and tensor
  all-reduce lowering.

## Rebuild figures

The aggregate builder expects the raw artifact root named in
`data/provenance.txt`; restore that git-ignored directory before running all
four commands.  The compact CSV/JSON files are sufficient to inspect the
accepted measurements but intentionally do not contain every raw run.

```sh
python3 report/scripts/plot_multicast.py
python3 report/scripts/plot_bypass_topology.py
python3 report/scripts/build_final_report_data.py
python3 report/scripts/generate_architecture_figures.py
python3 report/scripts/sync_presentation_figures.py
```

The architecture-figure script requires Graphviz (`neato`) and writes both
vector PDFs and PNG previews into `figures/`.

The sync step copies the eleven report figures used by
`ai_collectives_report.tex` into `presentation2/public/` and verifies that the
two copies are byte-identical.  The report itself prefers those shared
presentation assets, so the PDF and slides render the same figure revisions.

The scripts reject missing/non-finite multicast pairs, inconsistent bypass
VNet/routing metadata, and inconsistent final artifact counts or statuses
before updating aggregate tables and figures.  The accepted bypass evidence is
10,752 successful gem5 runs: 7,680 runs in the original four-design screen and
3,072 runs in the distance-scaled multi-hop stride refinement.  Raw simulator
directories are reproducible from the retained manifests and runner entry
points; compact tables alone are not a raw-data archive.

## Re-run the evaluated simulations

Exact numerical reproduction requires the source snapshot recorded for each
campaign; later routing changes intentionally do not reproduce the historical
source-only screen.  The runners below encode the remaining factorial defaults
(sizes, traffic, packet lengths, loads, and seeds), while the corresponding
JSON manifests record every expanded argument and source hash.

At integrated snapshot `77fcf26d57`:

```sh
python3 tests/gem5/lab4/run_multicast_performance.py \
  --output report/raw-results/multicast-4x4-8x8 --jobs 32
python3 tests/gem5/lab4/run_multicast_matrix.py \
  --output report/raw-results/multicast-correctness-8x8 \
  --jobs 32 --rounds 10 --packet-flits 1 4 16 64
python3 tests/gem5/lab4/run_tensor_allreduce_paired.py \
  --output report/raw-results/head-77fcf26d/tensor-paired
python3 tests/gem5/lab4/run_lab4_full_gate.py --jobs 32 \
  --output report/raw-results/head-77fcf26d/full-gate
```

At source-only bypass snapshot `135768001a97`:

```sh
python3 tests/gem5/lab4/run_bypass_performance.py \
  --output report/raw-results/head-77fcf26d/bypass-performance --jobs 64
```

At pressure-aware snapshot `ea4c3c9b0f` (whose relevant file hashes match
`data/bypass_multihop_manifest.json`):

```sh
python3 tests/gem5/lab4/run_bypass_performance.py \
  --families stride --wire-models distance_scaled \
  --bypass-adaptive-routing --bypass-adaptive-policy conservative \
  --bypass-adaptive-max-packet-flits 32 \
  --output report/raw-results/refinement-v3-full --jobs 32
```

The seven-gate runner checks functional correctness, backpressure, and trace
replay.  It does not run either large bypass performance campaign.

## Build the PDF

Run from the repository root so that figure and artifact paths match the
report source:

```sh
pdflatex -interaction=nonstopmode -halt-on-error \
  -output-directory=report report/ai_collectives_report.tex
pdflatex -interaction=nonstopmode -halt-on-error \
  -output-directory=report report/ai_collectives_report.tex
```

## Interpretation boundary

The report presents multicast and bypass results separately for 4x4 and 8x8,
then compares their scaling behavior.  Multicast uses one near-center source
per topology; the 8x8 fanout-32/64 scale-out cases remain separate from the
common-fanout comparison.  Bypass uses matched synthetic Garnet traffic at
both sizes and reports topology-specific resource proxies; physical timing
closure and energy remain outside the model. The H100 trace is a real executed
collective microbenchmark with explicit 1/1024 byte/time scaling, not a
complete model trace. Tensor all-reduce is multi-flit streaming but does not
model finite accumulator capacity or arithmetic latency. The report retains
negative and neutral results and explicitly documents the multicast fast path.
