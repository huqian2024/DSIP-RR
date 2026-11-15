#!/usr/bin/env python3
"""Collect every DSIP-reconstruction variant into one comparison table.

Reads the run directories under ``--root`` (each with ``s3_report.json`` and,
where available, the matching ``*-s4.json`` from ``dynamics_aware.py``) and writes
``dsip_recon_variants.csv`` plus a markdown table to stdout.

The point is traceability: every row states its own adapter settings
(time scale, replan-active, density, seed) so no two configurations can be
confused in the paper.

    python3 evaluation/dsip_recon_report.py --root results --out evaluation/figures/dsip_recon
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FIELDS = ["variant", "arm", "replan_active", "time_scale", "seed",
          "n_trips", "time_loss_per_vehicle_mean_s",
          "proximity_events_lt1p5m", "emergency_braking_events",
          "n_planned_vehicles", "n_released_vehicles", "n_calls",
          "n_over_budget", "wall_p50_s",
          "rect_overlap_pairs", "peak_a_p50", "peak_a_p95", "peak_a_max", "peak_j_p50"]


def load_variant(run_dir, label, arm):
    rep_path = run_dir / "s3_report.json"
    if not rep_path.exists():
        return None
    rep = json.loads(rep_path.read_text())
    row = {"variant": label, "arm": arm,
           "replan_active": rep.get("replan_active"),
           "time_scale": rep.get("time_scale"), "seed": rep.get("seed")}
    for k in ("n_trips", "time_loss_per_vehicle_mean_s",
              "proximity_events_lt1p5m", "emergency_braking_events",
              "n_planned_vehicles", "n_released_vehicles", "n_calls",
              "n_over_budget", "wall_p50_s"):
        row[k] = rep.get(k)
    s4 = sorted(glob.glob(str(run_dir.parent / "dsip_s4"
                             / ("%s-s4.json" % run_dir.name))))
    if s4:
        d = json.loads(Path(s4[0]).read_text())
        row["rect_overlap_pairs"] = d.get("n_pairs_with_rectangle_overlap")
        kin = d.get("kinematics") or {}
        # kin[*] is the distribution over plans of that plan's peak value, so
        # "peak_a_p50" = the median plan's peak acceleration.
        for key, name, field in (("a_abs_max", "peak_a_p50", "p50"),
                                 ("a_abs_max", "peak_a_p95", "p95"),
                                 ("a_abs_max", "peak_a_max", "max"),
                                 ("j_abs_p50", "peak_j_p50", "p50")):
            cell = kin.get(key) or {}
            row[name] = cell.get(field)
    return row


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default="results")
    ap.add_argument("--out", default="evaluation/figures/dsip_recon")
    args = ap.parse_args(argv)

    root = Path(args.root)
    root = root if root.is_absolute() else ROOT / root
    out = Path(args.out)
    out = out if out.is_absolute() else ROOT / out
    out.mkdir(parents=True, exist_ok=True)

    rows = []
    # Uncontrolled baselines from the turning-ratio comparison.
    for rep in sorted(root.glob("dsip_compare/*-none-s*/sumo_command.txt")):
        run_dir = rep.parent
        label = run_dir.name.split("-none-")[0].replace("lanes3_", "")
        import re
        m = re.search(r"end (\d+)", rep.read_text() or "")
        row = {"variant": label, "arm": "none", "replan_active": None,
               "time_scale": None, "seed": int(run_dir.name.rsplit("s", 1)[1])}
        rows.append(row)

    # Adaptive arms.
    for rep in sorted(root.glob("dsip_*/s3_report.json")) + \
            sorted(root.glob("dsip_*/*/s3_report.json")):
        run_dir = rep.parent
        label = run_dir.name
        arm = "dsip"
        row = load_variant(run_dir, label, arm)
        if row:
            rows.append(row)

    with open(out / "dsip_recon_variants.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)

    hdr = ("| variant | replan-active | λ | trips | TL/veh | near | emg |"
           " rect ovl | a p50 | a max |")
    print(hdr)
    print("|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        if r.get("n_trips") is None:
            continue
        print("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            r["variant"], r.get("replan_active"), r.get("time_scale"),
            r.get("n_trips"), r.get("time_loss_per_vehicle_mean_s"),
            r.get("proximity_events_lt1p5m"),
            r.get("emergency_braking_events"), r.get("rect_overlap_pairs"),
            r.get("peak_a_p50"), r.get("peak_a_max")))
    print("\nwrote %s (%d rows)" % (out / "dsip_recon_variants.csv", len(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
