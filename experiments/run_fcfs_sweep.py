#!/usr/bin/env python3
"""Run the FCFS baseline over the full 15-flow x 30-seed matrix.

Scope
-----
5 densities x 3 lane counts (``scenarios/flows/lanes{L}_density{D}.rou.xml``)
x the 30 seeds the author supplied (``experiments/seeds_30.txt``, 81890..81919),
on the matching network:

    lanes2 -> scenarios/original/cross2.net.xml
    lanes3 -> scenarios/original/cross3.net.xml
    lanes4 -> scenarios/original/cross4.net.xml

The lanes2 -> cross2 mapping is **inferred from the net naming** (cross1 and
cross2 are both 2 lanes per approach); it is recorded as an open question in
docs/HANDOFF.md and must be confirmed by the author.

Everything is reproducible from the untouched submission assets: the net, the
demand file and the vehicle type are read from ``scenarios/``, the step length
is the command-line override ``--step-length 0.1``, and nothing is written back.

Usage
-----
    python3 experiments/run_fcfs_sweep.py                # all 450 runs
    python3 experiments/run_fcfs_sweep.py --workers 8
    python3 experiments/run_fcfs_sweep.py --lanes 3 --densities 1 2
    python3 experiments/run_fcfs_sweep.py --dry-run

Resumable: a run whose result JSON already exists is skipped, so an interrupted
sweep can simply be started again.
"""

import argparse
import csv
import json
import os
import sys
import time
import traceback
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from baselines.fcfs_sumo import control   # noqa: E402

OUT_DIR = ROOT / "results" / "fcfs_sweep"
RUN_DIR = ROOT / "results" / "fcfs_control"
SEED_FILE = ROOT / "experiments" / "seeds_30.txt"
NET_OF_LANES = {2: "cross2", 3: "cross3", 4: "cross4"}

FIELDS = ["lanes", "density", "net", "flows", "seed", "n_departed", "n_arrived",
          "mean_time_loss", "mean_trip_duration", "mean_speed",
          "n_collisions", "n_collision_records", "n_requests", "n_granted",
          "n_stopped", "n_forced", "wall_s", "status"]


def read_seeds(path=SEED_FILE):
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(int(line))
    return out


def result_path(lanes, density, seed):
    net = "scenarios/original/%s.net.xml" % NET_OF_LANES[lanes]
    flows = "scenarios/flows/lanes%d_density%d.rou.xml" % (lanes, density)
    tag = ("control_%s_%s_seed%d"
           % (Path(net).stem, Path(flows).stem, seed))
    return RUN_DIR / ("run_%s.json" % tag), net, flows, tag


def _row(lanes, density, net, flows, seed, d, wall, status):
    t = d.get("tripinfo") or {}
    return {"lanes": lanes, "density": density, "net": net, "flows": flows,
            "seed": seed,
            "n_departed": d.get("n_departed"),
            "n_arrived": d.get("n_arrived"),
            "mean_time_loss": t.get("mean_time_loss"),
            "mean_trip_duration": t.get("mean_trip_duration"),
            "mean_speed": t.get("mean_speed"),
            "n_collisions": d.get("n_collisions"),
            "n_collision_records": d.get("n_collision_records"),
            "n_requests": d.get("n_requests"),
            "n_granted": d.get("n_granted"),
            "n_stopped": d.get("n_stopped"),
            "n_forced": d.get("n_forced"),
            "wall_s": round(wall, 1), "status": status}


def one(task):
    lanes, density, seed, end_time = task
    path, net, flows, tag = result_path(lanes, density, seed)
    if path.exists():
        d = json.loads(path.read_text(encoding="utf-8"))
        return _row(lanes, density, net, flows, seed, d, 0.0, "skipped")

    t0 = time.time()
    try:
        d = control.run(end_time=end_time, seed=seed, control=True,
                        net=net, flows=flows, quiet=True)
        wall = time.time() - t0
        d["wall_s"] = round(wall, 1)
        path.write_text(json.dumps(d, indent=2), encoding="utf-8")
        return _row(lanes, density, net, flows, seed, d, wall, "ok")
    except Exception as exc:                                  # keep going
        wall = time.time() - t0
        print(traceback.format_exc(), flush=True)
        return {"lanes": lanes, "density": density, "net": net, "flows": flows,
                "seed": seed, "wall_s": round(wall, 1),
                "status": "error: %s" % exc}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lanes", type=int, nargs="+", default=[2, 3, 4])
    ap.add_argument("--densities", type=int, nargs="+", default=[1, 2, 3, 4, 5])
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--end", type=float, default=1000.0)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    seeds = read_seeds()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RUN_DIR.mkdir(parents=True, exist_ok=True)

    tasks = [(L, D, s, a.end)
             for L in a.lanes for D in a.densities for s in seeds]
    print("seeds      : %d  (%d..%d)" % (len(seeds), seeds[0], seeds[-1]))
    print("tasks      : %d  (%d lanes x %d densities x %d seeds)"
          % (len(tasks), len(a.lanes), len(a.densities), len(seeds)))
    print("workers    :", a.workers)
    print("end time   :", a.end, "s", flush=True)
    if a.dry_run:
        for t in tasks[:3]:
            print("  ", result_path(*t[:3])[1:3])
        print("   ...")
        return 0

    csv_path = OUT_DIR / "summary.csv"
    new_file = not csv_path.exists()
    started = time.time()
    done = 0
    with open(csv_path, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        if new_file:
            writer.writeheader()
            fh.flush()
        with Pool(a.workers) as pool:
            for row in pool.imap_unordered(one, tasks):
                done += 1
                writer.writerow({k: row.get(k) for k in FIELDS})
                fh.flush()
                if row.get("status") not in ("ok", "skipped"):
                    print("ERROR", row.get("flows"), row.get("seed"),
                          row.get("status"), flush=True)
                if done % 10 == 0 or done == len(tasks):
                    el = time.time() - started
                    eta = el / done * (len(tasks) - done)
                    print("[%d/%d] %5.1f%%  elapsed %5.0fs  eta %5.0fs"
                          % (done, len(tasks), 100.0 * done / len(tasks),
                             el, eta), flush=True)
    print("summary:", csv_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
