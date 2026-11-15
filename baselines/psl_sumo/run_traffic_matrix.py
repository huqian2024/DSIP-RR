#!/usr/bin/env python3
"""Run the **traffic-side** PSL matrix -- the comparison basis chosen by the author.

Basis decision (author, 2026-11-15, option A2) is recorded in
``docs/baselines/fairness-protocol.md`` section 7: the reported PSL baseline is the
SUMO execution level (the four metrics of ``main.tex`` section III-B), not the
planning-side completion fractions.  The startup gate therefore requires
3 nets x 5 densities x >=3 seeds, which is what this driver produces.

Why ``--w 7`` and not 13.9
--------------------------
``w`` only calibrates the adapter's occupancy model (``Li/w + Li/v``); the solver
binary always plans with its hard-coded 7.  The earlier 450-run planning matrix
used ``--w 13.9`` (the road speed limit) to lift planning-side completion, but the
measured execution shows that this schedule is much less executable: entry
deviation p50 37.4 / 41.2 / 41.1 s against 20.7 / 23.6 / 26.5 s in the upstream
default, and near-miss events 71 / 76 / 103 against 55 / 46 / 55 (cross3, d1/d3/d5,
seed 81890; ``docs/baselines/psl-traffic-matrix.md``).  Because the schedule assumes
cruise passage while the executor restarts vehicles from rest, the upstream default
is both the un-modified value and the more executable one, so the executed baseline
uses it.  ``--w 13.9`` remains available as a documented sensitivity, never mixed in.

Each cell is a chain of existing, independently re-runnable steps, invoked as
subprocesses so this driver cannot drift from the code it drives::

    plan_scenario.py   (w = 7, upstream default)
    validate_plan.py
    execute_plan.py --control psl     (schedule enforced with stop/resume)
    execute_plan.py --control none    (same net/rou/seed, uncontrolled reference)

Everything is resumable at the step level: an artifact that already exists is
skipped, so the driver can be interrupted and restarted freely.

Outputs (git-ignored, fully regenerable)::

    <out>/plans/psl-{net}-d{D}-s{S}/     schedule, plan, summary, validation
    <out>/psl-{net}-d{D}-s{S}/           metrics.json, timeseries.csv, tripinfo...
    <out>/none-{net}-d{D}-s{S}/          same, uncontrolled
    <out>/traffic_summary.csv            one row per (net, density, seed, control)
    <out>/traffic.log                    append-only driver log
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

NET_LANES = {"cross2": 2, "cross3": 3, "cross4": 4}


def net_path(net):
    return ROOT / "scenarios" / "original" / ("%s.net.xml" % net)


def typ_path():
    return ROOT / "scenarios" / "original" / "types.typ.xml"


def flow_path(lanes, density):
    return ROOT / "scenarios" / "flows" / ("lanes%d_density%d.rou.xml"
                                          % (lanes, density))


def run(cmd, log, timeout=1800):
    log.write("$ %s\n" % " ".join(str(c) for c in cmd))
    log.flush()
    t0 = time.time()
    try:
        p = subprocess.run([str(c) for c in cmd], capture_output=True,
                           text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        log.write("TIMEOUT after %.0f s\n" % (time.time() - t0))
        log.flush()
        return 124
    if p.returncode != 0:
        log.write((p.stdout or "")[-2000:] + (p.stderr or "")[-2000:] + "\n")
    log.write("rc=%d in %.1f s\n" % (p.returncode, time.time() - t0))
    log.flush()
    return p.returncode


def step_plan(out, args, net, density, seed, inst, dem, log):
    plan_dir = out / "plans" / ("psl-%s-d%d-s%d" % (net, density, seed))
    if (plan_dir / "summary.json").exists():
        return plan_dir, "cached"
    cmd = [sys.executable, HERE / "plan_scenario.py",
           "--instance-dir", inst, "--demand-dir", dem, "--run-dir", plan_dir,
           "--packer", "psl", "--w", args.w, "--window-size", "40",
           "--horizon", "1000"]
    return plan_dir, ("ok" if run(cmd, log, timeout=1800) == 0 else "fail")


def step_validate(plan_dir, inst, args, log):
    val = plan_dir / "validation.json"
    if val.exists():
        return "cached"
    cmd = [sys.executable, HERE / "validate_plan.py",
           "--plan", plan_dir / "plan.csv",
           "--graph", inst / "graph.json", "--paths", inst / "paths.json",
           "--speed-model", "constant", "--w", args.w, "--out", val]
    return "ok" if run(cmd, log, timeout=3600) == 0 else "fail"


def step_exec(out, args, net, lanes, density, seed, inst, plan_dir, control, log):
    run_dir = out / ("%s-%s-d%d-s%d" % (control, net, density, seed))
    if (run_dir / "metrics.json").exists():
        return run_dir, "cached"
    cmd = [sys.executable, HERE / "execute_plan.py",
           "--net", net_path(net), "--rou", flow_path(lanes, density),
           "--typ", typ_path(), "--instance-dir", inst,
           "--schedule", plan_dir / "schedule.csv", "--out-dir", run_dir,
           "--seed", seed, "--end", args.end,
           "--speed-model", "constant", "--control", control,
           "--mingap-factor", "0.5"]
    return run_dir, ("ok" if run(cmd, log, timeout=1800) == 0 else "fail")



FIELDS = ["net", "lanes", "density", "seed", "control", "w", "status",
          "time_loss_series_mean_s", "time_loss_per_vehicle_mean_s",
          "speed_series_mean_mps", "speed_per_vehicle_mean_mps",
          "travel_time_mean_s", "proximity_events_lt1p5m",
          "emergency_braking_events", "vehicles_inserted", "trips_completed",
          "entry_deviation_p50_s", "plan_completion_fraction",
          "plan_rate_veh_s"]


def collect(net, lanes, density, seed, control, w, run_dir, plan_dir):
    row = {"net": net, "lanes": lanes, "density": density, "seed": seed,
           "control": control, "w": w}
    mp = run_dir / "metrics.json"
    if not mp.exists():
        row["status"] = "missing"
        return row
    m = json.loads(mp.read_text())
    row.update({
        "status": "ok",
        "time_loss_series_mean_s": m["time_loss"]["series_mean"],
        "time_loss_per_vehicle_mean_s": m["time_loss"]["per_vehicle_mean"],
        "speed_series_mean_mps": m["average_speed"]["series_mean"],
        "speed_per_vehicle_mean_mps": m["average_speed"]["per_vehicle_mean"],
        "travel_time_mean_s": m["travel_time"]["per_vehicle_mean_s"],
        "proximity_events_lt1p5m": m["safety"]["collision_episodes"],
        "emergency_braking_events": m["safety"]["emergency_braking_events"],
        "vehicles_inserted": m["fleet"].get("n_inserted"),
        "trips_completed": m["fleet"].get("n_trips"),
        "entry_deviation_p50_s": (m.get("entry_deviation_s") or {}).get("p50"),
    })
    sp = plan_dir / "summary.json"
    if control == "psl" and sp.exists():
        s = json.loads(sp.read_text())
        row["plan_completion_fraction"] = (s.get("completion_within_horizon")
                                           or {}).get("fraction")
        row["plan_rate_veh_s"] = (s.get("saturation") or {}).get(
            "scheduled_rate_veh_s")
    return row


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out-root", default="results/psl_traffic")
    ap.add_argument("--plan-root", default="results/psl_matrix",
                    help="holds instances/{net}_trim and demand/{net}_d{D}_s{S};"
                         " reusing it keeps demand identical to the planning"
                         " matrix")
    ap.add_argument("--nets", default="cross2,cross3,cross4")
    ap.add_argument("--densities", default="1,2,3,4,5")
    ap.add_argument("--seeds", default="81890,81891,81892")
    ap.add_argument("--w", default="7",
                    help="passage speed of the adapter occupancy model; 7 is the"
                         " solver's own hard-coded value (see module docstring)")
    ap.add_argument("--end", default="1000")
    ap.add_argument("--no-validate", action="store_true")
    args = ap.parse_args(argv)

    out = Path(args.out_root)
    out = out if out.is_absolute() else ROOT / out
    plan_root = Path(args.plan_root)
    plan_root = plan_root if plan_root.is_absolute() else ROOT / plan_root
    out.mkdir(parents=True, exist_ok=True)

    nets = [x.strip() for x in args.nets.split(",") if x.strip()]
    dens = [int(x) for x in args.densities.split(",") if x.strip()]
    seeds = [int(x) for x in args.seeds.split(",") if x.strip()]
    total = len(nets) * len(dens) * len(seeds)

    log = open(out / "traffic.log", "a")
    log.write("\n=== %s  %d cells x 2 controls, w=%s, end=%s ===\n"
              % (time.strftime("%Y-%m-%d %H:%M:%S"), total, args.w, args.end))
    print("traffic matrix: %d nets x %d densities x %d seeds = %d plans,"
          " %d SUMO runs, w=%s" % (len(nets), len(dens), len(seeds), total,
                                   2 * total, args.w), flush=True)

    rows, i = [], 0
    for net in nets:
        lanes = NET_LANES[net]
        inst = plan_root / "instances" / ("%s_trim" % net)
        if not (inst / "paths.json").exists():
            sys.exit("missing instance: %s (run run_matrix.py first)" % inst)
        for d in dens:
            for s in seeds:
                i += 1
                dem = plan_root / "demand" / ("%s_d%d_s%d" % (net, d, s))
                if not (dem / "request_manifest.json").exists():
                    print("[%d/%d] %s d%d s%d: MISSING demand %s"
                          % (i, total, net, d, s, dem), flush=True)
                    log.write("missing demand %s\n" % dem)
                    continue
                t0 = time.time()
                plan_dir, st_plan = step_plan(out, args, net, d, s, inst, dem,
                                              log)
                st_val = "skipped"
                if not args.no_validate and st_plan != "fail":
                    st_val = step_validate(plan_dir, inst, args, log)
                got = {}
                for control in ("psl", "none"):
                    if st_plan == "fail":
                        got[control] = (out / ("%s-%s-d%d-s%d"
                                               % (control, net, d, s)), "skip")
                        continue
                    got[control] = step_exec(out, args, net, lanes, d, s, inst,
                                             plan_dir, control, log)
                for control in ("psl", "none"):
                    run_dir, _ = got[control]
                    rows.append(collect(net, lanes, d, s, control, args.w,
                                        run_dir, plan_dir))
                print("[%d/%d] %s d%d s%d: plan=%s val=%s psl=%s none=%s %.0fs"
                      % (i, total, net, d, s, st_plan, st_val,
                         got["psl"][1], got["none"][1], time.time() - t0),
                      flush=True)

    with open(out / "traffic_summary.csv", "w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=FIELDS)
        wr.writeheader()
        for r in rows:
            wr.writerow({k: r.get(k) for k in FIELDS})
    log.write("wrote %s (%d rows)\n" % (out / "traffic_summary.csv", len(rows)))
    log.close()
    print("\nwrote %s (%d rows)" % (out / "traffic_summary.csv", len(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

