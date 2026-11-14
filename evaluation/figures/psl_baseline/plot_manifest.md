# Plot manifest -- PSL baseline figures

Provenance for `psl_baseline`.

| artefact | source | note |
|---|---|---|
| `psl_traffic_summary.csv` | `results/psl_final/exec-d*/metrics.json`, `results/psl_exec/cross3-d*-none/metrics.json` | 1 run per (density, control) |
| `timeseries_all.csv` | same runs, `timeseries.csv` | 10 s logging, paper section III-B |
| `fig_timeloss.pdf/.png` | `timeseries_all.csv` | mean over the active fleet |
| `fig_speed.pdf/.png` | `timeseries_all.csv` | mean instantaneous speed |

Data class: **NEW_BASELINE_RAW** (no historical DSIP data).
Runs: cross3 only, seed 81890, 1000 s, 0.1 s step, w=13.9.
No box plot is drawn: one run per cell cannot form a distribution
(AGENTS.md 6.3).
