#!/usr/bin/env python3
"""Collect the PSL traffic-side runs into comparison-ready tables.

Reads the runs produced by ``baselines/psl_sumo/{demand,plan_scenario,
execute_plan}.py`` and writes, under ``--out-dir``:

* ``psl_traffic_by_seed.csv`` -- one row per (density, control, seed).  This is
  the file a box plot or a paired test needs; never pre-averaged.
* ``psl_traffic_summary.csv`` -- one row per (density, control) with
  mean / min / max over seeds and the seed count.
* ``timeseries_all.csv``      -- long format, one row per (density, control,
  seed, logging step), for the paper-style temporal figures.

Figures are **off by default** (author instruction 2026-11-14: prepare the data
first).  Pass ``--figures`` to also write ``fig_timeloss`` / ``fig_speed`` as
``.pdf`` + ``.png``; that path is the only one that needs matplotlib.

Metric definitions follow ``paper/submitted/.../main.tex`` section III-B: the
mean over the active fleet at each logging step, with the paper's 10 s interval.
``time_loss_series_mean_s`` is the mean of that series; the ``per_vehicle``
columns are the tripinfo means.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

BY_SEED_FIELDS = [
    "lanes", "density", "control", "seed",
    "time_loss_series_mean_s", "time_loss_per_vehicle_mean_s",
    "speed_series_mean_mps", "speed_per_vehicle_mean_mps",
    "travel_time_mean_s", "proximity_events_lt1p5m",
    "emergency_braking_events", "vehicles_inserted", "trips_completed",
    "entry_deviation_p50_s", "plan_completion_fraction", "plan_rate_veh_s",
]
SUMMARY_FIELDS = ["lanes", "density", "control", "n_seeds"]
for _m in BY_SEED_FIELDS[4:]:
    SUMMARY_FIELDS += [_m + "_mean", _m + "_min", _m + "_max"]


def load_cell(metrics_path, ts_path, lanes, density, control, seed,
              plan_summary=None):
    m = json.loads(Path(metrics_path).read_text())
    row = {
        "lanes": lanes, "density": density, "control": control, "seed": seed,
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
        "plan_completion_fraction": None, "plan_rate_veh_s": None,
    }
    if plan_summary and Path(plan_summary).exists():
        p = json.loads(Path(plan_summary).read_text())
        row["plan_completion_fraction"] = (p.get("completion_within_horizon")
                                           or {}).get("fraction")
        row["plan_rate_veh_s"] = (p.get("saturation") or {}).get(
            "scheduled_rate_veh_s")
    ts = []
    if Path(ts_path).exists():
        for r in csv.DictReader(open(ts_path, newline="")):
            ts.append({"lanes": lanes, "density": density, "control": control,
                       "seed": seed, "time_s": r["time_s"],
                       "mean_time_loss_s": r["mean_time_loss_s"],
                       "mean_speed_mps": r["mean_speed_mps"],
                       "n_active": r["n_active"]})
    return row, ts


NET_LANES = {"cross2": 2, "cross3": 3, "cross4": 4}


def iter_cells(base, nets, args):
    """Yield (net, lanes, density, seed, plan_summary, {control: folder}).

    ``nets`` empty reproduces the original pilot layout (``exec-d1-s81890``);
    otherwise the net-aware layout written by ``baselines/psl_sumo/
    run_traffic_matrix.py`` (``psl-cross3-d1-s81890`` / ``plans/psl-...``).
    """
    dens = [int(x) for x in args.densities.split(",") if x.strip()]
    seeds = [int(x) for x in args.seeds.split(",") if x.strip()]
    if not nets:
        for d in dens:
            for s in seeds:
                yield (None, args.lanes, d, s,
                       base / ("psl-d%d-s%d" % (d, s)) / "summary.json",
                       {"psl": base / ("exec-d%d-s%d" % (d, s)),
                        "none": base / ("none-d%d-s%d" % (d, s))})
        return
    for net in nets:
        lanes = NET_LANES[net]
        for d in dens:
            for s in seeds:
                stem = "%s-d%d-s%d" % (net, d, s)
                yield (net, lanes, d, s,
                       base / "plans" / ("psl-" + stem) / "summary.json",
                       {"psl": base / ("psl-" + stem),
                        "none": base / ("none-" + stem)})


def summarise(by_seed):
    groups = {}
    for r in by_seed:
        groups.setdefault((r["lanes"], r["density"], r["control"]), []).append(r)
    out = []
    for key in sorted(groups):
        rows = groups[key]
        rec = {"lanes": key[0], "density": key[1], "control": key[2],
               "n_seeds": len(rows)}
        for metric in BY_SEED_FIELDS[4:]:
            vals = [r[metric] for r in rows if r[metric] is not None]
            if vals:
                rec[metric + "_mean"] = round(statistics.fmean(vals), 4)
                rec[metric + "_min"] = round(min(vals), 4)
                rec[metric + "_max"] = round(max(vals), 4)
            else:
                rec[metric + "_mean"] = rec[metric + "_min"] = \
                    rec[metric + "_max"] = None
        out.append(rec)
    return out


def make_figures(ts_rows, out_dir, metric, ylabel, fname, title_prefix):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    dens = sorted({r["density"] for r in ts_rows})
    seeds = sorted({r["seed"] for r in ts_rows})
    fig, axes = plt.subplots(len(dens), 1, figsize=(3.5, 2.1 * len(dens)),
                             sharex=True, squeeze=False)
    styles = {"psl": dict(color="black", linestyle="-", linewidth=1.2),
              "none": dict(color="0.55", linestyle="--", linewidth=1.0)}
    for ax, d in zip(axes[:, 0], dens):
        for control in ("none", "psl"):
            label = ("PSL schedule + stop-and-go" if control == "psl"
                     else "uncontrolled")
            for s in seeds:
                rows = [r for r in ts_rows if r["density"] == d
                        and r["control"] == control and r["seed"] == s]
                rows.sort(key=lambda r: float(r["time_s"]))
                if rows:
                    ax.plot([float(r["time_s"]) for r in rows],
                            [float(r[metric]) for r in rows],
                            label=label if s == seeds[0] else None,
                            **styles[control])
        ax.set_ylabel(ylabel)
        ax.set_title("density level %d" % d, fontsize=8)
        ax.tick_params(labelsize=7)
        ax.grid(True, alpha=0.3, linewidth=0.5)
    axes[-1, 0].set_xlabel("simulation time (s)")
    axes[0, 0].legend(fontsize=6, frameon=False, loc="upper left")
    fig.suptitle("%s, cross3 (6 lanes), %d seeds"
                 % (title_prefix, len(seeds)), fontsize=8)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    for ext in ("pdf", "png"):
        fig.savefig(out_dir / ("%s.%s" % (fname, ext)), dpi=300,
                    bbox_inches="tight")
    plt.close(fig)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run-root", default=None,
                    help="root holding the run folders; defaults to"
                         " results/psl_traffic when --nets is given and to"
                         " results/psl_tr (pilot layout) otherwise")
    ap.add_argument("--densities", default="1,3,5")
    ap.add_argument("--seeds", default="81890,81891,81892,81893,81894")
    ap.add_argument("--lanes", type=int, default=3)
    ap.add_argument("--nets", default="",
                    help="comma-separated nets (cross2,cross3,cross4); enables the"
                         " net-aware layout written by"
                         " baselines/psl_sumo/run_traffic_matrix.py")
    ap.add_argument("--w", default="",
                    help="passage speed w of the executed schedules, recorded in"
                         " the plot manifest")
    ap.add_argument("--out-dir", default="evaluation/figures/psl_baseline")
    ap.add_argument("--figures", action="store_true",
                    help="also render the two temporal figures (needs matplotlib)")
    args = ap.parse_args(argv)

    base = Path(args.run_root or ("results/psl_traffic"
                                  if args.nets.strip() else "results/psl_tr"))
    if not base.is_absolute():
        base = ROOT / base
    out = Path(args.out_dir)
    if not out.is_absolute():
        out = ROOT / out
    out.mkdir(parents=True, exist_ok=True)

    by_seed, ts_all = [], []
    nets = [x.strip() for x in args.nets.split(",") if x.strip()]
    for net, lanes, d, s, plan, folders in iter_cells(base, nets, args):
        for control in ("psl", "none"):
            folder = folders[control]
            mp = folder / "metrics.json"
            if not mp.exists():
                continue
            row, ts = load_cell(mp, folder / "timeseries.csv", lanes, d,
                                control, s, plan if control == "psl" else None)
            if net:
                row["net"] = net
            by_seed.append(row)
            ts_all += ts

    summary = summarise(by_seed)
    with open(out / "psl_traffic_by_seed.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=BY_SEED_FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in by_seed:
            w.writerow(r)
    with open(out / "psl_traffic_summary.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=SUMMARY_FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in summary:
            w.writerow(r)
    if ts_all:
        with open(out / "timeseries_all.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(ts_all[0].keys()))
            w.writeheader()
            for r in ts_all:
                w.writerow(r)
    if args.figures and ts_all:
        make_figures(ts_all, out, "mean_time_loss_s", "mean time loss (s)",
                     "fig_timeloss", "Average time loss")
        make_figures(ts_all, out, "mean_speed_mps", "mean speed (m/s)",
                     "fig_speed", "Average speed")

    lines = ["# Plot manifest -- PSL baseline data", "",
             "| artefact | source | note |", "|---|---|---|",
             "| `psl_traffic_by_seed.csv` | `%s/*/metrics.json` | one row per "
             "(density, control, seed); plot from this file |" % args.run_root,
             "| `psl_traffic_summary.csv` | the same | mean/min/max over seeds |",
             "| `timeseries_all.csv` | `*/timeseries.csv` | 10 s logging, "
             "paper section III-B |", ""]
    if args.figures:
        lines += ["| `fig_timeloss.pdf/.png` | `timeseries_all.csv` | one line "
                  "per seed |",
                  "| `fig_speed.pdf/.png` | `timeseries_all.csv` | one line "
                  "per seed |", ""]
    lines += ["Data class: **NEW_BASELINE_RAW** (no historical DSIP data).",
              "Runs: %s, seeds %s, 1000 s, 0.1 s step%s."
              % ((", ".join(nets) if nets else "cross3 only"), args.seeds,
                 (", w=%s" % args.w) if args.w else ""),
              "Figures are generated only with `--figures` (author instruction:",
              "prepare the data first).", ""]
    (out / "plot_manifest.md").write_text("\n".join(lines))

    print("by-seed rows %d, summary rows %d, time-series rows %d -> %s"
          % (len(by_seed), len(summary), len(ts_all), out))
    for r in summary:
        print("  d%d %-4s n=%d TLser=%.2f [%.2f,%.2f] TLveh=%.2f v=%.2f prox=%.1f"
              % (r["density"], r["control"], r["n_seeds"],
                 r["time_loss_series_mean_s_mean"] or 0,
                 r["time_loss_series_mean_s_min"] or 0,
                 r["time_loss_series_mean_s_max"] or 0,
                 r["time_loss_per_vehicle_mean_s_mean"] or 0,
                 r["speed_series_mean_mps_mean"] or 0,
                 r["proximity_events_lt1p5m_mean"] or 0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

