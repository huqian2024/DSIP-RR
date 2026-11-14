"""Full-horizon rolling-batch PSL planning for one DSIP-RR scenario.

Why this module exists
----------------------
``run_psl.py`` plans one small batch (5-25 vehicles) taken from a 40 s window.
Our experiments need: 3 lane configurations × 5 densities × 30 seeds × 1000 s,
i.e. thousands of vehicles per scenario.  The upstream binary is a *batch*
planner (``PBS.cpp`` plans a fixed agent set once), so the only faithful way to
cover the full horizon is to plan **consecutive batches in arrival order** and
carry the conflict-point reservations across batches.

What it produces
----------------
A conflict-free per-vehicle **schedule** (entry time, exit time, occupied
intervals) for the whole 1000 s demand.  ``output_kind = "schedule_only"``:
this is a planning-side artefact.  It is NOT a SUMO traffic simulation and the
files here must not be reported as throughput / travel time / collision counts.

Two speed models (see ``kinematics.py``)
----------------------------------------
``--speed-mode kinematic`` (default) re-times PSL's *ordering* for our scenario
kinematics: a held vehicle enters from rest and accelerates at ``accel = 1.0``
up to ``maxSpeed = 13.9``.  This is the execution the FCFS baseline also gets.
``--speed-mode psl`` keeps upstream's constant-speed model with the solver's own
``v`` (its LP bound is 15 m/s), i.e. PSL's own opinion of the plan.
"""

from __future__ import annotations

import argparse
import bisect
import csv
import json
import shutil
import subprocess
import time
from pathlib import Path

import kinematics as kin

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BINARY = ROOT / "third_party" / "_local" / "AIM-PSL" / "PBS-SIPP-ver2" / "AIMPBS"
GRAPH_NAME = "intro_graph_3.json"
PAIR_NAME = "pairDistance_3.json"
ARRIVAL_NAME = "vehicleArrival.json"
OUTPUT_NAME = "output.txt"
PSL_COLUMNS = ["in_point", "out_point", "length", "earliest_arrival", "in_time",
               "out_time_head", "out_time_tail", "time_spend", "speed",
               "importance"]
EPS = 1e-9


def sha256(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def conflict_groups(graph):
    """vertex name -> group id.

    After ``net_to_graph.py`` collapsed the approach/exit points, vertices that
    share a physical point share ``pos`` exactly, so grouping on the rounded
    position reproduces the solver's ``vertex_conflicts`` partition without
    re-reading the private ``_group`` field.
    """
    by_pos = {}
    for v in graph["vertices"]:
        key = (round(v["pos"][0], 2), round(v["pos"][1], 2))
        by_pos.setdefault(key, []).append(v["name"])
    gid = {}
    for i, key in enumerate(sorted(by_pos)):
        for name in by_pos[key]:
            gid[name] = i
    return gid


class ReservationGuard:
    """Monotone time-window reservations over conflict groups.

    ``commit`` is only called for vehicles whose release time has been decided,
    so the table is an append-mostly structure.  ``earliest`` advances a
    candidate release time until every conflict point on the path is free.
    """

    def __init__(self, gid, paths_by_prefix, mode, accel, vmax, w=kin.W):
        self.w = w
        self.gid = gid
        self.paths = paths_by_prefix
        self.mode = mode
        self.accel = accel
        self.vmax = vmax
        self._res = {}          # group id -> list of (t0, t1)
        self._width = {}        # group id -> max interval width seen (pruning)
        self.n_checks = 0
        self.n_pushes = 0

    # -- internal -------------------------------------------------------
    def _windows(self, prefix, release, speed):
        p = self.paths[prefix]
        passage = kin.li(p["move"])
        out = []
        for name, off in zip(p["vertices"], p["offsets"]):
            t0, t1 = kin.occupancy(release, off, passage, mode=self.mode,
                                   speed=speed, accel=self.accel, vmax=self.vmax,
                                   w=self.w)
            out.append((self.gid[name], t0, t1))
        return out

    def _conflict_end(self, windows):
        """Latest end among intervals that overlap any of ``windows``."""
        worst = None
        for g, t0, t1 in windows:
            lst = self._res.get(g)
            if not lst:
                continue
            lo = bisect.bisect_left(lst, (t0 - self._width.get(g, 0.0),))
            lo = max(0, lo - 1)
            for i in range(lo, len(lst)):
                s0, s1 = lst[i]
                if s0 >= t1:
                    break
                if s0 < t1 - EPS and t0 < s1 - EPS:
                    if worst is None or s1 > worst:
                        worst = s1
        return worst

    # -- public ---------------------------------------------------------
    def earliest(self, prefix, release_min, speed, max_iter=20000):
        """Smallest release >= ``release_min`` that clears every conflict point."""
        cand = release_min
        for _ in range(max_iter):
            w = self._windows(prefix, cand, speed)
            self.n_checks += 1
            end = self._conflict_end(w)
            if end is None:
                return cand, w
            cand = max(cand, end + 1e-6)
        raise RuntimeError("reservation guard did not converge for %s" % prefix)

    def commit(self, windows):
        for g, t0, t1 in windows:
            lst = self._res.setdefault(g, [])
            bisect.insort(lst, (t0, t1))
            self._width[g] = max(self._width.get(g, 0.0), t1 - t0)
        self.n_pushes += 1

    def prune(self, before):
        for g, lst in self._res.items():
            k = bisect.bisect_left(lst, (before,))
            if k:
                del lst[:k]


def run_psl_batch(run_dir, binary, batch, timeout):
    """Plan one batch. ``batch`` = list of request dicts (already ordered).

    Returns (rows, wall_s, reported_s, status); ``rows[i]`` belongs to
    ``batch[i]`` because upstream writes ``plan[]`` in agent order.
    """
    payload = {}
    for i, r in enumerate(batch):
        payload[str(i)] = {"id": i, "importance": 1,
                           "trajectory": r["trajectory"],
                           "lane": r["lane"],
                           "arrivalTime": r["arrival_freeflow"]}
    (run_dir / ARRIVAL_NAME).write_text(json.dumps(payload, indent=1))
    cmd = [str(binary.resolve()), str(len(batch) - 1)]
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, cwd=str(run_dir), capture_output=True, text=True,
                          timeout=timeout)
    wall = time.perf_counter() - t0
    if proc.returncode != 0:
        raise SystemExit("AIMPBS failed rc=%d\n%s" % (proc.returncode, proc.stderr))
    reported = None
    for line in proc.stdout.strip().splitlines():
        try:
            reported = float(line.strip())
        except ValueError:
            continue
    rows = []
    with open(run_dir / OUTPUT_NAME) as fh:
        fh.readline()
        for rec in csv.reader(fh, delimiter=";"):
            if not rec or len(rec) < len(PSL_COLUMNS):
                continue
            rec = [c.strip() for c in rec]
            row = dict(zip(PSL_COLUMNS, rec))
            for k in PSL_COLUMNS[2:9]:
                row[k] = float(row[k])
            rows.append(row)
    status = "optimal"
    sol = run_dir / "solution"
    if sol.exists():
        for line in sol.read_text(errors="replace").splitlines():
            if "solutionStatusString" in line:
                status = line.split("=")[-1].strip().strip('">/ ')
                break
    return rows, wall, reported, status


def solve_window(run, binary, planned, timeout, stats):
    """Plan a window, degrading gracefully.

    The upstream binary **segfaults** when PBS fails to place an agent:
    ``PTNode::writeToFile`` (``PTNode.cpp:9-30``) indexes ``plan[i][0]`` with no
    empty-plan guard, and there is no ``no solution`` return path before the
    write.  A single infeasible window would therefore abort a whole scenario, so
    the adapter retries with progressively weaker requests and records every
    degradation instead of hiding it.
    """
    attempts = []
    for label, reqs in (("backlog", planned),
                        ("plain_eta", [{**q, "arrival_freeflow": q["eta_request"]}
                                       for q in planned])):
        try:
            rows, wall, reported, status = run_psl_batch(run, binary, reqs, timeout)
            if len(rows) == len(reqs):
                stats.setdefault(label, 0)
                stats[label] += 1
                return rows, wall, reported, status, label
            attempts.append("%s: %d/%d rows" % (label, len(rows), len(reqs)))
        except SystemExit as exc:
            attempts.append("%s: %s" % (label, str(exc).splitlines()[0]))
    stats["failed_windows"] = stats.get("failed_windows", 0) + 1
    stats.setdefault("failure_notes", []).append("; ".join(attempts)[:400])
    return None, 0.0, None, "solver_crash", "failed"


def _completion(coord, horizon):
    """How much of the coordinated demand the schedule clears inside ``horizon``.

    This is the metric that makes the saturation finding comparable and
    quotable: the schedule itself always finishes eventually, so what matters is
    the fraction that fits the protocol's 1000 s window.
    """
    if not coord:
        return None
    served = [r for r in coord if r["in_time"] <= horizon]
    delays = [r["in_time"] - r["earliest_arrival"] for r in served]
    return {
        "horizon_s": horizon,
        "n_coordinated": len(coord),
        "n_served": len(served),
        "fraction": round(len(served) / len(coord), 4),
        "mean_entry_delay_s": round(sum(delays) / len(delays), 3) if delays else None,
        "max_entry_delay_s": round(max(delays), 3) if delays else None,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Full-horizon rolling-batch PSL planning for one scenario.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--instance-dir", required=True)
    ap.add_argument("--demand-dir", required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--binary", default=str(DEFAULT_BINARY))
    ap.add_argument("--batch-size", type=int, default=20,
                    help="kept for compatibility; the moving-frame scheduler "
                         "commits the whole window")
    ap.add_argument("--window-size", type=int, default=40,
                    help="vehicles planned jointly per round")
    ap.add_argument("--speed-mode", choices=("limit", "psl", "kinematic"),
                    default="limit",
                    help="limit = cruise through the stop line at the scenario "
                         "speed cap (default, stop-free passage assumed); "
                         "psl = upstream's own v (LP bound 15 m/s); "
                         "kinematic = held at the line, accelerating from rest")
    ap.add_argument("--accel", type=float, default=kin.ACCEL)
    ap.add_argument("--vmax", type=float, default=kin.V_LIMIT)
    ap.add_argument("--rebase", choices=("window_start", "frontier", "none"),
                    default="window_start",
                    help="time origin for the solver request.  window_start "
                         "(default) preserves the relative arrival order while "
                         "keeping the numbers small; frontier forces every "
                         "vehicle to start after the last committed entry; "
                         "none passes absolute arrival times")
    ap.add_argument("--packer", choices=("psl", "greedy"), default="psl",
                    help="psl = use the solver's own ordering (the baseline); "
                         "greedy = diagnostic control: no solver, insert in ETA "
                         "order through the same reservation guard")
    ap.add_argument("--w", type=float, default=kin.W,
                    help="conflict-point passage speed.  The solver hard-codes 7; "
                         "any other value is a DIAGNOSTIC surrogate, not PSL")
    ap.add_argument("--horizon", type=float, default=1000.0,
                    help="demand horizon (s).  The paper protocol is 1000 s; "
                         "completion is measured against it")
    ap.add_argument("--timeout", type=float, default=600.0)
    ap.add_argument("--max-batches", type=int, default=0,
                    help="stop after N batches (0 = all); for smoke tests")
    args = ap.parse_args(argv)

    inst, dem, run = Path(args.instance_dir), Path(args.demand_dir), Path(args.run_dir)
    run.mkdir(parents=True, exist_ok=True)
    binary = Path(args.binary)
    if not binary.exists():
        raise SystemExit("PSL binary not found: %s" % binary)

    graph = json.loads((inst / "graph.json").read_text())
    paths = json.loads((inst / "paths.json").read_text())["paths"]
    paths_by_prefix = {p["prefix"]: p for p in paths}
    gid = conflict_groups(graph)
    manifest_in = json.loads((dem / "request_manifest.json").read_text())
    requests = manifest_in["requests"]
    # Movements with no real crossing point (right turns in a four-leg layout)
    # cannot be planned by a conflict-resolving solver: they have no conflict
    # point to be placed at.  They are scheduled at their free-flow arrival and
    # reported separately; nothing about them needs coordination.
    free_prefixes = {p["prefix"] for p in paths if p.get("conflict_free")}
    free_reqs = [r for r in requests if r["prefix"] in free_prefixes]
    requests = [r for r in requests if r["prefix"] not in free_prefixes]
    for name, src in ((GRAPH_NAME, inst / "graph.json"),
                      (PAIR_NAME, inst / "pairDistance.json")):
        shutil.copy2(src, run / name)

    model = "accelerating" if args.speed_mode == "kinematic" else "constant"
    guard = ReservationGuard(gid, paths_by_prefix, model, args.accel, args.vmax,
                             w=args.w)

    # Receding horizon over *overlapping* windows: each round plans
    # ``window_size`` pending vehicles jointly and commits only the earliest
    # ``batch_size`` of them.  A plain non-overlapping batch decomposition makes
    # every batch boundary a hard serialisation point (the guard then has to
    # push the next batch behind the previous one), which inflates delay for
    # reasons that have nothing to do with PSL.
    pending = list(requests)
    schedule, per_batch, total_wall = [], [], 0.0
    rounds = 0
    # Per-approach backlog: the latest entry time already committed on each
    # approach.  Without feeding this back, every window is planned against
    # arrival times that are stale by the accumulated delay, so the guard has to
    # push the whole window behind the previous one and the delay compounds
    # across rounds for no algorithmic reason.
    # Sequential batch planning in a *moving time frame*.
    #
    # ``frontier`` is the last entry time already committed.  Every window is
    # requested in local time (``arrivalTime = max(0, ETA - frontier)``) and the
    # solved times are shifted back afterwards.  Two reasons:
    #   * the guard can then only push by genuine cross-window conflicts, not by
    #     the "ratchet" where each window is re-requested at stale absolute ETAs
    #     and lands behind the previous one (measured: 2.7x makespan inflation);
    #   * the upstream solver becomes ~10x slower when ``arrivalTime`` is a large
    #     absolute value, so keeping the numbers small is a real requirement.
    frontier = 0.0
    solve_stats = {}
    while pending:
        if args.max_batches and rounds >= args.max_batches:
            break
        window = pending[:args.window_size]
        frontier_before = frontier
        if args.packer == "greedy":
            # Diagnostic control: no solver at all.  Each vehicle is inserted at
            # its own free-flow arrival through the *same* reservation guard, so
            # a throughput gap against ``packer=psl`` measures what PSL's
            # ordering costs, not what the conflict model costs.
            rows, wall, reported, status, attempt = [], 0.0, None, "no_solver", "greedy"
            for r in window:
                p = paths_by_prefix[r["prefix"]]
                rows.append({"in_time": r["arrival_freeflow"], "speed": args.vmax,
                             "length": p["length"], "in_point": p["vertices"][0],
                             "out_point": p["vertices"][-1]})
            origin = 0.0
        else:
            if args.rebase == "frontier":
                origin = frontier
            elif args.rebase == "none":
                origin = 0.0
            else:
                origin = window[0]["arrival_freeflow"]
        planned = []
        for r in window:
            q = dict(r)
            q["eta_request"] = r["arrival_freeflow"]
            q["arrival_freeflow"] = max(0.0, r["arrival_freeflow"] - origin)
            planned.append(q)
        if args.packer != "greedy":
            rows, wall, reported, status, attempt = solve_window(
                run, binary, planned, args.timeout, solve_stats)
            total_wall += wall
        if rows is None:
            # Unschedulable for the upstream solver.  Skip it and keep the
            # scenario alive; the count is reported in summary.json.
            pending = pending[len(window):]
            per_batch.append({"round": rounds, "window": len(window),
                              "committed": 0, "wall_s": round(wall, 6),
                              "solver_reported_s": reported,
                              "cplex_status": "solver_crash", "n_retimed": 0,
                              "attempt": attempt, "local_span_s": 0.0,
                              "round_span_s": 0.0})
            rounds += 1
            continue
        if len(rows) != len(window):
            raise SystemExit("round %d: %d plan rows for %d vehicles"
                             % (rounds, len(rows), len(window)))
        for row in rows:                      # local -> absolute
            row["in_time"] += origin
        local_span = (max(r["in_time"] for r in rows)
                      - min(r["in_time"] for r in rows)) if rows else 0.0
        order = sorted(range(len(rows)), key=lambda i: (rows[i]["in_time"], i))
        shifts = 0
        for i in order:
            r, row = window[i], rows[i]
            # "limit" (default) and "kinematic" cannot exceed the scenario cap;
            # "psl" reports exactly what the solver returned.
            speed = (row["speed"] if args.speed_mode == "psl"
                     else min(row["speed"], args.vmax))
            release, windows = guard.earliest(r["prefix"], row["in_time"], speed)
            guard.commit(windows)
            if release > row["in_time"] + 1e-6:
                shifts += 1
            frontier = max(frontier, release)
            move = paths_by_prefix[r["prefix"]]["move"]
            passage = kin.li(move)
            trav = kin.traversal_time(row["length"], mode=model, speed=speed,
                                      accel=args.accel, vmax=args.vmax)
            tail = kin.occupancy(release, row["length"], passage, mode=model,
                                 speed=speed, accel=args.accel,
                                 vmax=args.vmax, w=args.w)[1]
            schedule.append({
                "load_index": len(schedule),
                "vehicle_id": r["vehicle_id"],
                "prefix": r["prefix"],
                "in_point": row["in_point"],
                "out_point": row["out_point"],
                "length": row["length"],
                "earliest_arrival": r["arrival_freeflow"],
                "psl_in_time": round(row["in_time"], 6),
                "psl_speed": row["speed"],
                "in_time": round(release, 6),
                "out_time_head": round(release + trav, 6),
                "out_time_tail": round(tail, 6),
                "time_spend": round(trav, 6),
                "speed": round(speed, 6),
                "importance": 1,
            })
        done = set(order)
        pending = pending[len(window):]
        per_batch.append({"round": rounds, "window": len(window),
                          "committed": len(order),
                          "wall_s": round(wall, 6),
                          "solver_reported_s": reported,
                          "cplex_status": status, "n_retimed": shifts,
                          "attempt": attempt,
                          "local_span_s": round(local_span, 3),
                          "round_span_s": round(frontier - frontier_before, 3)})
        rounds += 1
        if rounds % 10 == 0:
            print("  round %d  committed %d / %d  frontier %.1f s  solver %.1f s"
                  % (rounds, len(schedule), len(requests), frontier, total_wall),
                  flush=True)

    # ---- uncoordinated (conflict-free) movements ----------------------
    for r in free_reqs:
        p = paths_by_prefix[r["prefix"]]
        passage = kin.li(p["move"])
        release = r["arrival_freeflow"]
        speed = min(args.vmax, kin.V_LIMIT) if args.speed_mode != "psl" else \
            kin.V_LIMIT
        trav = kin.traversal_time(p["length"], mode=model, speed=speed,
                                  accel=args.accel, vmax=args.vmax)
        tail = kin.occupancy(release, p["length"], passage, mode=model,
                             speed=speed, accel=args.accel,
                             vmax=args.vmax, w=args.w)[1]
        schedule.append({
            "load_index": len(schedule),
            "vehicle_id": r["vehicle_id"],
            "prefix": r["prefix"],
            "in_point": p["vertices"][0] if p["vertices"] else r["prefix"],
            "out_point": p["vertices"][-1] if p["vertices"] else r["prefix"],
            "length": round(p["length"], 6),
            "earliest_arrival": r["arrival_freeflow"],
            "psl_in_time": "",
            "psl_speed": "",
            "in_time": round(release, 6),
            "out_time_head": round(release + trav, 6),
            "out_time_tail": round(tail, 6),
            "time_spend": round(trav, 6),
            "speed": round(speed, 6),
            "importance": 1,
            "coordinated": False,
        })
    schedule.sort(key=lambda d: (d["in_time"], d["vehicle_id"]))
    for i, row in enumerate(schedule):
        row["load_index"] = i
        row.setdefault("coordinated", True)

    # ---- outputs ------------------------------------------------------
    fields = ["load_index", "vehicle_id", "prefix", "in_point", "out_point",
              "length", "earliest_arrival", "psl_in_time", "psl_speed",
              "in_time", "out_time_head", "out_time_tail", "time_spend",
              "speed", "importance", "coordinated"]
    with open(run / "schedule.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for row in schedule:
            w.writerow(row)
    # a plan.csv compatible with validate_plan.py
    with open(run / "plan.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=PSL_COLUMNS + ["load_index"])
        w.writeheader()
        for row in schedule:
            w.writerow({k: row[k] for k in PSL_COLUMNS}
                       | {"load_index": row["load_index"]})

    coord = [r for r in schedule if r.get("coordinated")]
    delays = [r["in_time"] - r["earliest_arrival"] for r in coord]
    retime = [r["in_time"] - float(r["psl_in_time"]) for r in coord
               if r["psl_in_time"] != ""]
    statuses = {}
    for b in per_batch:
        statuses[b["cplex_status"]] = statuses.get(b["cplex_status"], 0) + 1
    first = min((r["earliest_arrival"] for r in schedule), default=0.0)
    last = max((r["out_time_tail"] for r in schedule), default=0.0)
    span = last - first
    summary = {
        "method": "psl",
        "output_kind": "schedule_only",
        "packer": args.packer,
        "passage_speed_w": args.w,
        "speed_mode": args.speed_mode,
        "kinematics": {"model": model, "accel": args.accel, "vmax": args.vmax,
                       "note": "upstream LP bounds are v in [3,15] but "
                               "types.typ.xml caps speed at 13.9"},
        "batch_size": args.batch_size,
        "window_size": args.window_size,
        "n_vehicles": len(schedule),
        "n_coordinated": sum(1 for r in schedule if r.get("coordinated")),
        "n_uncoordinated_conflict_free": sum(1 for r in schedule
                                             if not r.get("coordinated")),
        "n_batches": len(per_batch),
        "horizon_s": [round(first, 6), round(last, 6)],
        "makespan_s": round(span, 6),
        "n_retimed_vs_psl": sum(1 for d in retime if d > 1e-6),
        "delay_stats_s": {
            "mean_vs_freeflow": round(sum(delays) / len(delays), 6) if delays else None,
            "max_vs_freeflow": round(max(delays), 6) if delays else None,
            "mean_vs_psl_plan": round(sum(retime) / len(retime), 6) if retime else None,
            "max_vs_psl_plan": round(max(retime), 6) if retime else None,
        },
        "throughput_veh_per_h": round(len(schedule) * 3600.0 / span, 3) if span else None,
        "completion_within_horizon": _completion(coord, args.horizon),
        "saturation": {
            "demand_rate_veh_s": round(len(coord) / args.horizon, 4),
            "scheduled_rate_veh_s": round(len(coord) / span, 4) if span else None,
            "ratio_scheduled_over_demand": round(len(coord) / span * args.horizon
                                                 / len(coord), 4)
            if span and coord else None,
            "note": "scheduled_rate is the sustained rate implied by the emitted "
                    "schedule; if it is below demand the queue cannot clear "
                    "inside the horizon and completion_within_horizon < 1",
        },
        "planning": {
            "batches_solved": len(per_batch),
            "cplex_status_counts": statuses,
            "timeouts": statuses.get("timeout", 0),
            "failures": sum(v for k, v in statuses.items()
                            if k not in ("optimal", "feasible")),
            "window_attempts": {k: v for k, v in solve_stats.items()
                                if k in ("backlog", "plain_eta")},
            "failed_windows": solve_stats.get("failed_windows", 0),
            "failure_notes": solve_stats.get("failure_notes", [])[:5],
            "total_solver_wall_s": round(total_wall, 6),
            "mean_solver_wall_s": round(total_wall / len(per_batch), 6)
            if per_batch else None,
            "reported_by_solver_s": round(
                sum(b["solver_reported_s"] or 0.0 for b in per_batch), 6),
        },
        "reservation_guard": {"checks": guard.n_checks,
                             "committed_vehicles": guard.n_pushes},
        "not_available": ["throughput/travel time/collision counts from SUMO "
                          "execution -- this is a planning-side schedule only"],
        "per_batch": per_batch,
    }
    (run / "summary.json").write_text(json.dumps(summary, indent=1))

    manifest = {
        "algorithm": "psl",
        "adapter_version": "plan_scenario/1",
        "binary_provenance": "upstream_prebuilt",
        "binary_sha256": sha256(binary),
        "upstream_repo": "https://github.com/theanhhoang/AIM.git",
        "upstream_branch": "AAAI22_PBS-SIPP",
        "upstream_commit": "5686e15092fd95a46309a118655a5ab0c23c60fa",
        "instance_dir": str(inst), "demand_dir": str(dem),
        "net_sha256": manifest_in.get("net_sha256"),
        "rou_sha256": manifest_in.get("rou_sha256"),
        "typ_sha256": manifest_in.get("typ_sha256"),
        "seed": manifest_in.get("seed"),
        "arrival_model": manifest_in.get("arrival_model"),
        "reference_source": manifest_in.get("reference_source"),
        "speed_mode": args.speed_mode,
        "passage_speed_w": args.w,
        "passage_speed_w_note": "upstream SIPP.h:79 hard-codes 7; this is the "
                                "value the ADAPTER enforces. The binary is "
                                "unmodified and still plans with 7.",
        "batch_size": args.batch_size,
        "window_size": args.window_size,
        "kinematics_deviation": "PSL v_max=15 m/s (hard-coded) vs "
                                "types.typ.xml maxSpeed=13.9 m/s",
        "graph_vertices": len(graph["vertices"]),
        "n_requests": len(requests),
    }
    (run / "run_manifest.json").write_text(json.dumps(manifest, indent=1))
    print(json.dumps({k: summary[k] for k in
                      ("n_vehicles", "n_batches", "makespan_s",
                       "n_retimed_vs_psl", "delay_stats_s",
                       "throughput_veh_per_h")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
