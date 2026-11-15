#!/usr/bin/env python3
"""Assemble the DSIP turning-ratio experiment: 3 ratios x 2 arms x N seeds.

Two run layouts are produced by the reconstruction and both are accepted:

* seed 81890 (the first sweep) has its arms in fixed directories:
  ``results/dsip_replan_active`` (1:2:1), ``results/dsip_ra_r111``,
  ``results/dsip_ra_r122``, and the uncontrolled arms under
  ``results/dsip_compare/<flow>-none-s81890``;
* later seeds are produced by ``run_compare.py`` into
  ``results/dsip_cmp_s<seed>/<flow>-<arm>-s<seed>``.

The output is deliberately **per seed**: the whole point of this sweep is that a
single seed is not enough to state the relative effect.

    python3 evaluation/dsip_turning_ratio.py --out evaluation/figures/dsip_recon
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FLOW_OF_RATIO = {"1:2:1": "lanes3_density3",
                 "1:1:1": "lanes3_density3_r111",
                 "1:2:2": "lanes3_density3_r122"}

SEED_81890_DSIP = {"1:2:1": "results/dsip_replan_active",
                   "1:1:1": "results/dsip_ra_r111",
                   "1:2:2": "results/dsip_ra_r122"}

FIELDS = ["seed", "ratio", "arm", "n_trips", "time_loss_per_vehicle_mean_s",
          "mean_travel_time_s", "proximity_events_lt1p5m",
          "emergency_braking_events", "n_released_vehicles", "n_calls",
          "wall_p50_s", "dir"]


def uncontrolled_metrics(run_dir):
    """Same aggregates as the runner's, without importing torch/traci."""
    import xml.etree.ElementTree as ET
    loss, dur = [], []
    try:
        root = ET.parse(str(run_dir / "tripinfo.xml")).getroot()
        for ti in root.findall("tripinfo"):
            try:
                loss.append(float(ti.get("timeLoss")))
                dur.append(float(ti.get("duration")))
            except (TypeError, ValueError):
                continue
    except Exception:                                     # noqa: BLE001
        pass
    near, emg = 0, 0
    log = run_dir / "sumo.log"
    if log.exists():
        for line in log.read_text(errors="ignore").splitlines():
            if "collision with vehicle" in line and "gap=" in line:
                near += 1
            elif "emergency braking" in line:
                emg += 1
    n = len(loss)
    return {"n_trips": n,
            "time_loss_per_vehicle_mean_s": round(sum(loss) / n, 3) if n else None,
            "duration_mean_s": round(sum(dur) / n, 3) if n else None,
            "proximity_events_lt1p5m": near,
            "emergency_braking_events": emg}


def read_run(run_dir):
    rep = run_dir / "s3_report.json"
    out = {"dir": str(run_dir.relative_to(ROOT))}
    if rep.exists():
        d = json.loads(rep.read_text())
        out.update({"n_trips": d.get("n_trips"),
                    "time_loss_per_vehicle_mean_s":
                        d.get("time_loss_per_vehicle_mean_s"),
                    "mean_travel_time_s": d.get("duration_mean_s"),
                    "proximity_events_lt1p5m":
                        d.get("proximity_events_lt1p5m"),
                    "emergency_braking_events":
                        d.get("emergency_braking_events"),
                    "n_released_vehicles": d.get("n_released_vehicles"),
                    "n_calls": d.get("n_calls"),
                    "wall_p50_s": d.get("wall_p50_s")})
        return out
    m = uncontrolled_metrics(run_dir)
    out.update({"n_trips": m.get("n_trips"),
                "time_loss_per_vehicle_mean_s":
                    m.get("time_loss_per_vehicle_mean_s"),
                "mean_travel_time_s": m.get("duration_mean_s"),
                "proximity_events_lt1p5m": m.get("proximity_events_lt1p5m"),
                "emergency_braking_events": m.get("emergency_braking_events"),
                "n_released_vehicles": None, "n_calls": None,
                "wall_p50_s": None})
    return out



def collect(seeds):
    rows = []
    for seed in seeds:
        cmp_root = ROOT / "results" / ("dsip_cmp_s%d" % seed)
        for ratio, flow in FLOW_OF_RATIO.items():
            if seed == 81890 and ratio in SEED_81890_DSIP:
                d = ROOT / SEED_81890_DSIP[ratio]
            else:
                # run_compare names folders after the rou file stem, which keeps
                # the ".rou" suffix.
                d = cmp_root / ("%s.rou-dsip-s%d" % (flow, seed))
            if d.exists():
                r = read_run(d)
                r.update({"seed": seed, "ratio": ratio, "arm": "dsip"})
                if r.get("n_trips"):        # skip runs still in progress
                    rows.append(r)
            if seed == 81890:
                d = (ROOT / "results" / "dsip_compare"
                     / ("%s.rou-none-s%d" % (flow, seed)))
            else:
                d = cmp_root / ("%s.rou-none-s%d" % (flow, seed))
            if d.exists():
                r = read_run(d)
                r.update({"seed": seed, "ratio": ratio, "arm": "none"})
                if r.get("n_trips"):
                    rows.append(r)
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seeds", default="81890,81891,81892")
    ap.add_argument("--out", default="evaluation/figures/dsip_recon")
    args = ap.parse_args(argv)

    seeds = [int(x) for x in args.seeds.split(",") if x.strip()]
    out = Path(args.out)
    out = out if out.is_absolute() else ROOT / out
    out.mkdir(parents=True, exist_ok=True)

    rows = collect(seeds)
    with open(out / "turning_ratio_by_seed.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)

    rel_rows = []
    for seed in seeds:
        for arm in ("none", "dsip"):
            base = next((r for r in rows if r["seed"] == seed
                         and r["arm"] == arm and r["ratio"] == "1:2:1"), None)
            if not base or not base.get("time_loss_per_vehicle_mean_s"):
                continue
            for ratio in ("1:1:1", "1:2:2"):
                cur = next((r for r in rows if r["seed"] == seed
                            and r["arm"] == arm and r["ratio"] == ratio), None)
                if not cur or not cur.get("time_loss_per_vehicle_mean_s"):
                    continue
                rel_rows.append({
                    "seed": seed, "arm": arm, "ratio": ratio,
                    "d_time_loss_pct": round(
                        100 * (cur["time_loss_per_vehicle_mean_s"]
                               / base["time_loss_per_vehicle_mean_s"] - 1), 2),
                    "d_trips_pct": round(
                        100 * (cur["n_trips"] / base["n_trips"] - 1), 2),
                    "d_proximity_pct": round(
                        100 * (cur["proximity_events_lt1p5m"]
                               / max(base["proximity_events_lt1p5m"], 1) - 1),
                        2),
                })
    with open(out / "turning_ratio_relative.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["seed", "arm", "ratio",
                                           "d_time_loss_pct", "d_trips_pct",
                                           "d_proximity_pct"])
        w.writeheader()
        for r in rel_rows:
            w.writerow(r)

    print("| ratio | arm | seed | trips | TL/veh (s) | near | emg |")
    print("|---|---|---|---|---|---|---|")
    for r in sorted(rows, key=lambda x: (x["ratio"], x["arm"], x["seed"])):
        print("| %s | %s | %d | %s | %s | %s | %s |" % (
            r["ratio"], r["arm"], r["seed"], r.get("n_trips"),
            r.get("time_loss_per_vehicle_mean_s"),
            r.get("proximity_events_lt1p5m"),
            r.get("emergency_braking_events")))
    print("\n| ratio | arm | seed | dTL % | dtrips % | dprox % |")
    print("|---|---|---|---|---|---|")
    for r in rel_rows:
        print("| %s | %s | %d | %+.1f | %+.1f | %+.1f |" % (
            r["ratio"], r["arm"], r["seed"], r["d_time_loss_pct"],
            r["d_trips_pct"], r["d_proximity_pct"]))
    print("\nwrote %s (%d rows)" % (out / "turning_ratio_by_seed.csv",
                                    len(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
