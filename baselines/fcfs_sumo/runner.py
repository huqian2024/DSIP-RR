#!/usr/bin/env python3
"""FCFS SHADOW controller runner -- read-only, no vehicle actuation.

Connects ``traci`` to ``scenarios/smoke/cross3_smoke.sumocfg`` for 100 simulated
seconds, feeds every step into

    VehicleTracker -> RequestQueue -> ShadowEngine

and writes

    results/fcfs_shadow/vehicle_events.csv
    results/fcfs_shadow/requests.csv
    results/fcfs_shadow/decisions.csv
    results/fcfs_shadow/shadow_summary.json
    results/fcfs_shadow/shadow_run.log   (stdout/stderr of the caller)

It never calls setSpeed / slowDown / setStop / moveTo / moveToXY / changeLane.

Usage (from the repository root):
    python3 -m baselines.fcfs_sumo.runner
"""

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from baselines.fcfs_sumo.conflicts import ConflictModel          # noqa: E402
from baselines.fcfs_sumo.queue import RequestQueue, REQUEST_TIME_BASIS  # noqa: E402
from baselines.fcfs_sumo.shadow import ShadowEngine              # noqa: E402
from baselines.fcfs_sumo.tracker import VehicleTracker           # noqa: E402

CFG_REL = "scenarios/smoke/cross3_smoke.sumocfg"
CFG = str(ROOT / "scenarios" / "smoke" / "cross3_smoke.sumocfg")
OUT_DIR = ROOT / "results" / "fcfs_shadow"
END_TIME = 100.0
MODE_LABEL = "SHADOW_MODE (no vehicle control)"


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})
    return len(rows)


def main():
    import traci

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    model = ConflictModel()
    tracker = VehicleTracker(model)
    queue = RequestQueue(model)
    engine = ShadowEngine(model, tracker, queue)

    print("=" * 78)
    print("FCFS SHADOW MODE run")
    print("=" * 78)
    print("config :", CFG_REL)
    print("end    :", END_TIME, "s")
    print("mode   :", MODE_LABEL)
    print("-" * 78)
    print("movements (from net + routes):")
    for m in model.movements:
        print("  %s %-12s %-13s -> %-13s dir=%s lanes=%s vias=%d"
              % (m["id"], m["route"], m["from_edge"], m["to_edge"], m["dir"],
                 ",".join(map(str, m["from_lanes"])), len(m["vias"])))
    print("conflict matrix symmetric:", model.symmetric)
    print("task03 log cross-check   :", model.task03_check.get("match"),
          "(found=%s, mismatches=%d)" % (model.task03_check.get("found"),
                                         len(model.task03_check.get("mismatches", []))))
    print("-" * 78)

    lane_len_cache = {}

    def lane_length(lane_id):
        if lane_id not in lane_len_cache:
            lane_len_cache[lane_id] = traci.lane.getLength(lane_id)
        return lane_len_cache[lane_id]

    traci.start(["sumo", "-c", CFG, "--no-step-log", "true",
                 "--duration-log.statistics", "true"])
    sumo_version = None
    try:
        sumo_version = traci.getVersion()
        step = 0
        while traci.simulation.getTime() < END_TIME - 1e-9:
            traci.simulationStep()
            step += 1
            t = traci.simulation.getTime()
            snapshot = []
            for vid in traci.vehicle.getIDList():
                snapshot.append({
                    "id": vid,
                    "routeID": traci.vehicle.getRouteID(vid),
                    "roadID": traci.vehicle.getRoadID(vid),
                    "laneID": traci.vehicle.getLaneID(vid),
                    "lanePos": traci.vehicle.getLanePosition(vid),
                    "speed": traci.vehicle.getSpeed(vid),
                    "pos": traci.vehicle.getPosition(vid),
                })
            tracker.update(t, snapshot)
            for (_te, vid, event, _detail) in tracker.events_at(t):
                if event != "first_seen":
                    continue
                rec = tracker.records[vid]
                try:
                    dist = lane_length(rec["first_lane"]) - rec["first_lane_pos"]
                except Exception:
                    dist = None
                queue.request(t, vid, rec["movement_index"], dist, rec["first_speed"])
            engine.step(t)
            if step % 20 == 0:
                print("t=%6.1f s  running=%2d  queued=%2d  inside=%d"
                      % (t, len(snapshot), len(queue),
                         sum(len(v) for v in tracker.movements_inside().values())))
    finally:
        traci.close()

    # ---------------- post-run bookkeeping ---------------------------------
    queue.freeze_ranks()
    enter_events = [e for e in tracker.events if e[2] == "enter"]
    leave_events = [e for e in tracker.events if e[2] == "leave"]
    gone_inside = [e for e in tracker.events if e[2] == "gone_inside"]
    gone_events = [e for e in tracker.events if e[2] == "gone"]
    open_now = sorted(tracker.open_vehicles())

    mov_counts, dir_counts = {}, {}
    for rec in tracker.records.values():
        idx = rec["movement_index"]
        key = model.label(idx) if idx is not None else "?"
        mov_counts[key] = mov_counts.get(key, 0) + 1
        d = model.movement(idx)["dir"] if idx is not None else "?"
        dir_counts[d] = dir_counts.get(d, 0) + 1

    ev_rows = [{"t": t, "vehicle_id": vid, "event": event, "detail": detail,
                "movement": (model.label(tracker.records[vid]["movement_index"])
                             if tracker.records[vid]["movement_index"] is not None
                             else "?")}
               for (t, vid, event, detail) in tracker.events]
    n_ev = write_csv(OUT_DIR / "vehicle_events.csv", ev_rows,
                     ["t", "vehicle_id", "event", "detail", "movement"])

    req_rows = []
    for req in queue.ordered():
        rec = tracker.records.get(req.vehicle_id, {})
        idx = req.movement_index
        req_rows.append({
            "seq": req.seq,
            "vehicle_id": req.vehicle_id,
            "movement": model.label(idx) if idx is not None else "?",
            "dir": model.movement(idx)["dir"] if idx is not None else "?",
            "route": rec.get("route_id"),
            "t_request": req.t_request,
            "request_time_basis": REQUEST_TIME_BASIS,
            "rank_at_request": req.rank_at_request,
            "dist_to_stop_at_request": (round(req.dist_to_stop_at_request, 2)
                                        if req.dist_to_stop_at_request is not None
                                        else ""),
            "speed_at_request": round(req.speed_at_request, 2),
            "eta_constant_speed_diagnostic_only": (
                round(req.eta_constant_speed, 2)
                if req.eta_constant_speed is not None else ""),
            "first_decision": engine.first_decision.get(req.vehicle_id, ""),
            "last_decision_before_entry": engine.last_decision_before_entry.get(
                req.vehicle_id, ""),
            "final_status": engine.status.get(req.vehicle_id, ""),
            "t_enter_actual": rec.get("enter_t", ""),
            "t_leave_actual": rec.get("leave_t", ""),
            "entered_while_blocked": req.vehicle_id in engine.entered_while_blocked,
            "entered_while_undetermined":
                req.vehicle_id in engine.entered_while_undetermined,
            "hard_conflict_at_entry": "|".join(
                engine.hard_conflict_at_entry.get(req.vehicle_id, [])),
            "n_steps_observed": rec.get("n_samples", 0),
        })
    n_req = write_csv(OUT_DIR / "requests.csv", req_rows,
                      list(req_rows[0].keys()) if req_rows else ["seq"])

    n_dec = write_csv(OUT_DIR / "decisions.csv", engine.history,
                      ["t", "seq", "vehicle_id", "movement", "previous", "status",
                       "resource_state", "blocking_movements", "reason"])

    checks = {
        "all_12_movements_in_model": len(model.movements) == 12,
        "movements_observed": ",".join(sorted(mov_counts)),
        "all_movements_observed": len(mov_counts) == len(model.movements),
        "n_vehicles_tracked": len(tracker.records),
        "n_requests": len(queue),
        "one_request_per_vehicle": len(queue.duplicate_attempts) == 0,
        "duplicate_request_attempts": len(queue.duplicate_attempts),
        "priority_order_stable": queue.order_changes == 0,
        "order_changes_detected": queue.order_changes,
        "n_enter_events": len(enter_events),
        "n_leave_events": len(leave_events),
        "n_open_at_end": len(open_now),
        "enter_leave_pairing_ok": len(enter_events) == len(leave_events) + len(open_now),
        "gone_while_inside": len(gone_inside),
        "n_gone_events": len(gone_events),
        "invalid_state_transitions": len(engine.invalid_transitions),
        "conflict_matrix_symmetric": model.symmetric,
        "task03_matrix_match": model.task03_check.get("match"),
        "entered_while_BLOCKED": len(engine.entered_while_blocked),
        "entered_while_UNDETERMINED": len(engine.entered_while_undetermined),
    }

    summary = {
        "mode": MODE_LABEL,
        "not_a_performance_experiment": True,
        "config": CFG_REL,
        "end_time": END_TIME,
        "sumo_version_reported_by_traci": sumo_version,
        "n_steps": step,
        "conflict_model": model.summary(),
        "movement_distribution": mov_counts,
        "direction_distribution": dir_counts,
        "requests": {
            "request_time_basis": REQUEST_TIME_BASIS,
            "warning": "proxy request time (first observation on an approach) is "
                       "NOT the Dresner-Stone request time; the control-zone "
                       "definition has not been fixed",
            "n_requests": len(queue),
            "duplicate_attempts": len(queue.duplicate_attempts),
            "order_changes": queue.order_changes,
        },
        "decisions": {
            "status_rows": len(engine.history),
            "status_counts": engine.status_counts(),
            "invalid_transitions": engine.invalid_transitions[:20],
        },
        "shadow_vs_actual": {
            "n_violations": len(engine.violations),
            "entered_while_BLOCKED": sorted(engine.entered_while_blocked),
            "entered_while_UNDETERMINED": sorted(engine.entered_while_undetermined),
            "note": "shadow mode does not actuate, so divergences are expected and "
                    "are recorded as diagnostics, not as algorithm failures",
        },
        "checks": checks,
        "outputs": {"vehicle_events.csv": n_ev, "requests.csv": n_req,
                    "decisions.csv": n_dec},
    }
    (OUT_DIR / "shadow_summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8")

    print("-" * 78)
    print("vehicles tracked       :", len(tracker.records))
    print("requests queued        : %d (duplicate attempts: %d)"
          % (len(queue), len(queue.duplicate_attempts)))
    print("movement distribution  :", dict(sorted(mov_counts.items())))
    print("direction distribution :", dict(sorted(dir_counts.items())))
    print("enter / leave / open   : %d / %d / %d"
          % (len(enter_events), len(leave_events), len(open_now)))
    print("decision rows          :", len(engine.history))
    print("status counts          :", dict(sorted(engine.status_counts().items())))
    print("invalid transitions    :", len(engine.invalid_transitions))
    print("entered while BLOCKED  :", len(engine.entered_while_blocked))
    print("entered while UNDETERM.:", len(engine.entered_while_undetermined))
    print("-" * 78)
    for key, value in checks.items():
        if isinstance(value, bool):
            print("  [%s] %s" % ("OK  " if value else "FAIL", key))
    print("outputs ->", OUT_DIR)
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
