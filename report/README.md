# Topic 3/4 report artifacts

This directory contains the final current-revision evaluation of router-level
multicast, bypass express links, real-H100 trace replay, and tensor all-reduce.
The base revision is `77fcf26d57`; the optimization manifests additionally
record hashes for every modified source used by the accepted simulator binary.
All headline matrices were run on August 10, 2026. Raw outputs are git-ignored,
while compact CSV/JSON snapshots and generated figures are retained.

## Contents

- `ai_collectives_report.tex/pdf`: final eight-page Topic 3/4 report;
- `multicast_report.tex`: integrated Topic 3/4 LaTeX report;
- `data/multicast_paired.csv`: 162 paired comparisons;
- `data/multicast_results.json`: 162 paired rows and 324 raw runs;
- `data/aggregate_*.csv`: generated summary tables;
- `data/bypass_optimization_*.csv`: static/adaptive data-VNet A/B summaries;
- `data/worst_throughput_cases.csv`: ten lowest-throughput comparisons;
- `data/trace_replay_summary.csv`: compact T3/T4 accepted measurements;
- `data/trace_replay_provenance.txt`: trace hashes, semantics, and artifact paths;
- `bypass_g9.md`, `bypass_g10.md`: bypass cost and interaction gates;
- `figures/*.pdf`: vector figures used by LaTeX;
- `figures/*.png`: preview-friendly copies;
- `scripts/plot_multicast.py`: multicast validation and plotting;
- `scripts/build_final_report_data.py`: cross-artifact validation and
  bypass/tensor plotting.

## Rebuild figures

```sh
python3 report/scripts/plot_multicast.py
python3 report/scripts/build_final_report_data.py
```

The scripts reject missing/non-finite multicast pairs, inconsistent bypass
VNet/routing metadata, and inconsistent final artifact counts or statuses
before updating aggregate tables and figures. The bypass optimization raw
artifacts are under the git-ignored
`raw-results/bypass-optimization-v4/{static,adaptive}-data-vnet/` directories.

## Build the PDF

```sh
cd report
pdflatex -interaction=nonstopmode -halt-on-error ai_collectives_report.tex
pdflatex -interaction=nonstopmode -halt-on-error ai_collectives_report.tex
```

## Interpretation boundary

The multicast data is a mechanism/regression study on one 4x4 topology and
one source placement. The bypass study uses synthetic Garnet traffic and does
not model physical timing closure or energy. The H100 trace is a real executed
collective microbenchmark with explicit 1/1024 byte/time scaling, not a
complete model trace. Tensor all-reduce is multi-flit streaming but does not
model finite accumulator capacity or arithmetic latency. The report retains
negative and neutral results and explicitly documents the multicast fast path.
