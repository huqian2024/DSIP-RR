#!/usr/bin/env python3
"""Collect the PSL traffic-side runs into one plottable table and two figures.

Inputs (produced by ``baselines/psl_sumo/execute_plan.py``):

* ``--psl-dir``  contains ``exec-d{D}/metrics.json`` + ``timeseries.csv`` for the
  schedule-controlled runs;
* ``--none-dir`` contains ``cross3-d{D}-s81890-none/metrics.json`` +
  ``timeseries.csv`` for the uncontrolled reference.

Outputs, all under ``--out-dir``:

* ``psl_traffic_summary.csv`` -- one row per (density, control), directly usable
  as a table or as input to a box plot once more seeds exist;
* ``timeseries_all.csv``      -- long format, one row per (density, control,
  logging step), for the paper-style temporal figures (Figs. 2-4 / as2-as4);
* ``fig_timeloss.pdf/.png``   -- mean time loss over the active fleet, 10 s
  sampling, one panel per density (main.tex section III-B);
* ``fig_speed.pdf/.png``      -- mean instantaneous speed, same sampling;
* ``plot_manifest.md``        -- provenance for every artefact above.

Metric definitions follow ``paper/submitted/.../main.tex`` section III-B:
"at each logging step ... computed over all vehicles currently active", with the
10 s logging interval used by Figs. 2-4.  ``time_loss.series_mean`` is the mean
of that time series; ``time_loss.per_vehicle_mean`` is the tripinfo mean.

Only ONE seed exists per cell, so nothing here is a distribution: no box plots,
no confidence bands, and every caption states the run count.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SUMMARY_FIELDS = ["lanes", "density", "seed", "control", "runs",
                  "time_loss_series_mean_s", "time_loss_per_vehicle_mean_s",
                  "speed_series_mean_mps", "speed_per_vehicle_mean_mps",
                  "travel_time_mean_s", "proximity_events_lt1p5m",
                  "emergency_braking_events", "vehicles_inserted",
                  "trips_completed", "entry_deviation_p50_s",
                  "plan_completion_fraction", "plan_rate_veh_s"]


def load_run(metrics_path, ts_path, density, control, seed=81890, lanes=3):
    m = json.loads(Path(metrics_path).read_text())
    row = {
        "lanes": lanes, "density": density, "seed": seed, "control": control,
        "runs": 1,
        "time_loss_series_mean_s": m["time_loss"]["series_mean"],
        "time_loss_per_vehicle_mean_s": m["time_loss"]["per_vehicle_mean"],
        "speed_series_mean_mps": m["average_speed"]["series_mean"],
        "speed_per_vehicle_mean_mps": m["average_speed"]["per_vehicle_mean"],
        "travel_time_mean_s": m["travel_time"]["per_vehicle_mean_s"],
        "proximity_events_lt1p5m": m["safety"]["collision_episodes"],
        "emergency_braking_events": m["safety"]["emergency_braking_events"],
        "vehicles_inserted": m["fleet"].get("n_inserted"),
        "trips_completed": m["fleet"].get("n_trips"),
        "entry_deviation_p50_s": m["entry_deviation_s"]["p50"],
    }
    ts = []
    if Path(ts_path).exists():
        for r in csv.DictReader(open(ts_path, newline="")):
            ts.append({"density": density, "control": control,
                       "time_s": r["time_s"],
                       "mean_time_loss_s": r["mean_time_loss_s"],
                       "mean_speed_mps": r["mean_speed_mps"],
                       "n_active": r["n_active"]})
    return row, ts


def make_figures(ts_rows, out_dir, metric, ylabel, fname, title_prefix):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    dens = sorted({r["density"] for r in ts_rows})
    fig, axes = plt.subplots(len(dens), 1, figsize=(3.5, 2.1 * len(dens)),
                             sharex=True, squeeze=False)
    styles = {"psl": dict(color="black", linestyle="-", linewidth=1.4,
                          label="PSL schedule + stop-and-go"),
              "none": dict(color="0.45", linestyle="--", linewidth=1.2,
                           label="uncontrolled")}
    for ax, d in zip(axes[:, 0], dens):
        for control in ("none", "psl"):
            rows = [r for r in ts_rows
                    if r["density"] == d and r["control"] == control]
            rows.sort(key=lambda r: float(r["time_s"]))
            xs = [float(r["time_s"]) for r in rows]
            ys = [float(r[metric]) if r[metric] not in ("", None) else float("nan")
                  for r in rows]
            if xs:
                ax.plot(xs, ys, **styles[control])
        ax.set_ylabel(ylabel)
        ax.set_title("density level %d" % d, fontsize=8)
        ax.tick_params(labelsize=7)
        ax.grid(True, alpha=0.3, linewidth=0.5)
    axes[-1, 0].set_xlabel("simulation time (s)")
    axes[0, 0].legend(fontsize=6, frameon=False, loc="upper left")
    fig.suptitle("%s, cross3 (6 lanes), 1 seed, 1 run per cell"
                 % title_prefix, fontsize=8)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    for ext in ("pdf", "png"):
        fig.savefig(out_dir / ("%s.%s" % (fname, ext)), dpi=300,
                    bbox_inches="tight")
    plt.close(fig)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--psl-dir", default="results/psl_final",
                    help="contains exec-d{D}/ from execute_plan.py (control=psl)")
    ap.add_argument("--none-dir", default="results/psl_exec",
                    help="contains cross3-d{D}-s81890-none/")
    ap.add_argument("--densities", default="1,3,5")
    ap.add_argument("--out-dir", default="evaluation/figures/psl_baseline")
    args = ap.parse_args(argv)

    psl_dir = ROOT / args.psl_dir if not Path(args.psl_dir).is_absolute() \
        else Path(args.psl_dir)
    none_dir = ROOT / args.none_dir if not Path(args.none_dir).is_absolute() \
        else Path(args.none_dir)
    out = ROOT / args.out_dir if not Path(args.out_dir).is_absolute() \
        else Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    rows, ts_all = [], []
    for d in [int(x) for x in args.densities.split(",") if x]:
        p = psl_dir / ("exec-d%d" % d)
        if (p / "metrics.json").exists():
            r, t = load_run(p / "metrics.json", p / "timeseries.csv", d, "psl")
            rows.append(r)
            ts_all += t
        else:
            print("missing %s" % (p / "metrics.json"))
        n = none_dir / ("cross3-d%d-s81890-none" % d)
        if (n / "metrics.json").exists():
            r, t = load_run(n / "metrics.json", n / "timeseries.csv", d, "none")
            rows.append(r)
            ts_all += t
        else:
            print("missing %s" % (n / "metrics.json"))

    with open(out / "psl_traffic_summary.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=SUMMARY_FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    if ts_all:
        with open(out / "timeseries_all.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(ts_all[0].keys()))
            w.writeheader()
            for r in ts_all:
                w.writerow(r)

    if ts_all:
        make_figures(ts_all, out, "mean_time_loss_s",
                     r"mean time loss (s)", "fig_timeloss",
                     "Average time loss")
        make_figures(ts_all, out, "mean_speed_mps",
                     r"mean speed (m/s)", "fig_speed", "Average speed")

    manifest = ["# Plot manifest -- PSL baseline figures", "",
                "Provenance for `%s`." % out.name, "",
                "| artefact | source | note |", "|---|---|---|",
                "| `psl_traffic_summary.csv` | `%s/exec-d*/metrics.json`, `%s/cross3-d*-none/metrics.json` | 1 run per (density, control) |"
                % (args.psl_dir, args.none_dir),
                "| `timeseries_all.csv` | same runs, `timeseries.csv` | 10 s logging, paper section III-B |",
                "| `fig_timeloss.pdf/.png` | `timeseries_all.csv` | mean over the active fleet |",
                "| `fig_speed.pdf/.png` | `timeseries_all.csv` | mean instantaneous speed |",
                "", "Data class: **NEW_BASELINE_RAW** (no historical DSIP data).",
                "Runs: cross3 only, seed 81890, 1000 s, 0.1 s step, w=13.9.",
                "No box plot is drawn: one run per cell cannot form a distribution",
                "(AGENTS.md 6.3).", ""]
    (out / "plot_manifest.md").write_text("\n".join(manifest))

    print("wrote %d summary rows, %d time-series rows to %s"
          % (len(rows), len(ts_all), out))
    for r in rows:
        print("  d%d %-4s TLseries=%-7s TLveh=%-7s v=%-6s prox=%-4s ebrake=%s"
              % (r["density"], r["control"], r["time_loss_series_mean_s"],
                 r["time_loss_per_vehicle_mean_s"], r["speed_series_mean_mps"],
                 r["proximity_events_lt1p5m"], r["emergency_braking_events"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
