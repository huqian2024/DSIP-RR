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
HEAD_LOOKAHEAD = 12.0           # m   a vehicle with a leader closer than this on
                                #     its lane is NOT the lane head, so it is left
                                #     to IDM car-following instead of being stopped
GRANT_TIMEOUT = 5.0             # s   implementation guard: a grant that has not
                                #     produced a junction entry within this time is
                                #     revoked, so no vehicle can hold a resource it
                                #     cannot use (D8 "no hold-and-wait").  Not a
                                #     research parameter: 5 s = 2.5 x (L_ACZ / v_max).
STEP = 0.1                       # s   D6
OUT_DIR = ROOT / "results" / "fcfs_control"

NET = "scenarios/original/cross3.net.xml"
ROU = "scenarios/original/routes.rou.xml"
TYP = "scenarios/original/types.typ.xml"


class ResourceMap:
    """D3: one movement -> the set of lanes it must reserve.

    ``granularity``
      ``"movement"`` (default) reserve **every** lane of the movement, i.e. all
      six lanes of a three-lane straight movement even though one vehicle
      traverses only one via lane and one exit lane.  Safety-wise this adds
      nothing (the extra lanes are never entered); it only lowers throughput.
      Kept as the default because it is the granularity approved on
      2026-11-02 and the author asked for it to be preserved.

      ``"lane"`` reserve only the ``via`` lane and the exit lane that the
      vehicle will actually traverse, resolved from the SUMO ``connection``
      table by its current approach-lane index.  This is the closer analogue
      of cell/path reservation in Dresner--Stone / AIM4.
    """

    def __init__(self, model, granularity="movement"):
        self.granularity = granularity
        self.movements = model.movements
        self.res = {}
        self.exit_lanes = set()
        self.lookup = {}
        for m in model.movements:
            to_lanes = {"%s_%d" % (m["to_edge"], i) for i in m["to_lanes"]}
            self.exit_lanes |= to_lanes
            self.res[m["index"]] = set(m["vias"]) | to_lanes
        for c in model.connections:
            self.lookup[(c["from"], c["to"], c["fromLane"])] = (
                c["via"], c["toLane"])
        self.approach_edges = {m["from_edge"] for m in model.movements}

    def of(self, movement_index, approach_lane=None):
        if self.granularity == "lane" and approach_lane is not None:
            m = self.model_movement(movement_index)
            hit = self.lookup.get((m["from_edge"], m["to_edge"], approach_lane))
            if hit:
                via, to_lane = hit
                return {via, "%s_%d" % (m["to_edge"], to_lane)}
        return self.res[movement_index]

    def model_movement(self, movement_index):
        return self.movements[movement_index]



class Controller:
    """FCFS-by-resource admission control with setStop / resume actuation."""

    def __init__(self, model, resources, traci_, queue_guard=False):
        self.model = model
        self.rm = resources
        self.tc = traci_
        self.queue_guard = queue_guard
        self.request_time = {}     # vid -> time at ACZ entry (frozen)
        self.granted = {}          # vid -> movement index
        self.grant_time = {}       # vid -> time the grant was issued
        self.revoked = 0
        self.grant_count = 0       # cumulative grants issued (not the final dict size)
        self.entered = set()       # vids observed inside a junction
        self.stopped = set()       # vids we issued setStop for
        self.pending_resume = set()  # granted but stop not reached yet
        self.reserved = {}         # lane -> vid
        self.touched = set()       # (vid, lane) pairs the vehicle has reached
        self.release = {}          # lane -> earliest re-use time
        self.too_close = 0
        self.events = []
        self._lane_len = {}
        self._route_idx = {}

    # ---- helpers ------------------------------------------------------
    def _dist_to_stop(self, vid):
        lane = self.tc.vehicle.getLaneID(vid)
        if lane not in self._lane_len:
            self._lane_len[lane] = self.tc.lane.getLength(lane)
        return self._lane_len[lane] - self.tc.vehicle.getLanePosition(vid)

    def _movement_of(self, vid):
        rid = self.tc.vehicle.getRouteID(vid)
        if rid not in self._route_idx:
            self._route_idx[rid] = self.model.index_of_route(rid)
        return self._route_idx[rid]

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

    def _free(self, vid, mi, lane_i, now):
        return not any(self._lane_busy(l, vid, now)
                       for l in self.rm.of(mi, lane_i))

    def _release_lane(self, lane, now):
        """Free a lane.  The exit-lane merge window (MERGE_CLEAR ~= v_max*DT_SAFE)
        already encodes the safety gap, so adding DT_SAFE again would halve
        capacity; the buffer is applied only where occupancy is instantaneous."""
        self.reserved.pop(lane, None)
        self.release[lane] = now + (0.0 if lane in self.rm.exit_lanes else DT_SAFE)

    def _refresh_reservations(self, active):
        """Drop a reservation only once the vehicle has actually passed that lane.

        A vehicle inside the junction has ``roadID`` = ``:center_*``, i.e. it no
        longer matches its exit lane, but it has not merged onto that lane yet.
        Releasing on that basis is what let two merge partners onto the same
        exit lane at the same moment, so a lane is released only after the
        vehicle has actually been observed on it and has cleared the merge
        window.
        """
        now = self.tc.simulation.getTime()
        for lane, vid in list(self.reserved.items()):
            if vid not in active:
                self._release_lane(lane, now)
                continue
            if vid not in self.entered:
                continue                          # still approaching
            road = self.tc.vehicle.getRoadID(vid)
            if lane == road:
                self.touched.add((vid, lane))
                if lane in self.rm.exit_lanes:
                    if self.tc.vehicle.getLanePosition(vid) < MERGE_CLEAR:
                        continue                  # still in the merge window
                else:
                    continue                      # still on the via lane
            elif (vid, lane) not in self.touched:
                continue                          # not reached this lane yet
            self._release_lane(lane, now)

    def _revoke_stale_grants(self, active, now):
        """D8 no hold-and-wait: drop grants that never turned into an entry."""
        if not self.queue_guard:
            return
        for vid, t_grant in list(self.grant_time.items()):
            if vid not in active:
                self.grant_time.pop(vid, None)
                self.granted.pop(vid, None)
                continue
            if vid in self.entered or now - t_grant <= GRANT_TIMEOUT:
                continue
            self.grant_time.pop(vid, None)
            self.granted.pop(vid, None)
            self.revoked += 1
            for lane, owner in list(self.reserved.items()):
                if owner == vid:
                    self.reserved.pop(lane, None)
                    self.release[lane] = now + DT_SAFE
            self.events.append(("revoked", now, vid))

    def _blocked_by_leader(self, vid):
        """True if a non-granted vehicle is queued directly ahead of vid."""
        if not self.queue_guard:
            return False
        lead = self.tc.vehicle.getLeader(vid, 30.0)
        if lead is None:
            return False
        lead_id, dist = lead
        if lead_id in self.granted:
            return False                      # it is already moving on
        return dist < 10.0

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
        self._revoke_stale_grants(active, now)

        # 1) ACZ request registration (D2): first time inside L_ACZ
        #    Only the HEAD of each approach lane is admitted or stopped; every
        #    vehicle behind it is queued by SUMO's IDM.  Stopping followers as
        #    well produced most of the "too close to brake" / forced admissions
        #    and let a grant sit on a resource that the vehicle could not use.
        waiting = []
        for vid in active:
            if vid in self.granted:
                continue
            edge = tc.vehicle.getRoadID(vid)
            if edge.startswith(":") or edge not in self.rm.approach_edges:
                continue
            mi = self._movement_of(vid)
            if mi is None:
                continue
            if self._dist_to_stop(vid) <= L_ACZ:
                self.request_time.setdefault(vid, now)
                if tc.vehicle.getLeader(vid, HEAD_LOOKAHEAD) is not None:
                    continue                  # not the head of its lane
                waiting.append((self.request_time[vid], vid, mi,
                                tc.vehicle.getLaneIndex(vid)))

        # 2) FCFS admission (D8: key = (request_time, vehicle_id))
        for _, vid, mi, lane_i in sorted(waiting):
            if self._blocked_by_leader(vid):
                self._stop_at_line(vid)
                continue
            if self._free(vid, mi, lane_i, now):
                for lane in self.rm.of(mi, lane_i):
                    self.reserved.setdefault(lane, vid)
                self.granted[vid] = mi
                self.grant_time[vid] = now
                self.grant_count += 1
                if vid in self.stopped:
                    self._try_resume(vid, now)
            elif not self._stop_at_line(vid):
                # cannot be held any more -> forced through; record it honestly
                for lane in self.rm.of(mi, lane_i):
                    self.reserved.setdefault(lane, vid)
                self.granted[vid] = mi
                self.grant_time[vid] = now
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


def run(end_time=100.0, seed=81890, control=True, granularity="movement",
        net=NET, flows=ROU, quiet=False, queue_guard=False):
    import traci

    model = ConflictModel(net_path=str(ROOT / net))
    rm = ResourceMap(model, granularity=granularity)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    cmd = ["sumo", "-n", net, "-r", flows, "-a", TYP,
           "--begin", "0", "--end", str(end_time),
           "--step-length", str(STEP), "--seed", str(seed),
           "--no-step-log", "true", "--no-warnings", "true",
           "--collision.action", "warn", "--duration-log.statistics", "true"]
    def say(*a):
        if not quiet:
            print(*a)

    say("=" * 78)
    say("FCFS REAL-CONTROL run   (D1-D8 from docs/decisions/fcfs-parameters.md)")
    say("=" * 78)
    say("cmd      :", " ".join(cmd))
    say("control  :", "ON" if control else "OFF (baseline)")
    say("DT_SAFE  :", DT_SAFE, "s     L_ACZ:", L_ACZ, "m     MERGE_CLEAR:",
        round(MERGE_CLEAR, 2), "m")
    say("granularity:", granularity)
    say("resources: %d movements, %d distinct exit lanes"
        % (len(model.movements), len(rm.exit_lanes)))
    say("-" * 78)

    traci.start(cmd)
    ctrl = Controller(model, rm, traci, queue_guard=queue_guard) if control else None
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
        "granularity": granularity,
        "params": {"DT_SAFE": DT_SAFE, "L_ACZ": L_ACZ,
                   "MERGE_CLEAR": MERGE_CLEAR,
                   "STOP_OFFSET": STOP_OFFSET, "STEP": STEP},
        "n_collisions": len(_count_episodes(collisions)),
        "n_collision_records": len(collisions),
        "collision_episodes": _count_episodes(collisions),
        "collisions": collisions,
        "n_requests": len(ctrl.request_time) if ctrl else 0,
        "n_granted": (ctrl.grant_count if ctrl else 0),
        "n_stopped": len(ctrl.stopped) if ctrl else 0,
        "n_too_close": ctrl.too_close if ctrl else 0,
        "n_forced": (sum(1 for e in ctrl.events if e[0] == "forced") if ctrl else 0),
        "n_revoked": (ctrl.revoked if ctrl else 0),
        "events": (ctrl.events if ctrl else []),
    }
    tag = (("control" if control else "baseline")
           + ("_" + granularity if granularity != "movement" else "")
           + "_" + Path(net).stem + "_" + Path(flows).stem)
    json_path = OUT_DIR / ("run_%s_seed%d.json" % (tag, seed))
    json_path.write_text(json.dumps(out, indent=2), encoding="utf-8")

    csv_path = OUT_DIR / ("events_%s_seed%d.csv" % (tag, seed))
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["action", "time", "vehicle_id"])
        w.writerows(out["events"])

    say("collisions (episodes) :", out["n_collisions"],
        "  [%d per-step records]" % out["n_collision_records"])
    for c in out["collision_episodes"]:
        say("   t=%6.2f lane=%-16s %s vs %s"
            % (c["time"], c["lane"], c["victim"], c["other"]))
    if ctrl:
        say("requests / granted    : %d / %d" % (out["n_requests"], out["n_granted"]))
        say("vehicles held at line :", out["n_stopped"])
        say("too-close / forced    : %d / %d" % (out["n_too_close"], out["n_forced"]))
        say("grants revoked        :", out["n_revoked"])
    say("artefacts             :", json_path.name, "/", csv_path.name)
    print("=" * 78)
    return out


def main():
    ap = argparse.ArgumentParser(description="FCFS real-control execution mode")
    ap.add_argument("--end", type=float, default=100.0, help="simulation end (s)")
    ap.add_argument("--seed", type=int, default=81890)
    ap.add_argument("--granularity", choices=("movement", "lane"),
                    default="movement",
                    help="reservation granularity; the default keeps the "
                         "approved movement-level lane-set reservation")
    ap.add_argument("--baseline", action="store_true",
                    help="run without control (same seed) for A/B comparison")
    ap.add_argument("--queue-guard", action="store_true",
                    help="enable the leader/expiry queue guard (experimental: it "
                         "traded 0 -> 1 collision on the validated 100 s case)")
    ap.add_argument("--net", default=NET,
                    help="SUMO net file (default scenarios/original/cross3.net.xml)")
    ap.add_argument("--flows", default=ROU,
                    help="SUMO route file (default scenarios/original/routes.rou.xml)")
    a = ap.parse_args()
    run(end_time=a.end, seed=a.seed, control=not a.baseline,
        granularity=a.granularity, net=a.net, flows=a.flows,
        queue_guard=a.queue_guard)


if __name__ == "__main__":
    main()
