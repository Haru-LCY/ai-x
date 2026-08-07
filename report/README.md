# Topic 3/4 report artifacts

This directory contains the reproducible multicast data snapshot plus the
audited bypass and real-H100 trace-replay conclusions. The multicast matrix
was captured at commit `d14545edcb`; trace replay was accepted before the
clean integration commit `2fb5abde72`, with dirty-state provenance explicitly
retained in the T3/T4 acceptance documents.

## Contents

- `multicast_report.tex`: integrated Topic 3/4 LaTeX report;
- `data/multicast_paired.csv`: 162 paired comparisons;
- `data/multicast_results.json`: 162 paired rows and 324 raw runs;
- `data/aggregate_*.csv`: generated summary tables;
- `data/worst_throughput_cases.csv`: ten lowest-throughput comparisons;
- `data/trace_replay_summary.csv`: compact T3/T4 accepted measurements;
- `data/trace_replay_provenance.txt`: trace hashes, semantics, and artifact paths;
- `bypass_g9.md`, `bypass_g10.md`: bypass cost and interaction gates;
- `figures/*.pdf`: vector figures used by LaTeX;
- `figures/*.png`: preview-friendly copies;
- `scripts/plot_multicast.py`: validation, aggregation, and plotting script.

## Rebuild figures

The existing `void` environment contains pandas, NumPy, and Matplotlib:

```sh
/mnt/einsia/aws02-nvme/einsia-shared/homes/kaisen/miniforge3/envs/void/bin/python \
  report/scripts/plot_multicast.py
```

The script rejects missing, non-finite, or duplicate paired results before it
updates the aggregate tables and figures.

## Build the PDF

```sh
cd report
pdflatex -interaction=nonstopmode -halt-on-error multicast_report.tex
pdflatex -interaction=nonstopmode -halt-on-error multicast_report.tex
```

## Interpretation boundary

The multicast data is a mechanism/regression study on one 4x4 topology and
one source placement. The bypass study uses synthetic Garnet traffic and does
not model physical timing closure or energy. The H100 trace is a real executed
collective microbenchmark with explicit 1/1024 byte/time scaling, not a
complete model trace. All-reduce is scalar-lane replay, not vector reduction
hardware. The report retains negative and neutral results.
