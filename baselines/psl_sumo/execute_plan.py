"""E1 execution layer: replay a PSL schedule into SUMO.

What it does
------------
Reads ``schedule.csv`` from ``plan_scenario.py`` and drives the same SUMO
scenario with ``setStop`` / ``resume``: every coordinated vehicle is held at its
approach stop line and released so that it crosses at the scheduled time.  This
turns a `schedule_only` artefact into an actual traffic simulation, so the
manuscript's metrics can finally be computed.

Metrics (``paper/submitted/.../main.tex`` section III-B)
-------------------------------------------------------
*Time loss* -- "Following SUMO's standard definition ... ``T_actual - d/v_max``",
and "at each logging step the average time loss is computed over all vehicles
currently active".  We therefore sample, every ``--log-interval`` seconds
(the paper uses 10 s in Figs. 2-4), the mean of SUMO's per-vehicle time loss
over the active fleet, and also aggregate the per-vehicle trip values from
``--tripinfo-output``.

*Average speed* -- "the mean instantaneous speed of all vehicles currently
active in the simulation", sampled the same way; plus ``routeLength/duration``
per vehicle.

*Critical proximity* -- "inter-vehicle gaps below the 1.5 m safety threshold".
Rather than polling every leader every step (20 M TraCI calls per run), SUMO is
started with ``--collision.mingap-factor 0.5``: with ``minGap = 3.0 m`` in
``types.typ.xml`` that makes SUMO itself report an event whenever the gap drops
below 1.5 m.  Real overlaps (gap < 0) are a subset of those.

*Abrupt deceleration* -- "longitudinal deceleration exceeding SUMO's emergency
braking threshold"; SUMO emits these as ``performs emergency braking`` warnings,
which are parsed from the run log (threshold = the vType ``decel``, 4.5 m/s^2).

Execution fidelity
------------------
For every released vehicle the time at which it first appears on an internal
(``:``) edge is recorded, and compared with the scheduled entry.  The deviation
distribution is reported as ``entry_deviation_s`` -- if it is large the schedule
is not executable and the numbers must not be used.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STOP_OFFSET = 3.0          # m, hold this far before the end of the approach lane
RESUME_TOL = 1.5           # m, resume only once the vehicle is this close to its stop


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_schedule(path, paths_by_prefix):
    """vehicle id -> {stopline_time, speed, earliest_arrival, coordinated}."""
    out = {}
    with open(path, newline="") as fh:
        for r in csv.DictReader(fh):
            p = paths_by_prefix.get(r["prefix"])
            if p is None or not p["offsets"]:
                continue                       # conflict-free movement: no gate
            tick = float(r["in_time"])
            speed = float(r["speed"]) or 13.9
            # ``in_time`` is the arrival at trajectory[0] (the first conflict
            # point).  ``offsets[0]`` is that point's distance from the stop
            # line, measured along the path, so the stop-line crossing time is
            # in_time - offsets[0]/speed.
            out[r["vehicle_id"]] = {
                "stopline_time": tick - p["offsets"][0] / speed,
                "planned_entry": tick,
                "speed": speed,
                "earliest_arrival": float(r["earliest_arrival"]),
                "coordinated": r.get("coordinated", "True") == "True",
            }
    return out


def tripinfo_stats(path):
    """Per-vehicle aggregates: time loss, duration, speed (paper Eq. 13-14)."""
    import xml.etree.ElementTree as ET
    loss, dur, spd, dist = [], [], [], []
    try:
        root = ET.parse(str(path)).getroot()
    except Exception:
        return {}
    for ti in root.findall("tripinfo"):
        try:
            loss.append(float(ti.get("timeLoss")))
            d = float(ti.get("duration"))
            s = float(ti.get("routeLength"))
        except (TypeError, ValueError):
            continue
        dur.append(d)
        dist.append(s)
        if d > 0:
            spd.append(s / d)

    def mean(xs):
        return round(sum(xs) / len(xs), 4) if xs else None

    return {"n_trips": len(loss), "mean_time_loss_s": mean(loss),
            "mean_duration_s": mean(dur), "mean_speed_mps": mean(spd),
            "mean_route_length_m": mean(dist)}


def parse_emergency_braking(log_text):
    """SUMO prints one line per event: ``performs emergency braking with decel=...``."""
    hits = []
    for line in log_text.splitlines():
        if "performs emergency braking" in line:
            vid = ""
            if "'" in line:
                vid = line.split("'")[1]
            hits.append({"vehicle": vid, "line": line.strip()[:160]})
    return hits


def collision_episodes(collisions, gap=0.5):
    """Group per-step collision records into events (SUMO repeats while overlapping)."""
    eps, last = [], {}
    for c in sorted(collisions, key=lambda d: d["time"]):
        key = (c["lane"], c["victim"], c["other"])
        prev = last.get(key)
        if prev is None or c["time"] - prev > gap:
            eps.append(c)
        last[key] = c["time"]
    return eps


def _collisions(tc):
    try:
        return list(tc.simulation.getCollisions())
    except Exception:                                    # pragma: no cover
        return []


def _collision_dict(c, now):
    def g(*names):
        for n in names:
            v = getattr(c, n, None)
            if v is not None:
                return v
        return ""
    return {"time": round(float(now), 2), "lane": g("lane", "laneID"),
            "victim": g("victim", "victimID"),
            "other": g("collider", "colliderID", "other")}


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Execute a PSL schedule in SUMO (setStop/resume).",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--net", required=True)
    ap.add_argument("--rou", required=True)
    ap.add_argument("--typ", required=True)
    ap.add_argument("--instance-dir", required=True,
                    help="dir with paths.json (for the stop-line offset)")
    ap.add_argument("--schedule", required=True,
                    help="schedule.csv produced by plan_scenario.py")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--seed", type=int, default=81890)
    ap.add_argument("--end", type=float, default=1000.0)
    ap.add_argument("--step-length", type=float, default=0.1)
    ap.add_argument("--log-interval", type=float, default=10.0,
                    help="sampling interval of the paper's figures (10 s)")
    ap.add_argument("--control", choices=("psl", "none"), default="psl",
                    help="psl = enforce the schedule; none = uncontrolled control")
    ap.add_argument("--mingap-factor", type=float, default=0.5,
                    help="SUMO reports an event when gap < factor * minGap; "
                         "0.5 with minGap 3.0 m == the paper's 1.5 m threshold")
    ap.add_argument("--max-steps", type=int, default=0, help="0 = until --end")
    args = ap.parse_args(argv)

    import traci

    inst = Path(args.instance_dir)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = json.loads((inst / "paths.json").read_text())["paths"]
    paths_by_prefix = {p["prefix"]: p for p in paths}
    sched = load_schedule(args.schedule, paths_by_prefix)
    if args.control == "none":
        sched = {}

    trip = out / "tripinfo.xml"
    cmd = ["sumo", "-n", args.net, "-r", args.rou, "-a", args.typ,
           "--begin", "0", "--end", str(args.end),
           "--step-length", str(args.step_length), "--seed", str(args.seed),
           "--no-step-log", "true", "--duration-log.statistics", "true",
           "--collision.action", "warn",
           "--collision.mingap-factor", str(args.mingap_factor),
           "--tripinfo-output", str(trip),
           "--log", str(out / "sumo.log")]
    (out / "sumo_command.txt").write_text(" ".join(cmd) + "\n")

    sumo_log = open(out / "sumo_console.log", "w")
    traci.start(cmd, stdout=sumo_log)
    tc = traci
    held, released, waiting_entry = set(), set(), {}
    stop_pos = {}                 # vid -> the stop position it was given
    entry_dev, collisions, timeseries, entry_events = [], [], [], []
    seen = set()
    lane_len = {}
    n_stop_fail = 0
    next_log = 0.0
    n_steps = 0

    def stop_at_line(vid):
        nonlocal n_stop_fail
        edge = tc.vehicle.getRoadID(vid)
        if not edge or edge.startswith(":"):
            return False
        lane_i = tc.vehicle.getLaneIndex(vid)
        lid = "%s_%d" % (edge, lane_i)
        if lid not in lane_len:
            lane_len[lid] = tc.lane.getLength(lid)
        pos = lane_len[lid] - STOP_OFFSET
        if tc.vehicle.getLanePosition(vid) >= pos - 1.0:
            n_stop_fail += 1                 # already past: cannot hold it
            return False
        try:
            tc.vehicle.setStop(vid, edge, pos=pos, laneIndex=lane_i)
            stop_pos[vid] = pos
            return True
        except Exception:
            n_stop_fail += 1
            return False

    def try_resume(vid):
        """resume() only succeeds once the vehicle has actually reached its stop.

        Retrying blindly makes SUMO answer "Failed to resume ... reached: 0" on
        every step for every held vehicle, flooding the log and adding a round
        trip per vehicle per step (same defect as FCFS D-03).  The retry is
        therefore gated on the vehicle having arrived at its stop.
        """
        target = stop_pos.get(vid)
        if target is not None:
            if tc.vehicle.getLanePosition(vid) < target - RESUME_TOL:
                return False
        try:
            tc.vehicle.resume(vid)
            return True
        except Exception:
            return False

    try:
        while True:
            tc.simulationStep()
            n_steps += 1
            now = tc.simulation.getTime()
            if args.max_steps and n_steps >= args.max_steps:
                break
            if now > args.end:
                break
            for c in _collisions(tc):
                collisions.append(_collision_dict(c, now))

            active = tc.vehicle.getIDList()
            seen.update(active)
            for vid in active:
                row = sched.get(vid)
                if row is None or vid in released:
                    continue
                if now >= row["stopline_time"]:
                    if vid in held:
                        if try_resume(vid):
                            held.discard(vid)
                            stop_pos.pop(vid, None)
                            released.add(vid)
                            row["released_at"] = now
                            row["was_held"] = True
                            waiting_entry[vid] = row
                    else:
                        released.add(vid)
                        row["released_at"] = now
                        row["was_held"] = False
                        waiting_entry[vid] = row
                elif vid not in held:
                    if stop_at_line(vid):
                        held.add(vid)
                        row["held_at"] = now

            for vid in list(waiting_entry):
                if vid not in active:
                    waiting_entry.pop(vid, None)
                    continue
                if tc.vehicle.getRoadID(vid).startswith(":"):
                    row = waiting_entry.pop(vid)
                    entered = now
                    entry_dev.append(round(entered - row["planned_entry"], 3))
                    entry_events.append({
                        "vehicle_id": vid,
                        "planned_entry_s": round(row["planned_entry"], 3),
                        "stopline_time_s": round(row["stopline_time"], 3),
                        "released_at_s": round(row.get("released_at", float("nan")), 3),
                        "entered_at_s": round(entered, 3),
                        "deviation_s": round(entered - row["planned_entry"], 3),
                        "was_held": row.get("was_held", False),
                    })

            if now + 1e-9 >= next_log:
                speeds, losses = [], []
                for vid in active:
                    try:
                        speeds.append(tc.vehicle.getSpeed(vid))
                        losses.append(tc.vehicle.getTimeLoss(vid))
                    except Exception:
                        continue
                timeseries.append({
                    "time_s": round(now, 2),
                    "n_active": len(active),
                    "mean_speed_mps": round(sum(speeds) / len(speeds), 4)
                    if speeds else None,
                    "mean_time_loss_s": round(sum(losses) / len(losses), 4)
                    if losses else None,
                    "n_arrived": tc.simulation.getArrivedNumber(),
                    "n_departed": tc.simulation.getDepartedNumber(),
                })
                next_log += args.log_interval
    finally:
        tc.close()
        sumo_log.close()

    log_text = (out / "sumo.log").read_text(errors="replace")
    ebrake = parse_emergency_braking(log_text)
    eps = collision_episodes(collisions)
    trips = tripinfo_stats(trip)

    def mean(xs):
        return round(sum(xs) / len(xs), 4) if xs else None

    def pct(xs, q):
        if not xs:
            return None
        xs = sorted(xs)
        k = min(len(xs) - 1, max(0, int(round(q * (len(xs) - 1)))))
        return round(xs[k], 3)

    metrics = {
        "control": args.control,
        "n_scheduled": len(sched),
        "n_released": len(released),
        "stop_failures": n_stop_fail,
        "entry_deviation_s": {
            "n": len(entry_dev),
            "mean": mean(entry_dev),
            "p50": pct(entry_dev, 0.5),
            "p95": pct(entry_dev, 0.95),
            "min": round(min(entry_dev), 3) if entry_dev else None,
            "max": round(max(entry_dev), 3) if entry_dev else None,
        },
        "time_loss": {
            "series_mean": mean([r["mean_time_loss_s"] for r in timeseries
                                 if r["mean_time_loss_s"] is not None]),
            "per_vehicle_mean": trips.get("mean_time_loss_s"),
            "log_interval_s": args.log_interval,
        },
        "average_speed": {
            "series_mean": mean([r["mean_speed_mps"] for r in timeseries
                                 if r["mean_speed_mps"] is not None]),
            "per_vehicle_mean": trips.get("mean_speed_mps"),
        },
        "travel_time": {"per_vehicle_mean_s": trips.get("mean_duration_s")},
        "safety": {
            "collision_episodes": len(eps),
            "collision_records": len(collisions),
            "proximity_threshold_m": 0.5 * 3.0,
            "mingap_factor": args.mingap_factor,
            "emergency_braking_events": len(ebrake),
        },
        "fleet": {
            "n_trips": trips.get("n_trips"),
            "n_inserted": len(seen),
            "insertion_rate": round(len(seen) / len(sched), 4) if sched else None,
        },
        "simulated_s": round(timeseries[-1]["time_s"], 2) if timeseries else 0.0,
        "notes": [
            "time loss and speed follow main.tex section III-B (mean over the "
            "active fleet at each logging step) and are also reported per "
            "vehicle from tripinfo",
            "proximity events use SUMO's collision.mingap-factor with "
            "minGap=3.0 m, i.e. the paper's 1.5 m threshold",
            "right turns are uncoordinated (no internal conflict point) and are "
            "not gated by the schedule",
        ],
    }
    (out / "metrics.json").write_text(json.dumps(metrics, indent=1))
    if entry_events:
        with open(out / "entry_events.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(entry_events[0].keys()))
            w.writeheader()
            for e in entry_events:
                w.writerow(e)
    if timeseries:
        with open(out / "timeseries.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(timeseries[0].keys()))
            w.writeheader()
            for r in timeseries:
                w.writerow(r)
    if eps:
        with open(out / "collisions.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(eps[0].keys()))
            w.writeheader()
            for e in eps:
                w.writerow(e)
    manifest = {
        "adapter_version": "execute_plan/1",
        "control": args.control,
        "net": args.net, "rou": args.rou, "typ": args.typ,
        "net_sha256": sha256(args.net), "rou_sha256": sha256(args.rou),
        "typ_sha256": sha256(args.typ),
        "schedule": str(args.schedule), "schedule_sha256": sha256(args.schedule),
        "instance_dir": str(inst),
        "seed": args.seed, "step_length_s": args.step_length,
        "end_s": args.end, "log_interval_s": args.log_interval,
        "mingap_factor": args.mingap_factor,
        "sumo_command": cmd,
    }
    (out / "run_manifest.json").write_text(json.dumps(manifest, indent=1))
    print(json.dumps({k: metrics[k] for k in
                      ("control", "n_released", "entry_deviation_s",
                       "time_loss", "average_speed", "safety", "fleet")},
                     indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
