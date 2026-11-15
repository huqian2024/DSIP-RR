#!/usr/bin/env python3
"""S4 -- dynamics-aware validation of the committed DSIP plans.

The reconstructed planner inherits the prior's collision model: a **disk** of
radius 0.05 frame units.  With one frame unit = 34.75 m that disk is 1.74 m in
radius, while a SUMO vehicle is 5 m long and 1.8 m wide.  ``paper_faithful``
execution therefore commands positions the planner considered collision free but
which are not free for rectangles -- which is why the S3 runs report many
proximity events.

This script measures that gap instead of arguing about it:

* converts every committed plan into world positions at the SUMO step (0.1 s),
* checks **oriented rectangles** (5.0 x 1.8 m) pairwise at coincident times with
  the separating-axis test,
* derives the commanded speed / acceleration / jerk profile of each plan
  (statistic A of the reconstruction plan: max acceleration and jerk).

No planner code is touched: the plans are validated after the fact, so the
coordinator stays exactly as upstream ships it.

    python3 src/dsip_reconstruction/dynamics_aware.py \
        --run results/dsip_compare/lanes3_density3.rou-dsip-s81890 \
        --out results/dsip_s4
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.dsip_reconstruction.sumo_runner import (        # noqa: E402
    PLAN_DT, cumulative, point_at)

TIME_SCALE = 1.0       # execution time dilation (--time-scale of the runner)
SMOOTH = 9              # samples in the moving-average window
VEH_LENGTH = 5.0
VEH_WIDTH = 1.8
STEP = 0.1


def interp(xs, ys, x):
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    lo, hi = 0, len(xs) - 1
    while lo < hi - 1:
        mid = (lo + hi) // 2
        if xs[mid] <= x:
            lo = mid
        else:
            hi = mid
    span = xs[hi] - xs[lo]
    f = 0.0 if span <= 0 else (x - xs[lo]) / span
    return ys[lo] + f * (ys[hi] - ys[lo])


def plan_samples(plan):
    """[(t_rel, x, y, heading_rad), ...] at STEP resolution."""
    pts = [(p[0], p[1]) for p in plan["pts"]]
    cum = cumulative(pts)
    total = cum[-1]
    ts = [k * PLAN_DT * TIME_SCALE for k in range(len(plan["s"]))]
    arcs = [s * plan["L"] for s in plan["s"]]
    out = []
    t = 0.0
    horizon = ts[-1]
    while t <= horizon + 1e-9:
        arc = min(interp(ts, arcs, t), total)
        x, y = point_at(pts, cum, arc)
        x2, y2 = point_at(pts, cum, min(arc + 0.5, total))
        heading = math.atan2(y2 - y, x2 - x)
        out.append((t, x, y, heading))
        t += STEP
    return out


def kin(plan):
    """Commanded speed / acceleration / jerk on the plan's own time grid.

    Evaluated at the prior's resolution (PLAN_DT = 5/64 s) rather than at the SUMO
    step: resampling a 0.078 s profile onto 0.1 s introduces quantisation noise
    that would dominate a second difference.  The first and last two samples are
    dropped so the plan's own start/stop edges do not masquerade as accelerations.
    """
    arcs = [s * plan["L"] for s in plan["s"]]
    dt_eff = PLAN_DT * TIME_SCALE
    # The sampler's 64 support points are not perfectly evenly spaced, so raw
    # second differences are dominated by point noise.  A centred 5-sample moving
    # average (0.39 s) is applied before differencing; the same window is used for
    # every plan and both metrics, and it is reported in the output.
    w = SMOOTH
    half = w // 2
    arcs = [sum(arcs[max(0, i - half):min(len(arcs), i + half + 1)])
            / len(arcs[max(0, i - half):min(len(arcs), i + half + 1)])
            for i in range(len(arcs))]
    dt = dt_eff
    v = [(arcs[i + 1] - arcs[i]) / dt for i in range(len(arcs) - 1)]
    a = [(v[i + 1] - v[i]) / dt for i in range(len(v) - 1)]
    j = [(a[i + 1] - a[i]) / dt for i in range(len(a) - 1)]
    # Drop the smoothing window's edge effects as well as the plan's own
    # start/stop, otherwise the truncated window at the ends looks like a kick.
    edge = half + 2
    a_int, j_int = a[edge:-edge], j[edge:-edge]

    def q(xs, p):
        if not xs:
            return None
        xs = sorted(xs)
        i = min(len(xs) - 1, max(0, int(round(p * (len(xs) - 1)))))
        return round(xs[i], 4)

    return {
        "v_max": round(max(v), 3) if v else None,
        "a_abs_p50": q([abs(x) for x in a_int], 0.5),
        "a_abs_p95": q([abs(x) for x in a_int], 0.95),
        "a_abs_max": round(max((abs(x) for x in a_int), default=0.0), 3),
        "j_abs_p50": q([abs(x) for x in j_int], 0.5),
        "j_abs_p95": q([abs(x) for x in j_int], 0.95),
        "j_abs_max": round(max((abs(x) for x in j_int), default=0.0), 3),
    }


def rect_corners(x, y, heading):
    c, s = math.cos(heading), math.sin(heading)
    hl, hw = VEH_LENGTH / 2.0, VEH_WIDTH / 2.0
    return [(x + c * dx - s * dy, y + s * dx + c * dy)
            for dx, dy in ((hl, hw), (hl, -hw), (-hl, -hw), (-hl, hw))]


def rects_overlap(a, b):
    """Separating-axis test for two convex quadrilaterals."""
    for poly in (a, b):
        for i in range(4):
            x1, y1 = poly[i]
            x2, y2 = poly[(i + 1) % 4]
            axis = (-(y2 - y1), x2 - x1)
            pa = [axis[0] * px + axis[1] * py for px, py in a]
            pb = [axis[0] * px + axis[1] * py for px, py in b]
            if max(pa) < min(pb) or max(pb) < min(pa):
                return False
    return True



def main(argv=None):
    global VEH_LENGTH, VEH_WIDTH, SMOOTH, TIME_SCALE
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", required=True,
                    help="a DSIP run directory containing s3_plans.json")
    ap.add_argument("--out", default="results/dsip_s4")
    ap.add_argument("--length", type=float, default=VEH_LENGTH)
    ap.add_argument("--width", type=float, default=VEH_WIDTH)
    ap.add_argument("--time-scale", type=float, default=1.0,
                    help="must match the runner's --time-scale: the plan is"
                         " replayed over 5*lambda seconds")
    ap.add_argument("--smooth", type=int, default=SMOOTH,
                    help="moving-average window, in plan samples (PLAN_DT=0.078 s)")
    args = ap.parse_args(argv)

    VEH_LENGTH, VEH_WIDTH = args.length, args.width
    SMOOTH, TIME_SCALE = args.smooth, args.time_scale

    run = Path(args.run)
    run = run if run.is_absolute() else ROOT / run
    out = Path(args.out)
    out = out if out.is_absolute() else ROOT / out
    out.mkdir(parents=True, exist_ok=True)

    plans = json.loads((run / "s3_plans.json").read_text())
    report = json.loads((run / "s3_report.json").read_text())

    samples, kin_rows = {}, []
    for plan in plans:
        smp = plan_samples(plan)
        samples[plan["veh"]] = smp
        row = kin(plan)
        row.update({"veh": plan["veh"], "t0": plan["t0"], "L": plan["L"]})
        kin_rows.append(row)

    vehs = list(samples)
    t0 = {p["veh"]: p["t0"] for p in plans}
    overlaps, checked_pairs = [], 0
    for i in range(len(vehs)):
        for j in range(i + 1, len(vehs)):
            checked_pairs += 1
            si, sj = samples[vehs[i]], samples[vehs[j]]
            off = t0[vehs[i]] - t0[vehs[j]]
            hits, first_t = 0, None
            for (t, x, y, h) in si:
                tb = t - off
                if tb < -1e-9 or tb > sj[-1][0] + 1e-9:
                    continue
                k2 = max(0, min(len(sj) - 1, int(round(tb / STEP))))
                _, x2, y2, h2 = sj[k2]
                if rects_overlap(rect_corners(x, y, h),
                                 rect_corners(x2, y2, h2)):
                    hits += 1
                    if first_t is None:
                        first_t = round(float(t0[vehs[i]] + t), 2)
            if hits:
                overlaps.append({"a": vehs[i], "b": vehs[j], "n_steps": hits,
                                 "first_abs_t": first_t,
                                 "duration_s": round(hits * STEP, 2)})

    def agg(key):
        vals = sorted(r[key] for r in kin_rows if r[key] is not None)
        if not vals:
            return None
        return {"p50": round(vals[len(vals) // 2], 3),
                "p95": round(vals[max(0, int(0.95 * (len(vals) - 1)))], 3),
                "max": round(vals[-1], 3)}

    result = {
        "stage": "S4",
        "mode": "dynamics_aware (post-hoc validation; coordinator unchanged)",
        "run": str(run.relative_to(ROOT)),
        "n_plans": len(plans),
        "n_pairs_checked": checked_pairs,
        "n_pairs_with_rectangle_overlap": len(overlaps),
        "fraction_pairs_with_overlap": (round(len(overlaps) / checked_pairs, 4)
                                        if checked_pairs else None),
        "rect_overlap_steps_total": sum(o["n_steps"] for o in overlaps),
        "vehicle_geometry_m": {"length": VEH_LENGTH, "width": VEH_WIDTH},
        "execution_time_scale": TIME_SCALE,
        "kinematics_smoothing": ("centred %d-sample moving average of arc length"
                                 " (%.2f s) before finite differences"
                                 % (SMOOTH, SMOOTH * PLAN_DT)),
        "kinematics": {k: agg(k) for k in
                       ("v_max", "a_abs_p50", "a_abs_p95", "a_abs_max",
                        "j_abs_p50", "j_abs_p95", "j_abs_max")},
        "planner_declared_mode": report.get("mode"),
        "sumo_proximity_events_lt1p5m": report.get("proximity_events_lt1p5m"),
        "overlaps_head": overlaps[:20],
    }
    (out / ("%s-s4.json" % run.name)).write_text(json.dumps(result, indent=2))
    cols = ("veh", "t0", "L", "v_max", "a_abs_p50", "a_abs_p95", "a_abs_max",
            "j_abs_p50", "j_abs_p95", "j_abs_max")
    (out / ("%s-kin.csv" % run.name)).write_text(
        ",".join(cols) + "\n"
        + "\n".join(",".join(str(r.get(c)) for c in cols) for r in kin_rows))
    print(json.dumps({k: result[k] for k in
                      ["n_plans", "n_pairs_with_rectangle_overlap",
                       "fraction_pairs_with_overlap",
                       "sumo_proximity_events_lt1p5m"]}, indent=2))
    print("a_abs_max", result["kinematics"]["a_abs_max"],
          "j_abs_max", result["kinematics"]["j_abs_max"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
