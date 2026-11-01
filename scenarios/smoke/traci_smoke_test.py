#!/usr/bin/env python3
"""Task 03 - TraCI compatibility smoke test (READ-ONLY).

Purpose
-------
Check whether the pip-installed ``traci`` Python client can drive the locally
installed SUMO binary through ``scenarios/smoke/cross3_smoke.sumocfg``.

This script only exercises **getter** interfaces.  It never issues a vehicle
control command (no setSpeed / slowDown / setStop / moveTo / moveToXY /
changeLane / setLaneChangeMode / setSpeedMode ...).  Control methods are only
inspected for availability and signature with ``hasattr`` / ``inspect``.

Scope: 0-30 simulation seconds, 1 s step (the step length stored in the
configuration file).  Not a reproduction of any manuscript experiment.

Output
------
* human-readable log on stdout (redirected by the caller into
  ``results/smoke/traci_smoke.log``);
* machine-readable summary in ``results/smoke/traci_smoke_summary.json``.

Usage
-----
    python3 scenarios/smoke/traci_smoke_test.py   # from the repository root
"""

import inspect
import json
import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CFG_REL = "scenarios/smoke/cross3_smoke.sumocfg"
CFG = str(ROOT / "scenarios" / "smoke" / "cross3_smoke.sumocfg")
OUT_JSON = str(ROOT / "results" / "smoke" / "traci_smoke_summary.json")
END_TIME = 30.0
SAMPLE_VEHICLES = 2

# Read-only vehicle getters that an FCFS controller would need.
VEHICLE_GETTERS = [
    "getPosition",
    "getSpeed",
    "getRoadID",
    "getLaneID",
    "getLanePosition",
    "getLaneIndex",
    "getAngle",
    "getAcceleration",
    "getLength",
    "getRouteID",
    "getMaxSpeed",
    "getDistance",
]

# Control methods: only inspected, never called in this test.
CONTROL_METHODS = [
    "setSpeed",
    "slowDown",
    "setStop",
    "resume",
    "moveTo",
    "moveToXY",
    "changeLane",
    "setLane",
    "setLaneChangeMode",
    "setSpeedMode",
    "setAcceleration",
    "setMaxSpeed",
    "setStopParameter",
]

def _pkg_version(distribution_names):
    """Best-effort pip version string for the TraCI/sumolib client."""
    try:
        from importlib import metadata
    except ImportError:  # pragma: no cover
        return None
    for name in distribution_names:
        try:
            return "%s==%s" % (name, metadata.version(name))
        except Exception:
            continue
    return None


def _sig(obj):
    try:
        return str(inspect.signature(obj))
    except Exception as exc:  # builtins / C extensions
        return "<unavailable: %s>" % exc


def main():
    import traci  # imported here so version reporting happens first

    report = {
        "python": sys.version.split()[0],
        "cwd": os.getcwd(),
        "config": CFG_REL,
        "end_time": END_TIME,
        "step_length_from_cfg": 1,
        "environment": {
            "SUMO_HOME": os.environ.get("SUMO_HOME"),
            "traci_client": _pkg_version(["traci"]),
            "sumolib_client": _pkg_version(["sumolib"]),
        },
        "traci_module_file": traci.__file__,
        "checks": [],
        "steps": [],
        "errors": [],
        "warnings": [],
    }

    def record(check, ok, detail):
        report["checks"].append({"check": check, "ok": bool(ok), "detail": str(detail)})
        print("[%s] %-42s %s" % ("PASS" if ok else "FAIL", check, detail))

    def attempt(check, fn):
        try:
            value = fn()
            record(check, True, repr(value))
            return value
        except Exception as exc:
            report["errors"].append(
                {"check": check, "error": "%s: %s" % (type(exc).__name__, exc)})
            record(check, False, "%s: %s" % (type(exc).__name__, exc))
            return None

    print("=" * 78)
    print("TraCI compatibility smoke test (read-only)")
    print("=" * 78)
    print("python            :", report["python"])
    print("traci module      :", report["traci_module_file"])
    print("pip client version:", report["environment"]["traci_client"])
    print("SUMO_HOME         :", report["environment"]["SUMO_HOME"])
    print("config            :", CFG_REL)
    print("-" * 78)

    # ---- 1) start ----------------------------------------------------------
    try:
        traci.start([
            "sumo",
            "-c", CFG,
            "--no-step-log", "true",
            "--duration-log.statistics", "true",
        ])
        record("traci.start()", True, "SUMO process started and connected")
    except Exception as exc:
        report["errors"].append({"check": "traci.start()", "error": traceback.format_exc()})
        record("traci.start()", False, "%s: %s" % (type(exc).__name__, exc))
        os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
        with open(OUT_JSON, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
        print("\nCannot continue without a connection. No environment change was made.")
        return 2

    try:
        attempt("traci.getVersion()", lambda: traci.getVersion())
        attempt("simulation.getTime() at start", lambda: traci.simulation.getTime())

        # network-level reads, once
        attempt("lane.getLength('north2center_0')",
                lambda: traci.lane.getLength("north2center_0"))
        attempt("lane.getShape('north2center_0')",
                lambda: traci.lane.getShape("north2center_0"))
        attempt("edge.getLastStepVehicleIDs('north2center')",
                lambda: traci.edge.getLastStepVehicleIDs("north2center"))
        attempt("junction.getPosition('center')",
                lambda: traci.junction.getPosition("center"))
        attempt("simulation.getCollisions()", lambda: traci.simulation.getCollisions())

        # ---- 2) stepping ---------------------------------------------------
        step_count = 0
        while traci.simulation.getTime() < END_TIME + 1e-9:
            traci.simulationStep()
            step_count += 1
            t = traci.simulation.getTime()
            ids = traci.vehicle.getIDList()
            sample = {}
            for vid in ids[:SAMPLE_VEHICLES]:
                sample[vid] = {
                    "roadID": traci.vehicle.getRoadID(vid),
                    "laneID": traci.vehicle.getLaneID(vid),
                    "lanePos": round(traci.vehicle.getLanePosition(vid), 2),
                    "pos": [round(c, 2) for c in traci.vehicle.getPosition(vid)],
                    "speed": round(traci.vehicle.getSpeed(vid), 2),
                    "angle": round(traci.vehicle.getAngle(vid), 1),
                }
            report["steps"].append({
                "t": t,
                "n_running": len(ids),
                "sample": sample,
            })
        record("traci.simulationStep() loop", step_count > 0,
               "%d steps executed, sim time %.1f s" % (step_count, traci.simulation.getTime()))

        # ---- 3/4) getters on a live vehicle --------------------------------
        ids = traci.vehicle.getIDList()
        if ids:
            vid = ids[0]
            print("-" * 78)
            print("read getters on vehicle %r (t=%.1f s)" % (vid, traci.simulation.getTime()))
            for name in VEHICLE_GETTERS:
                attempt("vehicle.%s(%r)" % (name, vid),
                        lambda n=name, v=vid: getattr(traci.vehicle, n)(v))
            report["getter_sample_vehicle"] = vid
        else:
            msg = "no vehicle running at t=%.1f; getters not sampled" % traci.simulation.getTime()
            report["warnings"].append(msg)
            print("WARNING:", msg)

        attempt("simulation.getDepartedIDList()", lambda: traci.simulation.getDepartedIDList())
        attempt("simulation.getArrivedIDList()", lambda: traci.simulation.getArrivedIDList())
        attempt("simulation.getMinExpectedNumber()",
                lambda: traci.simulation.getMinExpectedNumber())

        # ---- 5) control API availability (inspected, NOT executed) ---------
        print("-" * 78)
        print("control API availability (inspected only, never called)")
        for name in CONTROL_METHODS:
            obj = getattr(traci.vehicle, name, None)
            ok = callable(obj)
            detail = _sig(obj) if ok else "MISSING"
            report["checks"].append({
                "check": "control API traci.vehicle.%s" % name,
                "ok": ok,
                "detail": detail,
                "executed": False,
            })
            print("[%s] traci.vehicle.%-20s %s" % ("HAVE" if ok else "MISS", name, detail))
    finally:
        # ---- close ---------------------------------------------------------
        try:
            traci.close()
            record("traci.close()", True, "connection closed cleanly")
        except Exception as exc:
            report["errors"].append({"check": "traci.close()", "error": traceback.format_exc()})
            record("traci.close()", False, "%s: %s" % (type(exc).__name__, exc))

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)

    n_fail = sum(1 for c in report["checks"] if not c["ok"])
    print("=" * 78)
    print("steps recorded: %d | checks: %d | failures: %d | errors: %d"
          % (len(report["steps"]), len(report["checks"]), n_fail, len(report["errors"])))
    print("summary json: %s" % OUT_JSON)
    print("=" * 78)
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
