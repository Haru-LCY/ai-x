# Topic 3/4 report artifacts

This directory contains the final current-revision evaluation of router-level
multicast, bypass express links, real-H100 trace replay, and tensor all-reduce.
The gem5 base revision is `77fcf26d57`; manifests additionally record hashes
for every modified source used by the simulator binary.  The multicast/tensor
snapshot was run on August 10, 2026.  The original geometric-mean bypass screen
and the subsequent multi-hop stride refinement were run on September 6, 2026
with refinement based on commit `1e8764cde7`. Raw outputs are git-ignored, while compact
CSV/JSON snapshots and generated figures are retained.

## Contents

- `ai_collectives_report.tex/pdf`: final Topic 3/4 report;
- `multicast_report.tex`: integrated Topic 3/4 LaTeX report;
- `data/multicast_paired.csv`: 162 paired comparisons;
- `data/multicast_results.json`: 162 paired rows and 324 raw runs;
- `data/aggregate_*.csv`: generated summary tables;
- `data/bypass_optimization_*.csv`: static/adaptive data-VNet A/B summaries;
- `data/bypass_multihop_summary.csv`: compact 1,536-pair multi-hop refinement;
- `data/bypass_multihop_manifest.json`: exact arguments and source hashes for
  the 3,072-run refinement;
- `data/bypass_refinement_pilot.csv`: like-for-like 96-pair policy selection;
- `data/worst_throughput_cases.csv`: ten lowest-throughput comparisons;
- `data/trace_replay_summary.csv`: compact T3/T4 accepted measurements;
- `data/trace_replay_provenance.txt`: trace hashes, semantics, and artifact paths;
- `bypass_g9.md`, `bypass_g10.md`: bypass cost and interaction validation reports;
- `figures/*.pdf`: vector figures used by LaTeX;
- `figures/*.png`: preview-friendly copies;
- `scripts/plot_multicast.py`: multicast validation and plotting;
- `scripts/build_final_report_data.py`: cross-artifact validation and
  bypass/tensor plotting.
- `scripts/generate_architecture_figures.py`: reproducible Graphviz diagrams
  for multicast replication, bypass topology/oracle routing, and tensor
  all-reduce lowering.

## Rebuild figures

The aggregate builder expects the raw artifact root named in
`data/provenance.txt`; restore that git-ignored directory before running all
three commands.  The compact CSV/JSON files are sufficient to inspect the
accepted measurements but intentionally do not contain every raw run.

```sh
python3 report/scripts/plot_multicast.py
python3 report/scripts/build_final_report_data.py
python3 report/scripts/generate_architecture_figures.py
```

The architecture-figure script requires Graphviz (`neato`) and writes both
vector PDFs and PNG previews into `figures/`.

The scripts reject missing/non-finite multicast pairs, inconsistent bypass
VNet/routing metadata, and inconsistent final artifact counts or statuses
before updating aggregate tables and figures.  The accepted bypass evidence is
10,752 successful gem5 runs: 7,680 runs in the original four-design screen and
3,072 runs in the distance-scaled multi-hop stride refinement.  Raw simulator
directories are reproducible from the retained manifests and compact tables.

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

The multicast data is a mechanism/regression study on one 4x4 topology and
one source placement. The bypass study uses synthetic Garnet traffic and does
not model physical timing closure or energy. The H100 trace is a real executed
collective microbenchmark with explicit 1/1024 byte/time scaling, not a
complete model trace. Tensor all-reduce is multi-flit streaming but does not
model finite accumulator capacity or arithmetic latency. The report retains
negative and neutral results and explicitly documents the multicast fast path.
