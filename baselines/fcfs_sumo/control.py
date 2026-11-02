#!/usr/bin/env python3
"""FCFS real-control execution mode -- MINIMAL, ADDITIVE.

This module adds vehicle actuation (``setStop`` / ``resume``) on top of the
already-validated shadow modules.  It does **not** modify ``conflicts.py``,
``tracker.py``, ``queue.py`` or ``shadow.py``; those keep their existing
(read-only, no-actuation) semantics.

It implements the values approved in ``docs/decisions/fcfs-parameters.md``:

    D1  DT_SAFE      = 2.0 s      (= vType tau in scenarios/original/types.typ.xml)
    D2  L_ACZ        = 28.0 m     (= v_max * DT_SAFE = 13.9 * 2.0)
    D3  resource     = internal via lanes  UNION  exit lanes
    D4  clear test   = observed empty  AND  (now >= release + DT_SAFE)
    D5  actuation    = setStop at stop-line - 2 m / resume on grant
    D6  step length  = 0.1 s      (command-line override, no new .sumocfg)
    D7  ETA          = t + d / max(v, 1.0), floored by t + d / v_max (diagnostic)

Usage (from the repository root):

    python3 -m baselines.fcfs_sumo.control
    python3 -m baselines.fcfs_sumo.control --end 100 --seed 81890

Outputs go to ``results/fcfs_control/`` (git-ignored, regenerable).
"""

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from baselines.fcfs_sumo.conflicts import ConflictModel   # noqa: E402

# --- approved parameters (docs/decisions/fcfs-parameters.md) ---------------
DT_SAFE = 2.0                    # s   D1
L_ACZ = 28.0                     # m   D2
STOP_OFFSET = 2.0                # m   stop this far before the approach lane end
V_MAX = 13.9                     # m/s from types.typ.xml
MERGE_CLEAR = V_MAX * DT_SAFE    # m   exit-lane merge window (~27.8 m)
STEP = 0.1                       # s   D6
OUT_DIR = ROOT / "results" / "fcfs_control"

NET = "scenarios/original/cross3.net.xml"
ROU = "scenarios/original/routes.rou.xml"
TYP = "scenarios/original/types.typ.xml"


class ResourceMap:
    """D3: one movement -> the set of lanes it must reserve."""

    def __init__(self, model):
        self.res = {}
        self.exit_lanes = set()
        for m in model.movements:
            to_lanes = {"%s_%d" % (m["to_edge"], i) for i in m["to_lanes"]}
            self.exit_lanes |= to_lanes
            self.res[m["index"]] = set(m["vias"]) | to_lanes
        self.approach_edges = {m["from_edge"] for m in model.movements}

    def of(self, movement_index):
        return self.res[movement_index]


class Controller:
    """FCFS-by-resource admission control with setStop / resume actuation."""

    def __init__(self, model, resources, traci_):
        self.model = model
        self.rm = resources
        self.tc = traci_
        self.request_time = {}     # vid -> time at ACZ entry (frozen)
        self.granted = {}          # vid -> movement index
        self.entered = set()       # vids observed inside a junction
        self.stopped = set()       # vids we issued setStop for
        self.pending_resume = set()  # granted but stop not reached yet
        self.reserved = {}         # lane -> vid
        self.release = {}          # lane -> earliest re-use time
        self.too_close = 0
        self.events = []

    # ---- helpers ------------------------------------------------------
    def _dist_to_stop(self, vid):
        lane = self.tc.vehicle.getLaneID(vid)
        return self.tc.lane.getLength(lane) - self.tc.vehicle.getLanePosition(vid)

    def _lane_busy(self, lane, me, now):
        if now < self.release.get(lane, -1.0):
            return True
        owner = self.reserved.get(lane)
        if owner is not None and owner != me:
            return True
        for v in self.tc.lane.getLastStepVehicleIDs(lane):
            if v == me:
                continue
            if lane in self.rm.exit_lanes:
                if self.tc.vehicle.getLanePosition(v) < MERGE_CLEAR:
                    return True
            else:
                return True
        return False

    def _free(self, vid, mi, now):
        return not any(self._lane_busy(l, vid, now) for l in self.rm.of(mi))

    def _refresh_reservations(self, active):
        """Drop reservations of vehicles that already cleared their lanes."""
        now = self.tc.simulation.getTime()
        for lane, vid in list(self.reserved.items()):
            if vid not in active:
                self.reserved.pop(lane, None)
                self.release[lane] = now + DT_SAFE
                continue
            if vid not in self.entered:
                continue                      # still approaching: keep it
            road = self.tc.vehicle.getRoadID(vid)
            if lane == road:
                if lane not in self.rm.exit_lanes:
                    continue                  # still on the via lane
                if self.tc.vehicle.getLanePosition(vid) < MERGE_CLEAR:
                    continue                  # still inside the merge window
            self.reserved.pop(lane, None)
            self.release[lane] = now + DT_SAFE

    def _try_resume(self, vid, now):
        """resume() only works once the vehicle has actually reached the stop."""
        try:
            self.tc.vehicle.resume(vid)
        except Exception:
            self.pending_resume.add(vid)      # retry next step (<= 0.1 s later)
            return
        self.pending_resume.discard(vid)
        self.events.append(("resume", now, vid))

    def _stop_at_line(self, vid):
        """Try to hold vid at the stop line.  Returns True if it is now held."""
        if vid in self.stopped:
            return True
        edge = self.tc.vehicle.getRoadID(vid)
        lane_i = self.tc.vehicle.getLaneIndex(vid)
        lane_len = self.tc.lane.getLength("%s_%d" % (edge, lane_i))
        pos = lane_len - STOP_OFFSET
        if self.tc.vehicle.getLanePosition(vid) >= pos - 1.0:
            self.too_close += 1
            self.stopped.add(vid)
            self.events.append(("too_close", self.tc.simulation.getTime(), vid))
            return False
        try:
            self.tc.vehicle.setStop(vid, edge, pos=pos, laneIndex=lane_i)
        except Exception:                     # SUMO refuses: "too close to brake"
            self.too_close += 1
            self.stopped.add(vid)
            self.events.append(("too_close", self.tc.simulation.getTime(), vid))
            return False
        self.stopped.add(vid)
        self.events.append(("stop", self.tc.simulation.getTime(), vid))
        return True

    # ---- one simulation step -----------------------------------------
    def step(self):
        tc = self.tc
        tc.simulationStep()
        now = tc.simulation.getTime()
        active = set(tc.vehicle.getIDList())
        for v in active:
            if tc.vehicle.getRoadID(v).startswith(":"):
                self.entered.add(v)
        self._refresh_reservations(active)

        # 1) ACZ request registration (D2): first time inside L_ACZ
        waiting = []
        for vid in active:
            if vid in self.granted:
                continue
            edge = tc.vehicle.getRoadID(vid)
            if edge.startswith(":") or edge not in self.rm.approach_edges:
                continue
            mi = self.model.index_of_route(tc.vehicle.getRouteID(vid))
            if mi is None:
                continue
            if self._dist_to_stop(vid) <= L_ACZ:
                self.request_time.setdefault(vid, now)
                waiting.append((self.request_time[vid], vid, mi))

        # 2) FCFS admission (D8: key = (request_time, vehicle_id))
        for _, vid, mi in sorted(waiting):
            if self._free(vid, mi, now):
                for lane in self.rm.of(mi):
                    self.reserved.setdefault(lane, vid)
                self.granted[vid] = mi
                if vid in self.stopped:
                    self._try_resume(vid, now)
            elif not self._stop_at_line(vid):
                # cannot be held any more -> forced through; record it honestly
                for lane in self.rm.of(mi):
                    self.reserved.setdefault(lane, vid)
                self.granted[vid] = mi
                self.events.append(("forced", now, vid))

        # 3) retry releases that were blocked before the stop was reached
        for vid in list(self.pending_resume):
            if vid not in active:
                self.pending_resume.discard(vid)
            else:
                self._try_resume(vid, now)


def _collisions(tc):
    """Return collision records for the last step (traci>=1.14) or []."""
    try:
        return list(tc.simulation.getCollisions())
    except Exception:                                    # pragma: no cover
        return []


def _collision_dict(c, now):
    """Normalise a traci Collision namedtuple; field names vary by version."""
    def g(*names):
        for n in names:
            v = getattr(c, n, None)
            if v is not None:
                return v
        return ""
    return {"time": round(float(now), 2),
            "lane": g("lane", "laneID"),
            "victim": g("victim", "victimID"),
            "other": g("collider", "colliderID", "other")}


def _count_episodes(collisions, gap=0.5):
    """traci reports one record per step while two vehicles overlap; group them."""
    episodes, last = [], {}
    for c in sorted(collisions, key=lambda d: d["time"]):
        key = (c["lane"], c["victim"], c["other"])
        prev = last.get(key)
        if prev is None or c["time"] - prev > gap:
            episodes.append(c)
        last[key] = c["time"]
    return episodes


def run(end_time=100.0, seed=81890, control=True):
    import traci

    model = ConflictModel()
    rm = ResourceMap(model)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    cmd = ["sumo", "-n", NET, "-r", ROU, "-a", TYP,
           "--begin", "0", "--end", str(end_time),
           "--step-length", str(STEP), "--seed", str(seed),
           "--no-step-log", "true", "--no-warnings", "true",
           "--collision.action", "warn", "--duration-log.statistics", "true"]
    print("=" * 78)
    print("FCFS REAL-CONTROL run   (D1-D8 from docs/decisions/fcfs-parameters.md)")
    print("=" * 78)
    print("cmd      :", " ".join(cmd))
    print("control  :", "ON" if control else "OFF (baseline)")
    print("DT_SAFE  :", DT_SAFE, "s     L_ACZ:", L_ACZ, "m     MERGE_CLEAR:",
          round(MERGE_CLEAR, 2), "m")
    print("resources: %d movements, %d distinct exit lanes"
          % (len(model.movements), len(rm.exit_lanes)))
    print("-" * 78)

    traci.start(cmd)
    ctrl = Controller(model, rm, traci) if control else None
    collisions = []
    try:
        steps = int(round(end_time / STEP))
        for _ in range(steps):
            if ctrl:
                ctrl.step()
            else:
                traci.simulationStep()
            now = traci.simulation.getTime()
            for c in _collisions(traci):
                collisions.append(_collision_dict(c, now))
    finally:
        traci.close()

    out = {
        "seed": seed,
        "end_time": end_time,
        "step_length": STEP,
        "control": control,
        "params": {"DT_SAFE": DT_SAFE, "L_ACZ": L_ACZ,
                   "MERGE_CLEAR": MERGE_CLEAR,
                   "STOP_OFFSET": STOP_OFFSET, "STEP": STEP},
        "n_collisions": len(_count_episodes(collisions)),
        "n_collision_records": len(collisions),
        "collision_episodes": _count_episodes(collisions),
        "collisions": collisions,
        "n_requests": len(ctrl.request_time) if ctrl else 0,
        "n_granted": len(ctrl.granted) if ctrl else 0,
        "n_stopped": len(ctrl.stopped) if ctrl else 0,
        "n_too_close": ctrl.too_close if ctrl else 0,
        "n_forced": (sum(1 for e in ctrl.events if e[0] == "forced") if ctrl else 0),
        "events": (ctrl.events if ctrl else []),
    }
    tag = "control" if control else "baseline"
    json_path = OUT_DIR / ("run_%s_seed%d.json" % (tag, seed))
    json_path.write_text(json.dumps(out, indent=2), encoding="utf-8")

    csv_path = OUT_DIR / ("events_%s_seed%d.csv" % (tag, seed))
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["action", "time", "vehicle_id"])
        w.writerows(out["events"])

    print("collisions (episodes) :", out["n_collisions"],
          "  [%d per-step records]" % out["n_collision_records"])
    for c in out["collision_episodes"]:
        print("   t=%6.2f lane=%-16s %s vs %s"
              % (c["time"], c["lane"], c["victim"], c["other"]))
    if ctrl:
        print("requests / granted    : %d / %d" % (out["n_requests"], out["n_granted"]))
        print("vehicles held at line :", out["n_stopped"])
        print("too-close / forced    : %d / %d" % (out["n_too_close"], out["n_forced"]))
    print("artefacts             :", json_path.name, "/", csv_path.name)
    print("=" * 78)
    return out


def main():
    ap = argparse.ArgumentParser(description="FCFS real-control execution mode")
    ap.add_argument("--end", type=float, default=100.0, help="simulation end (s)")
    ap.add_argument("--seed", type=int, default=81890)
    ap.add_argument("--baseline", action="store_true",
                    help="run without control (same seed) for A/B comparison")
    a = ap.parse_args()
    run(end_time=a.end, seed=a.seed, control=not a.baseline)


if __name__ == "__main__":
    main()
