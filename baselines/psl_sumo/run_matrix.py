"""Run the full paper-aligned PSL matrix.

Protocol alignment with the manuscript (``paper/submitted/.../main.tex``):

* 3 lane configurations -- ``cross2`` / ``cross3`` / ``cross4``
  (two-way 4 / 6 / 8 lanes);
* 5 traffic-density levels -- ``lanes{L}_density{1..5}.rou.xml``, i.e. Table I
  (MinD / LowD / MedD / HigD / MaxD, 1:2:1 turning ratio);
* 30 seeds -- ``experiments/seeds_30.txt`` (81890-81919);
* 1000 s horizon, 0.1 s step, ``types.typ.xml`` kinematics.

That is 3 x 5 x 30 = 450 runs, the same count the manuscript claims.

Each run is three existing, independently re-runnable steps, invoked as
subprocesses so that this driver cannot drift from the code it drives:

    demand.py  ->  plan_scenario.py  ->  validate_plan.py

Everything is resumable at the *step* level: a run whose artifacts already exist
is skipped, so the driver can be interrupted and restarted freely.

Outputs (all under ``--out-root``, git-ignored and fully regenerable)::

    <out>/instances/cross{L}_trim/         3 graph models, built once
    <out>/demand/cross{L}_d{D}_s{S}/       per-seed demand + reference run
    <out>/runs/psl-cross{L}-d{D}-s{S}/     schedule, plan, summary, validation
    <out>/matrix_summary.csv               one row per run, rewritten as it goes
    <out>/matrix.log                       append-only driver log
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SEEDS_FILE = ROOT / "experiments" / "seeds_30.txt"
FIELDS = ["run_id", "lanes", "density", "seed", "w", "status",
          "n_requests", "n_coordinated", "n_served", "completion_fraction",
          "mean_entry_delay_s", "max_entry_delay_s", "scheduled_rate_veh_s",
          "demand_rate_veh_s", "makespan_s", "solver_wall_s", "cplex_statuses",
          "failed_windows", "validation_ok", "conflict_pairs", "violations"]


def read_seeds(path=SEEDS_FILE):
    out = []
    for line in Path(path).read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        out.append(int(line))
    return out


def run(cmd, log_path, timeout=None):
    """Run one subprocess, appending its output to ``log_path``."""
    with open(log_path, "a") as fh:
        fh.write("\n$ %s\n" % " ".join(str(c) for c in cmd))
        fh.flush()
        try:
            proc = subprocess.run([str(c) for c in cmd], stdout=fh,
                                  stderr=subprocess.STDOUT, timeout=timeout)
            return proc.returncode
        except subprocess.TimeoutExpired:
            fh.write("!! TIMEOUT after %s s\n" % timeout)
            return -1


def net_path(lanes):
    return ROOT / "scenarios" / "original" / ("cross%d.net.xml" % lanes)


def flow_path(lanes, density):
    return ROOT / "scenarios" / "flows" / ("lanes%d_density%d.rou.xml"
                                           % (lanes, density))


def typ_path():
    return ROOT / "scenarios" / "original" / "types.typ.xml"


def step_instance(out_root, lanes, log):
    inst = out_root / "instances" / ("cross%d_trim" % lanes)
    if (inst / "instance_report.json").exists():
        return inst, "cached"
    cmd = [sys.executable, HERE / "net_to_graph.py",
           "--net", net_path(lanes), "--trim-ends", "--out-dir", inst]
    return inst, ("ok" if run(cmd, log) == 0 else "fail")


def step_demand(out_root, lanes, density, seed, inst, log, source="flows"):
    dem = out_root / "demand" / ("cross%d_d%d_s%d" % (lanes, density, seed))
    if (dem / "request_manifest.json").exists():
        return dem, "cached"
    cmd = [sys.executable, HERE / "demand.py",
           "--net", net_path(lanes),
           "--rou", flow_path(lanes, density),
           "--typ", typ_path(),
           "--instance-dir", inst, "--out-dir", dem,
           "--end", "1000", "--step", "0.1", "--seed", seed,
           "--reference-source", source]
    return dem, ("ok" if run(cmd, log, timeout=900) == 0 else "fail")


def step_plan(out_root, lanes, density, seed, inst, dem, w, timeout, log):
    out = out_root / "runs" / ("psl-cross%d-d%d-s%d" % (lanes, density, seed))
    if (out / "summary.json").exists():
        return out, "cached"
    cmd = [sys.executable, HERE / "plan_scenario.py",
           "--instance-dir", inst, "--demand-dir", dem, "--run-dir", out,
           "--packer", "psl", "--w", w, "--window-size", "40",
           "--horizon", "1000"]
    return out, ("ok" if run(cmd, log, timeout=timeout) == 0 else "fail")


def step_validate(out_root, lanes, inst, out, w, log):
    val = out / "validation.json"
    if val.exists():
        return "cached"
    cmd = [sys.executable, HERE / "validate_plan.py",
           "--plan", out / "plan.csv",
           "--graph", inst / "graph.json", "--paths", inst / "paths.json",
           "--speed-model", "constant", "--w", w, "--out", val]
    return "ok" if run(cmd, log, timeout=3600) == 0 else "fail"


def collect(row, out_root, lanes, density, seed, w):
    run_id = "psl-cross%d-d%d-s%d" % (lanes, density, seed)
    out = out_root / "runs" / run_id
    base = {"run_id": run_id, "lanes": lanes, "density": density,
            "seed": seed, "w": w}
    summary = out / "summary.json"
    if not summary.exists():
        base["status"] = "missing"
        return base
    s = json.loads(summary.read_text())
    c = s.get("completion_within_horizon") or {}
    sat = s.get("saturation") or {}
    plan = s.get("planning") or {}
    base.update({
        "status": "ok",
        "n_requests": None,
        "n_coordinated": c.get("n_coordinated"),
        "n_served": c.get("n_served"),
        "completion_fraction": c.get("fraction"),
        "mean_entry_delay_s": c.get("mean_entry_delay_s"),
        "max_entry_delay_s": c.get("max_entry_delay_s"),
        "scheduled_rate_veh_s": sat.get("scheduled_rate_veh_s"),
        "demand_rate_veh_s": sat.get("demand_rate_veh_s"),
        "makespan_s": s.get("makespan_s"),
        "solver_wall_s": plan.get("total_solver_wall_s"),
        "cplex_statuses": json.dumps(plan.get("cplex_status_counts") or {}),
        "failed_windows": plan.get("failed_windows"),
    })
    rm = out / "run_manifest.json"
    if rm.exists():
        base["n_requests"] = json.loads(rm.read_text()).get("n_requests")
    val = out / "validation.json"
    if val.exists():
        v = json.loads(val.read_text())
        base["validation_ok"] = v.get("ok")
        base["conflict_pairs"] = (v.get("checks") or {}).get(
            "conflict_vertex_pairs_checked")
        base["violations"] = (v.get("checks") or {}).get("conflict_violations")
    return base


def one_run(args, lanes, density, seed, inst, log):
    """demand -> plan -> validate for a single matrix cell."""
    t0 = time.time()
    dem, st = step_demand(args.out_root, lanes, density, seed, inst, log,
                          args.reference_source)
    if st == "fail":
        return "demand_fail"
    out, st = step_plan(args.out_root, lanes, density, seed, inst, dem,
                        args.w, args.plan_timeout, log)
    if st == "fail":
        return "plan_fail"
    if not args.no_validate:
        step_validate(args.out_root, lanes, inst, out, args.w, log)
    return "done (%.0fs)" % (time.time() - t0)


def write_summary(args, cells):
    rows = [collect(None, args.out_root, L, D, S, args.w)
            for (L, D, S) in cells]
    path = args.out_root / "matrix_summary.csv"
    tmp = path.with_suffix(".csv.tmp")
    with open(tmp, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    tmp.replace(path)
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Run the full paper-aligned PSL matrix (3 x 5 x 30).",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-root", default="results/psl_matrix")
    ap.add_argument("--lanes", default="2,3,4",
                    help="comma-separated lane counts (default 2,3,4)")
    ap.add_argument("--densities", default="1,2,3,4,5")
    ap.add_argument("--seeds", default="",
                    help="override the seed list, e.g. 81890,81891")
    ap.add_argument("--max-seeds", type=int, default=0,
                    help="use only the first N seeds (smoke test)")
    ap.add_argument("--w", type=float, default=13.9,
                    help="conflict-point passage speed enforced by the adapter")
    ap.add_argument("--jobs", type=int, default=1,
                    help="parallel runs (each is independent)")
    ap.add_argument("--plan-timeout", type=float, default=3600.0)
    ap.add_argument("--reference-source", default="flows",
                    choices=("flows", "tripinfo", "fcd"),
                    help="flows = departures resampled from the flow definitions "
                         "(required for a meaningful density sweep: at MaxD the "
                         "86 m approaches cannot insert the demand)")
    ap.add_argument("--no-validate", action="store_true")
    ap.add_argument("--summary-every", type=int, default=10,
                    help="rewrite matrix_summary.csv every N finished runs")
    args = ap.parse_args(argv)

    args.out_root = Path(args.out_root)
    if not args.out_root.is_absolute():
        args.out_root = ROOT / args.out_root
    args.out_root.mkdir(parents=True, exist_ok=True)
    log = args.out_root / "matrix.log"

    lane_list = [int(x) for x in args.lanes.split(",") if x]
    dens_list = [int(x) for x in args.densities.split(",") if x]
    seeds = ([int(x) for x in args.seeds.split(",") if x] if args.seeds
             else read_seeds())
    if args.max_seeds:
        seeds = seeds[:args.max_seeds]

    instances = {}
    for L in lane_list:
        inst, st = step_instance(args.out_root, L, log)
        instances[L] = inst
        print("instance cross%d: %s" % (L, st), flush=True)

    cells = [(L, D, S) for L in lane_list for D in dens_list for S in seeds]
    total = len(cells)
    print("matrix: %d lanes x %d densities x %d seeds = %d runs, w=%.2f, jobs=%d"
          % (len(lane_list), len(dens_list), len(seeds), total, args.w,
             args.jobs), flush=True)

    done = 0
    t0 = time.time()
    if args.jobs <= 1:
        for (L, D, S) in cells:
            msg = one_run(args, L, D, S, instances[L], log)
            done += 1
            print("[%d/%d] cross%d d%d s%d -> %s  elapsed %.0fs"
                  % (done, total, L, D, S, msg, time.time() - t0), flush=True)
            if done % args.summary_every == 0:
                write_summary(args, cells)
    else:
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futs = {pool.submit(one_run, args, L, D, S, instances[L], log):
                    (L, D, S) for (L, D, S) in cells}
            for fut in as_completed(futs):
                L, D, S = futs[fut]
                done += 1
                try:
                    msg = fut.result()
                except Exception as exc:                     # noqa: BLE001
                    msg = "exception: %s" % exc
                print("[%d/%d] cross%d d%d s%d -> %s  elapsed %.0fs"
                      % (done, total, L, D, S, msg, time.time() - t0),
                      flush=True)
                if done % args.summary_every == 0:
                    write_summary(args, cells)

    rows = write_summary(args, cells)
    ok = [r for r in rows if r.get("status") == "ok"]
    print("\nfinished %d runs in %.0f s; %d with summary" %
          (done, time.time() - t0, len(ok)), flush=True)
    if ok:
        fr = [r["completion_fraction"] for r in ok
              if r["completion_fraction"] is not None]
        if fr:
            print("completion: mean %.4f  min %.4f  max %.4f"
                  % (sum(fr) / len(fr), min(fr), max(fr)), flush=True)
    print("summary -> %s" % (args.out_root / "matrix_summary.csv"), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

