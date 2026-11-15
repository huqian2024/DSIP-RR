# Plot manifest -- PSL baseline data

| artefact | source | note |
|---|---|---|
| `psl_traffic_by_seed.csv` | `None/*/metrics.json` | one row per (density, control, seed); plot from this file |
| `psl_traffic_summary.csv` | the same | mean/min/max over seeds |
| `timeseries_all.csv` | `*/timeseries.csv` | 10 s logging, paper section III-B |

Data class: **NEW_BASELINE_RAW** (no historical DSIP data).
Runs: cross2, cross3, cross4, seeds 81890,81891,81892, 1000 s, 0.1 s step, w=7.
Figures are generated only with `--figures` (author instruction:
prepare the data first).
