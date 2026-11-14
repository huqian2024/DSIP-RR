"""Independently re-check a PSL plan against the upstream conflict model.

``output.txt`` only exposes per-vehicle entry/exit times, so a "no collision"
claim cannot be read off it.  It can however be *re-derived*: the upstream LP
gives every vehicle **one constant speed** for its whole path
(``SIPP.cpp:183-195``), so the time at which vehicle *i* reaches a conflict point
at along-path offset ``o`` is ``in_time_i + o / speed_i``, and it occupies that
point for::

    [ in_time + o/v ,  in_time + o/v + Li(direction)/w + Li(direction)/v ]

with ``Li`` and ``w`` from ``SIPP.cpp:364-380`` / ``SIPP.h:77-79``::

    w                 = 7
    turn_radius_right = 10 * 0.3048  m
    turn_radius_left  = 40 * 0.3048  m
    Li(straight)      = 5            (agent length)
    Li(left/right)    = 4 R asin(L / (2 R))

This module recomputes those occupancies from ``plan.csv`` + ``graph.json`` +
``paths.json`` and reports every overlapping pair.  It is an *independent*
check: it does not read the solver's reservation table.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kinematics as kin  # noqa: E402

EPS = 1e-6
# The LP may place one vehicle's tail exactly on the next vehicle's head
# (``leaving_time_tail == arrival_time`` is feasible upstream).  Anything below
# this threshold is treated as touching, not overlapping.
TOUCH_TOL = 1e-3
W = kin.W
TURN_RADIUS_RIGHT = kin.TURN_RADIUS_RIGHT
TURN_RADIUS_LEFT = kin.TURN_RADIUS_LEFT
AGENT_LENGTH = kin.AGENT_LENGTH


def li(move, agent_length=AGENT_LENGTH):
    return kin.li(move, agent_length)


def load_plan(path):
    rows = []
    with open(path, newline="") as fh:
        for r in csv.DictReader(fh):
            for k in ("length", "earliest_arrival", "in_time", "out_time_head",
                      "out_time_tail", "time_spend", "speed"):
                r[k] = float(r[k])
            r["load_index"] = int(r["load_index"])
            rows.append(r)
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plan", required=True)
    ap.add_argument("--graph", required=True)
    ap.add_argument("--paths", required=True)
    ap.add_argument("--out", default=None, help="write the JSON report here")
    ap.add_argument("--speed-model", choices=("constant", "accelerating"),
                    default="constant",
                    help="constant = upstream's model; accelerating = held "
                         "vehicle entering from rest at the typed accel")
    ap.add_argument("--accel", type=float, default=kin.ACCEL)
    ap.add_argument("--vmax", type=float, default=kin.V_LIMIT)
    ap.add_argument("--w", type=float, default=kin.W,
                    help="passage speed used to price a conflict point; must "
                         "match the value the schedule was built with")
    args = ap.parse_args(argv)

    rows = load_plan(args.plan)
    graph = json.loads(Path(args.graph).read_text())
    paths = json.loads(Path(args.paths).read_text())["paths"]
    by_prefix = {p["prefix"]: p for p in paths}
    conf = {v["name"]: v["vertex_conflicts"] for v in graph["vertices"]}

    problems = []

    # ---- per-vehicle bounds ------------------------------------------------
    for r in rows:
        # schedule.csv rounds times to 1e-6 s, so compare with a matching margin
        if r["in_time"] < r["earliest_arrival"] - 1e-3:
            problems.append("V%d leaves before earliest arrival (%.6f < %.6f)"
                            % (r["load_index"], r["in_time"], r["earliest_arrival"]))
        if r["out_time_head"] < r["in_time"] - EPS:
            problems.append("V%d negative travel time" % r["load_index"])
        if r["out_time_tail"] < r["out_time_head"] - EPS:
            problems.append("V%d tail before head" % r["load_index"])
        if not (3.0 - EPS <= r["speed"] <= 15.0 + EPS):
            problems.append("V%d speed %.4f outside the upstream LP bounds [3,15]"
                            % (r["load_index"], r["speed"]))
        expect = kin.traversal_time(r["length"], mode=args.speed_model,
                                    speed=r["speed"], accel=args.accel,
                                    vmax=args.vmax)
        if abs((r["out_time_head"] - r["in_time"]) - expect) > 1e-3:
            problems.append("V%d time_spend %.6f != %s-model traversal %.6f"
                            % (r["load_index"],
                               r["out_time_head"] - r["in_time"],
                               args.speed_model, expect))

    # ---- occupancy windows ------------------------------------------------
    windows = {}          # vertex name -> list of (load_index, t0, t1)
    for r in rows:
        prefix = r["in_point"].split("_")[0]
        p = by_prefix.get(prefix)
        if p is None:
            problems.append("V%d prefix %s not in paths.json"
                            % (r["load_index"], prefix))
            continue
        length_li = li(p["move"])
        for vname, off in zip(p["vertices"], p["offsets"]):
            t0, t1 = kin.occupancy(r["in_time"], off, length_li,
                                   mode=args.speed_model, speed=r["speed"],
                                   accel=args.accel, vmax=args.vmax, w=args.w)
            windows.setdefault(vname, []).append((r["load_index"], t0, t1))

    checked, touching, violations = set(), [], []
    for name, partners in conf.items():
        mine = windows.get(name, [])
        if not mine:
            continue
        for other in partners:
            if name >= other:
                continue
            theirs = windows.get(other, [])
            for ia, ta0, ta1 in mine:
                for ib, tb0, tb1 in theirs:
                    if ia == ib:
                        continue
                    key = (name, other, min(ia, ib), max(ia, ib))
                    checked.add(key)
                    overlap = min(ta1, tb1) - max(ta0, tb0)
                    if overlap <= TOUCH_TOL:
                        if overlap > -TOUCH_TOL:
                            touching.append({"point": name, "overlap_s":
                                             round(overlap, 9)})
                        continue
                    violations.append({
                        "point": name, "conflict_with": other,
                        "vehicles": [rows[ia]["vehicle_id"],
                                     rows[ib]["vehicle_id"]],
                        "overlap_s": round(overlap, 6),
                        "window_a": [round(ta0, 6), round(ta1, 6)],
                        "window_b": [round(tb0, 6), round(tb1, 6)],
                    })

    delays = [r["in_time"] - r["earliest_arrival"] for r in rows]
    report = {
        "n_vehicles": len(rows),
        "checks": {"per_vehicle": len(rows),
                   "conflict_vertex_pairs_checked": len(checked),
                   "exact_touch_pairs": len(touching),
                   "touch_tolerance_s": TOUCH_TOL,
                   "conflict_violations": len(violations)},
        "problems": problems,
        "violations": violations[:50],
        "metrics": {
            "mean_control_delay_s": round(sum(delays) / len(delays), 6) if rows else None,
            "max_control_delay_s": round(max(delays), 6) if rows else None,
            "makespan_s": round(max((r["out_time_tail"] for r in rows),
                                    default=0.0), 6),
            "mean_speed_mps": round(sum(r["speed"] for r in rows) / len(rows), 6)
            if rows else None,
            "mean_internal_travel_time_s": round(
                sum(r["time_spend"] for r in rows) / len(rows), 6) if rows else None,
        },
        "ok": not problems and not violations,
        "definitions": {
            "occupancy": "kinematics.occupancy(release, offset, Li, mode)",
            "speed_model": args.speed_model,
            "accel": args.accel, "vmax": args.vmax,
            "w": args.w, "turn_radius_right_m": TURN_RADIUS_RIGHT,
            "turn_radius_left_m": TURN_RADIUS_LEFT,
            "agent_length_m": AGENT_LENGTH,
            "note": "independent re-derivation of SIPP.cpp:183-380; the solver's "
                    "own reservation table is not read",
        },
    }
    text = json.dumps(report, indent=1)
    if args.out:
        Path(args.out).write_text(text)
    print(text)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
