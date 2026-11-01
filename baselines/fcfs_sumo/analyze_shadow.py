#!/usr/bin/env python3
"""Post-hoc analysis of a FCFS SHADOW run (reads only the produced CSVs).

Reconstructs per-step occupancy of the junction from
``results/fcfs_shadow/vehicle_events.csv`` and reports how often two
*conflicting* movements were inside the junction at the same time -- the
central diagnostic of shadow mode: without actuation the observed behaviour is
expected to violate the computed admissions.

Usage (from the repository root):
    python3 -m baselines.fcfs_sumo.analyze_shadow
"""

import csv
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from baselines.fcfs_sumo.conflicts import ConflictModel   # noqa: E402

OUT_DIR = ROOT / "results" / "fcfs_shadow"


def read_csv(name):
    path = OUT_DIR / name
    if not path.exists():
        raise SystemExit("missing %s (run the shadow runner first)" % path)
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def main():
    model = ConflictModel()
    events = read_csv("vehicle_events.csv")
    requests = read_csv("requests.csv")
    decisions = read_csv("decisions.csv")
    label = {m["id"]: m["index"] for m in model.movements}

    print("=" * 78)
    print("FCFS SHADOW run - post-hoc analysis (SHADOW MODE, no control)")
    print("=" * 78)

    enter_t, leave_t = {}, {}
    for row in events:
        vid, ev = row["vehicle_id"], row["event"]
        if ev == "enter":
            enter_t[vid] = float(row["t"])
        elif ev in ("leave", "gone_inside"):
            leave_t.setdefault(vid, float(row["t"]))
    end_time = max([float(r["t"]) for r in events] + [float(r["t"]) for r in decisions])

    mover = {r["vehicle_id"]: r["movement"] for r in requests}
    inside = defaultdict(set)
    for vid, t0 in enter_t.items():
        t1 = leave_t.get(vid, end_time)
        t = t0
        while t < t1:
            inside[t].add(vid)
            t += 1.0
    print("occupancy steps reconstructed:", len(inside))

    episodes = Counter()
    for t in sorted(inside):
        vids = sorted(inside[t])
        for i, a in enumerate(vids):
            ma = mover.get(a)
            if ma not in label:
                continue
            for b in vids[i + 1:]:
                mb = mover.get(b)
                if mb not in label:
                    continue
                if ma != mb and model.conflicts(label[ma], label[mb]):
                    episodes[tuple(sorted((ma, mb)))] += 1

    print()
    print("-" * 78)
    print("CONFLICTING MOVEMENTS SIMULTANEOUSLY INSIDE (uncontrolled shadow run)")
    print("-" * 78)
    print("distinct conflicting pairs : %d" % len(episodes))
    print("total co-occupancy steps   : %d" % sum(episodes.values()))
    for pair, count in episodes.most_common():
        print("  %s x %s : %d step-pairs (%.0f s of shared occupancy)"
              % (pair[0], pair[1], count, count))

    print()
    print("-" * 78)
    print("PER-MOVEMENT SUMMARY")
    print("-" * 78)
    by_mv = defaultdict(lambda: {"requests": 0, "entered": 0, "blocked_entry": 0})
    for row in requests:
        m = row["movement"]
        by_mv[m]["requests"] += 1
        if row["t_enter_actual"]:
            by_mv[m]["entered"] += 1
        if row["entered_while_blocked"] == "True":
            by_mv[m]["blocked_entry"] += 1
    print("%-5s %-4s %9s %8s %16s" % ("mv", "dir", "requests", "entered",
                                      "entered@BLOCKED"))
    for m in model.movements:
        st = by_mv[m["id"]]
        print("%-5s %-4s %9d %8d %16d" % (m["id"], m["dir"], st["requests"],
                                          st["entered"], st["blocked_entry"]))

    waits = [float(r["t_enter_actual"]) - float(r["t_request"])
             for r in requests if r["t_enter_actual"]]
    if waits:
        print()
        print("proxy request -> observed entry (s): n=%d mean=%.2f median=%.2f "
              "min=%.2f max=%.2f"
              % (len(waits), statistics.mean(waits), statistics.median(waits),
                 min(waits), max(waits)))

    print()
    print("first decision distribution :",
          dict(sorted(Counter(r["first_decision"] for r in requests).items())))
    print("decision before entry       :",
          dict(sorted(Counter(r["last_decision_before_entry"] for r in requests
                              if r["last_decision_before_entry"]).items())))
    print("entered while BLOCKED       :",
          sum(1 for r in requests if r["entered_while_blocked"] == "True"))
    print("entered while UNDETERMINED  :",
          sum(1 for r in requests if r["entered_while_undetermined"] == "True"))
    print("decision rows               :", len(decisions))
    print("rows by status              :",
          dict(sorted(Counter(r["status"] for r in decisions).items())))
    print("rows by resource_state      :",
          dict(sorted(Counter(r["resource_state"] for r in decisions).items())))

    last_blocked = {}
    for row in decisions:
        if row["status"] == "BLOCKED":
            last_blocked[row["vehicle_id"]] = row["blocking_movements"]
    counter = Counter()
    for row in requests:
        if row["entered_while_blocked"] == "True":
            counter[last_blocked.get(row["vehicle_id"], "?")] += 1
    print()
    print("conflicting movement(s) reported at entry, for 'entered while BLOCKED':")
    for key, count in counter.most_common():
        print("   %-24s %d vehicles" % (key or "(none)", count))

    open_v = [r for r in requests if r["t_enter_actual"] and not r["t_leave_actual"]]
    print()
    print("still inside the junction at simulation end: %d" % len(open_v))
    for r in open_v:
        print("   %-12s %s entered at t=%s" % (r["vehicle_id"], r["movement"],
                                               r["t_enter_actual"]))
    print()
    print("NOTE: SHADOW MODE. Vehicles were NOT controlled, so every contradiction")
    print("      above is an expected diagnostic, not an FCFS performance result.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
