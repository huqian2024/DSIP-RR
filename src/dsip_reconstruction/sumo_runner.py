"""S3 -- drive SUMO through MMD-xECBS (paper_faithful position control).

Structure
---------
``Frame``     maps SUMO world coordinates to the prior's [-1, 1]^2 planning box.
``RouteGeom`` per-vehicle polyline from the net's edge shapes, arc-length
              parameterised, so a planned progress fraction maps to a world point.
``DSIPRunner`` the rolling loop: pick the vehicles inside the commit window, plan
              them jointly with upstream ``CBS`` (is_xcbs/is_ecbs), execute the
              first part of the returned trajectories by idealised position
              control, then replan.

Execution vs planning
---------------------
The plan is expressed as a progress fraction ``s(t)`` along the vehicle's own
route (the chord in frame space corresponds to the route inside the region), so
lateral geometry comes from the SUMO net and timing comes from the planner.  This
is the ``paper_faithful`` mode of ``AGENTS.md``: positions are commanded, no
kinematic or curvature check is applied.  Every run records that choice.

Fallback (the "is there a backstop" question)
---------------------------------------------
If a planning call raises, exceeds ``--cbs-timeout`` or returns no solution, the
affected vehicles are *released to SUMO* (``setSpeed(-1)``) and counted in
``fallbacks``.  The run continues; no vehicle is frozen.  Every call's wall time
is logged with an ``over_budget`` flag against ``--budget`` (default 0.4 s).
"""

from __future__ import annotations

import json
import math
import os
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import torch

from . import prior

ROOT = Path(__file__).resolve().parents[2]

BOX_EDGE = 0.90          # keeps starts/goals inside the robot workspace
PLAN_DT = 5.0 / 64.0          # prior horizon: 64 support points over 5 s


class Frame:
    """World <-> planning-frame transform: ``q = (p - center) / metres_per_unit``."""

    def __init__(self, center, metres_per_unit):
        self.center = center
        self.scale = float(metres_per_unit)

    def to_frame(self, x, y):
        return ((x - self.center[0]) / self.scale,
                (y - self.center[1]) / self.scale)

    def from_frame(self, qx, qy):
        return (qx * self.scale + self.center[0],
                qy * self.scale + self.center[1])


class RouteGeom:
    """Per-edge polylines from the net's *lane* shapes, arc-length ready.

    Edges in this net carry no ``shape`` attribute; every lane does.  One lane per
    edge is used (the median index) because the plan only needs the movement's
    centreline -- lateral lane offsets (< 3.5 m) are absorbed by the frame scale
    and by ``moveToXY(keepRoute=2)``.
    """

    def __init__(self, net_path):
        root = ET.parse(str(net_path)).getroot()
        self.edges = {}
        self.edge_meta = {}
        for edge in root.findall("edge"):
            if edge.get("function") == "internal":
                continue
            lanes = []
            for lane in edge.findall("lane"):
                shape = lane.get("shape")
                if not shape:
                    continue
                pts = [tuple(float(v) for v in pair.split(","))
                       for pair in shape.split()]
                if len(pts) >= 2:
                    lanes.append((int(lane.get("index", 0)), pts))
            if not lanes:
                continue
            lanes.sort()
            eid = edge.get("id")
            self.edges[eid] = lanes[len(lanes) // 2][1]
            self.edge_meta[eid] = (edge.get("from"), edge.get("to"))

    def polyline(self, edge_ids, step=1.0):
        """Concatenate the edges' centrelines and resample at ``step`` metres.

        Lane shapes in this net have only their endpoints, so the raw polyline is
        too coarse to locate where a route leaves the planning box; resampling to
        1 m makes that crossing point well defined.
        """
        pts = []
        for eid in edge_ids:
            seg = self.edges.get(eid)
            if not seg:
                continue
            if pts and (abs(pts[-1][0] - seg[0][0]) < 1e-6
                        and abs(pts[-1][1] - seg[0][1]) < 1e-6):
                seg = seg[1:]
            pts.extend(seg)
        return resample(pts, step)

    def junction_boundary(self, junction_id):
        """Points where the incident edges meet the junction."""
        pts = []
        for eid, (src, dst) in self.edge_meta.items():
            seg = self.edges[eid]
            if dst == junction_id:
                pts.append(seg[-1])
            if src == junction_id:
                pts.append(seg[0])
        return pts


def resample(pts, step):
    """Insert points so consecutive samples are at most ``step`` metres apart."""
    if len(pts) < 2:
        return list(pts)
    out = [pts[0]]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        d = math.hypot(x1 - x0, y1 - y0)
        n = max(1, int(math.ceil(d / step)))
        for k in range(1, n + 1):
            f = k / n
            out.append((x0 + f * (x1 - x0), y0 + f * (y1 - y0)))
    return out


def cumulative(pts):
    cum = [0.0]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        cum.append(cum[-1] + math.hypot(x1 - x0, y1 - y0))
    return cum


def point_at(pts, cum, s):
    """World point at arc length ``s`` along ``pts``."""
    if not pts:
        return None
    if s <= 0:
        return pts[0]
    if s >= cum[-1]:
        return pts[-1]
    lo, hi = 0, len(cum) - 1
    while lo < hi - 1:
        mid = (lo + hi) // 2
        if cum[mid] <= s:
            lo = mid
        else:
            hi = mid
    span = cum[hi] - cum[lo]
    frac = 0.0 if span <= 0 else (s - cum[lo]) / span
    x0, y0 = pts[lo]
    x1, y1 = pts[hi]
    return (x0 + frac * (x1 - x0), y0 + frac * (y1 - y0))


def progress_curve(path_xy, horizon=64):
    """Normalised arc-length progress s_k in [0, 1] for each plan step."""
    pts = [(float(p[0]), float(p[1])) for p in path_xy[:horizon]]
    cum = cumulative(pts)
    total = cum[-1] if cum else 0.0
    if total <= 1e-9:
        return [0.0] * len(pts)
    return [c / total for c in cum]



class DSIPRunner:
    def __init__(self, args):
        self.args = args
        self.frame = None
        self.geom = RouteGeom(args.net)
        self.plans = {}          # veh_id -> {"s": [...], "t0": sim time, "L": metres}
        self.released = set()
        self.records = []        # one row per CBS call
        self.fallbacks = []
        self.n_planned_vehicles = 0

    # -- setup ---------------------------------------------------------------
    def build_frame(self, tc, junction_id):
        """Scale the planning box so the prior's 5 s horizon equals the crossing.

        The prior always spans its trajectory over ``trajectory_duration`` = 5 s.
        One frame unit is therefore set to ``0.5 * v * 5 s`` so that a vehicle
        entering at one edge and leaving at the opposite one travels at the road
        speed limit.  With ``v = 13.9 m/s`` the box half-width is 34.75 m.
        """
        x0, y0 = tc.junction.getPosition(junction_id)
        boundary = self.geom.junction_boundary(junction_id)
        junction_half = (max(max(abs(px - x0), abs(py - y0))
                            for px, py in boundary) if boundary else 15.0)
        metres_per_unit = 0.5 * self.args.road_speed * 5.0
        self.frame = Frame((x0, y0), metres_per_unit)
        if not self.args.commit_window:
            self.args.commit_window = 2.0 * metres_per_unit
        return {"junction": junction_id, "center": [x0, y0],
                "junction_half_extent_m": round(junction_half, 3),
                "metres_per_unit": round(metres_per_unit, 3),
                "region_half_extent_m": round(metres_per_unit, 3),
                "road_speed_mps": self.args.road_speed,
                "n_boundary_points": len(boundary)}

    # -- candidate selection -------------------------------------------------
    def remaining_path(self, tc, veh):
        """(polyline from here, metres to the planning-box exit, exit point)."""
        route = list(tc.vehicle.getRoute(veh))
        idx = tc.vehicle.getRouteIndex(veh)
        pts = self.geom.polyline(route[idx:])
        if len(pts) < 2:
            return None, 0.0, None
        x, y = tc.vehicle.getPosition(veh)
        cum = cumulative(pts)
        best_i, best_d = 0, float("inf")
        for i, (px, py) in enumerate(pts):
            d = (px - x) ** 2 + (py - y) ** 2
            if d < best_d:
                best_i, best_d = i, d
        s0 = cum[best_i]
        # Upstream rejects goals outside the robot's workspace, so stop at the last
        # point still inside the box (BOX_EDGE = 0.90) instead of at |q| = 1.
        exit_i = None
        for i in range(best_i, len(pts)):
            qx, qy = self.frame.to_frame(*pts[i])
            if max(abs(qx), abs(qy)) > BOX_EDGE:
                exit_i = max(i - 1, best_i)
                break
        if exit_i is None or exit_i <= best_i:
            return None, 0.0, None
        return pts[best_i:exit_i + 1], cum[exit_i] - s0, pts[exit_i]

    def candidates(self, tc):
        out = []
        for veh in tc.vehicle.getIDList():
            if veh in self.released:
                continue
            pts, rem, exit_pt = self.remaining_path(tc, veh)
            if pts is None or exit_pt is None:
                continue
            if rem > self.args.commit_window:
                continue
            x, y = tc.vehicle.getPosition(veh)
            qx, qy = self.frame.to_frame(x, y)
            if max(abs(qx), abs(qy)) > BOX_EDGE:  # outside the prior's workspace
                continue
            out.append((veh, pts, rem, exit_pt))
        return out

    # -- one planning call ---------------------------------------------------
    def plan_group(self, tc, group, planners_factory):
        from mmd.common.conflicts import PointConflict
        from mmd.common.constraints import MultiPointConstraint
        from mmd.planners.multi_agent import CBS

        tensor_args = {"device": torch.device(self.args.device),
                       "dtype": torch.float32}
        reference_robot_radius = prior.ROBOT_RADIUS
        planners, starts, goals, kept = [], [], [], []
        for veh, pts, rem, exit_pt in group:
            x, y = tc.vehicle.getPosition(veh)
            sx, sy = self.frame.to_frame(x, y)
            gx, gy = self.frame.to_frame(*exit_pt)
            if math.hypot(gx - sx, gy - sy) < 0.05:
                continue
            start = torch.tensor([sx, sy], **tensor_args)
            goal = torch.tensor([gx, gy], **tensor_args)
            try:
                planners.append(planners_factory(start, goal))
            except Exception as exc:                      # noqa: BLE001
                self.fallbacks.append({"veh": veh, "reason": "planner:%s" % exc})
                continue
            starts.append(start)
            goals.append(goal)
            kept.append((veh, pts, rem))
        if not kept:
            return kept, None, 0.0, None

        # Two agents that share a goal point are in collision *by construction* at
        # the final plan step, which upstream rejects as an invalid problem.
        # Keep the first arrival and let the next epoch plan the rest.
        r2 = (2.0 * float(reference_robot_radius)) ** 2
        keep_i = []
        for i, g in enumerate(goals):
            if all(float(((g - goals[j]) ** 2).sum()) > r2 for j in keep_i):
                keep_i.append(i)
        if len(keep_i) < len(goals):
            dropped = [kept[i][0] for i in range(len(kept)) if i not in keep_i]
            self.fallbacks.append({"veh": dropped, "reason": "goal_conflict"})
            planners = [planners[i] for i in keep_i]
            starts = [starts[i] for i in keep_i]
            goals = [goals[i] for i in keep_i]
            kept = [kept[i] for i in keep_i]
        if not kept:
            return [], None, 0.0, None

        reference = planners[0]
        if os.environ.get('DSIP_DEBUG_SHAPES'):
            print('DEBUG starts', [tuple(s.shape) for s in starts],
                  'goals', [tuple(g.shape) for g in goals],
                  'vals', [s.tolist() for s in starts],
                  [g.tolist() for g in goals])
        try:
            cbs = CBS(planners, starts, goals,
                      is_xcbs=True, is_ecbs=True,
                      conflict_type_to_constraint_types={
                          PointConflict: {MultiPointConstraint}},
                      reference_robot=reference.robot,
                      reference_task=reference.task)
        except Exception as exc:                          # noqa: BLE001
            self.fallbacks.append({"veh": [k[0] for k in kept],
                                   "reason": "cbs_init:%s" % exc})
            return kept, None, 0.0, None
        t0 = time.time()
        try:
            paths, n_exp, status, n_conf = cbs.plan(
                runtime_limit=self.args.cbs_timeout)
        except Exception as exc:                          # noqa: BLE001
            self.fallbacks.append({"veh": [k[0] for k in kept],
                                   "reason": "cbs:%s" % exc})
            return kept, None, time.time() - t0, None
        return kept, paths, time.time() - t0, (n_exp, str(status), n_conf)



    # -- execution -----------------------------------------------------------
    def apply_plans(self, tc):
        now = tc.simulation.getTime()
        for veh, plan in list(self.plans.items()):
            if veh in self.released or veh not in tc.vehicle.getIDList():
                self.plans.pop(veh, None)
                continue
            k = int((now - plan["t0"]) / PLAN_DT)
            if k < 0:
                continue
            if k >= len(plan["s"]):
                self.plans.pop(veh, None)
                tc.vehicle.setSpeed(veh, -1)
                continue
            s = plan["s"][k]
            x, y = point_at(plan["pts"], plan["cum"], s * plan["L"])
            nxt = point_at(plan["pts"], plan["cum"],
                           min(s * plan["L"] + 0.5, plan["L"]))
            angle = math.degrees(math.atan2(nxt[1] - y, nxt[0] - x))
            tc.vehicle.moveToXY(veh, "", -1, x, y, angle, keepRoute=2)
            tc.vehicle.setSpeed(veh, -1)

    def release(self, tc, veh, reason):
        self.plans.pop(veh, None)
        self.released.add(veh)
        self.fallbacks.append({"veh": veh, "reason": reason})


def run(args):
    """Main SUMO loop. Returns a run record dict."""
    import traci

    out = Path(args.out)
    out = out if out.is_absolute() else ROOT / out
    out.mkdir(parents=True, exist_ok=True)

    runner = DSIPRunner(args)
    cmd = ["sumo", "-n", str(args.net), "-r", str(args.rou),
           "-a", str(args.typ), "--begin", "0", "--end", str(args.end),
           "--step-length", "0.1", "--seed", str(args.seed),
           "--no-step-log", "true", "--collision.action", "warn",
           "--collision.mingap-factor", "0.5",
           "--tripinfo-output", str(out / "tripinfo.xml"),
           "--log", str(out / "sumo.log")]
    (out / "sumo_command.txt").write_text(" ".join(cmd) + "\n")
    console = open(out / "sumo_console.log", "w")
    traci.start(cmd, stdout=console)

    cache = {}

    def planners_factory(start, goal):
        key = (round(float(start[0]), 4), round(float(start[1]), 4),
               round(float(goal[0]), 4), round(float(goal[1]), 4))
        if not args.planner_cache or key not in cache:
            cache[key] = prior.build_mpd(start, goal, device=args.device,
                                         seed=args.seed,
                                         torch_compile=args.torch_compile)
        return cache[key]

    frame_info = None
    t_wall0 = time.time()
    sim_reached = 0.0
    try:
        frame_info = runner.build_frame(tc=traci, junction_id=args.junction)
        next_plan_t = 0.0
        while traci.simulation.getTime() < args.end:
            traci.simulationStep()
            now = traci.simulation.getTime()
            sim_reached = now
            runner.apply_plans(traci)
            if now + 1e-9 >= next_plan_t:
                next_plan_t = now + args.epoch
                group = [g for g in runner.candidates(traci)
                         if g[0] not in runner.plans][:args.max_agents]
                if group:
                    kept, paths, wall, info = runner.plan_group(
                        traci, group, planners_factory)
                    rec = {"sim_time": now, "n_agents": len(kept),
                           "wall_s": round(wall, 4),
                           "over_budget": bool(wall > args.budget),
                           "solved": paths is not None}
                    if info is not None:
                        rec.update({"ct_expansions": info[0],
                                    "status": info[1],
                                    "conflicts_left": info[2]})
                    runner.records.append(rec)
                    if paths is not None:
                        for (veh, pts, rem), path in zip(kept, paths):
                            runner.plans[veh] = {
                                "s": progress_curve(path), "t0": now,
                                "pts": pts, "cum": cumulative(pts), "L": rem}
                            runner.n_planned_vehicles += 1
                    else:
                        for veh, _pts, _rem in kept:
                            runner.release(traci, veh, "no_solution")
            if args.max_wall and time.time() - t_wall0 > args.max_wall:
                break
    finally:
        traci.close()

    walls = [r["wall_s"] for r in runner.records]
    record = {
        "stage": "S3",
        "mode": "paper_faithful",
        "net": Path(args.net).name,
        "rou": Path(args.rou).name,
        "seed": args.seed,
        "end_s": args.end,
        "sim_time_reached_s": round(sim_reached, 2),
        "epoch_s": args.epoch,
        "commit_window_m": args.commit_window,
        "max_agents": args.max_agents,
        "budget_s": args.budget,
        "cbs_timeout_s": args.cbs_timeout,
        "frame": frame_info,
        "n_calls": len(runner.records),
        "n_solved": sum(1 for r in runner.records if r["solved"]),
        "n_over_budget": sum(1 for r in runner.records if r["over_budget"]),
        "n_planned_vehicles": runner.n_planned_vehicles,
        "n_released_vehicles": len(runner.released),
        "n_fallbacks": len(runner.fallbacks),
        "wall_mean_s": round(sum(walls) / len(walls), 4) if walls else None,
        "wall_p50_s": round(sorted(walls)[len(walls) // 2], 4) if walls else None,
        "wall_max_s": round(max(walls), 4) if walls else None,
        "total_planning_wall_s": round(sum(walls), 2),
        "real_time_factor": (round(sum(walls) / sim_reached, 3)
                             if sim_reached else None),
    }
    record.update(traffic_metrics(out))
    (out / "s3_report.json").write_text(json.dumps(record, indent=2))
    (out / "s3_calls.json").write_text(json.dumps(runner.records, indent=1))
    (out / "s3_fallbacks.json").write_text(json.dumps(runner.fallbacks, indent=1))
    return record

def traffic_metrics(out):
    """Paper-style aggregates from tripinfo.xml and the SUMO warning log."""
    loss, dur, spd = [], [], []
    trip_path = Path(out) / "tripinfo.xml"
    try:
        root = ET.parse(str(trip_path)).getroot()
        for ti in root.findall("tripinfo"):
            try:
                loss.append(float(ti.get("timeLoss")))
                dur.append(float(ti.get("duration")))
                spd.append(float(ti.get("routeLength")) / max(float(ti.get("duration")), 1e-6))
            except (TypeError, ValueError):
                continue
    except Exception:                                     # noqa: BLE001
        pass
    near, emg, inserts = 0, 0, 0
    log_path = Path(out) / "sumo.log"
    if log_path.exists():
        for line in log_path.read_text(errors="ignore").splitlines():
            if "collision with vehicle" in line and "gap=" in line:
                near += 1
            elif "emergency braking" in line:
                emg += 1
            elif line.startswith("Inserted:"):
                try:
                    inserts = int(line.split()[1])
                except (IndexError, ValueError):
                    pass
    n = len(loss)
    return {
        "n_trips": n,
        "time_loss_per_vehicle_mean_s": round(sum(loss) / n, 3) if n else None,
        "duration_mean_s": round(sum(dur) / n, 3) if n else None,
        "speed_from_route_mean_mps": round(sum(spd) / n, 3) if n else None,
        "proximity_events_lt1p5m": near,
        "emergency_braking_events": emg,
        "n_inserted": inserts,
    }
