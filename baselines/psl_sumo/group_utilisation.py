"""Diagnostic: conflict-group utilisation of an emitted schedule.

Reads ``schedule.csv`` + ``paths.json`` + ``graph.json`` and reports, per
conflict group, how much of the planning horizon is occupied.  A group at
~100 % utilisation is a hard capacity ceiling of the *model*, not of the solver,
so this is the first thing to check before reading anything into the delays.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kinematics as kin  # noqa: E402
from plan_scenario import conflict_groups  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--schedule", required=True)
    ap.add_argument("--graph", required=True)
    ap.add_argument("--paths", required=True)
    ap.add_argument("--speed-model", choices=("constant", "accelerating"),
                    default="constant")
    ap.add_argument("--accel", type=float, default=kin.ACCEL)
    ap.add_argument("--vmax", type=float, default=kin.V_LIMIT)
    ap.add_argument("--top", type=int, default=20)
    args = ap.parse_args(argv)

    graph = json.loads(Path(args.graph).read_text())
    paths = {p["prefix"]: p for p in
             json.loads(Path(args.paths).read_text())["paths"]}
    gid = conflict_groups(graph)
    name_of_group = {}
    for v in graph["vertices"]:
        name_of_group.setdefault(gid[v["name"]], []).append(v["name"])

    rows = list(csv.DictReader(open(args.schedule, newline="")))
    load = {}
    t_min, t_max = float("inf"), 0.0
    for r in rows:
        p = paths[r["prefix"]]
        release = float(r["in_time"])
        speed = float(r["speed"])
        passage = kin.li(p["move"])
        for name, off in zip(p["vertices"], p["offsets"]):
            t0, t1 = kin.occupancy(release, off, passage, mode=args.speed_model,
                                   speed=speed, accel=args.accel, vmax=args.vmax)
            g = gid[name]
            load[g] = load.get(g, 0.0) + (t1 - t0)
            t_min = min(t_min, t0)
            t_max = max(t_max, t1)
    span = max(t_max - t_min, 1e-9)

    ranked = sorted(load.items(), key=lambda kv: -kv[1])
    print("vehicles=%d  horizon=%.1f s  groups=%d" % (len(rows), span, len(load)))
    print("%-6s %-10s %-8s %s" % ("group", "util%", "veh", "members"))
    for g, busy in ranked[:args.top]:
        n = sum(1 for r in rows
                if any(gid[v] == g for v in paths[r["prefix"]]["vertices"]))
        print("%-6d %-10.1f %-8d %s"
              % (g, 100.0 * busy / span, n,
                 ",".join(sorted(name_of_group[g])[:6])))
    over = [g for g, busy in load.items() if busy / span > 1.0]
    print("groups over 100%% utilisation: %d" % len(over))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
