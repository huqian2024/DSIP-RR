#!/usr/bin/env python3
"""Dependency-free logic self check for the FCFS shadow controller.

Runs without TraCI and without SUMO: it feeds synthetic snapshots into
VehicleTracker -> RequestQueue -> ShadowEngine and asserts the documented
behaviour.  Usage (from the repository root):

    python3 -m baselines.fcfs_sumo.test_logic
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from baselines.fcfs_sumo.conflicts import ConflictModel      # noqa: E402
from baselines.fcfs_sumo.queue import RequestQueue           # noqa: E402
from baselines.fcfs_sumo.shadow import ShadowEngine          # noqa: E402
from baselines.fcfs_sumo.tracker import VehicleTracker       # noqa: E402

failures = []


def check(name, condition, detail=""):
    ok = bool(condition)
    print("[%s] %-52s %s" % ("PASS" if ok else "FAIL", name, detail))
    if not ok:
        failures.append(name)


def snap(vid, route, road, lane=None, pos=0.0, speed=10.0):
    return {"id": vid, "routeID": route, "roadID": road,
            "laneID": lane or road + "_0", "lanePos": pos, "speed": speed,
            "pos": (0.0, 0.0)}


def test_conflict_model():
    model = ConflictModel()
    check("12 movements loaded", len(model.movements) == 12,
          "n=%d" % len(model.movements))
    check("conflict matrix symmetric", model.symmetric)
    task03 = model.task03_check
    if task03.get("found"):
        check("matrix matches Task 03 log", task03.get("match") is True,
              "mismatches=%d" % len(task03.get("mismatches", [])))
    else:
        print("[SKIP] %-52s %s" % ("matrix cross-check vs Task 03 log",
                                   "log absent; run scenarios/smoke/net_analysis.py"))
    check("center junction has no request/foes table",
          model.center.get("n_request") == 0)
    check("every movement has >=1 partner",
          all(model.partners(m["index"]) for m in model.movements))
    return model


def test_queue(model):
    queue = RequestQueue(model)
    queue.request(0.0, "vehB", 0)
    queue.request(0.0, "vehA", 0)     # same proxy time -> id breaks the tie
    queue.request(1.0, "vehC", 0)
    order = [r.vehicle_id for r in queue.ordered()]
    check("tie broken deterministically by vehicle id",
          order == ["vehA", "vehB", "vehC"], str(order))
    dup = queue.request(2.0, "vehA", 0)
    check("duplicate request rejected",
          dup is None and len(queue.duplicate_attempts) == 1,
          "duplicates=%d" % len(queue.duplicate_attempts))
    ranks = queue.freeze_ranks()
    check("ranks frozen at insertion", ranks["vehA"] == 1 and ranks["vehC"] == 3,
          str(ranks))
    check("order stable across checks", queue.check_order_stability())


def test_tracker(model):
    tracker = VehicleTracker(model)
    mv = model.movements[0]
    approach, exit_edge = mv["from_edge"], mv["to_edge"]
    tracker.update(1.0, [snap("v1", mv["route"], approach, pos=10.0)])
    tracker.update(2.0, [snap("v1", mv["route"], ":center_1", pos=5.0)])
    tracker.update(3.0, [snap("v1", mv["route"], exit_edge, pos=5.0)])
    rec = tracker.records["v1"]
    check("first seen recorded", rec["first_seen_t"] == 1.0)
    check("enter recorded once", rec["enter_t"] == 2.0, "enter_t=%s" % rec["enter_t"])
    check("leave recorded once", rec["leave_t"] == 3.0, "leave_t=%s" % rec["leave_t"])
    check("entered once, left once",
          len([e for e in tracker.events if e[2] == "enter"]) == 1
          and len([e for e in tracker.events if e[2] == "leave"]) == 1)
    tracker.update(4.0, [snap("v2", mv["route"], ":center_1", pos=5.0)])
    tracker.update(5.0, [])
    check("vanished vehicle marked gone", tracker.records["v2"]["gone_t"] == 5.0)
    check("vehicle gone inside is flagged",
          any(e[2] == "gone_inside" for e in tracker.events))


def test_engine(model):
    tracker = VehicleTracker(model)
    queue = RequestQueue(model)
    engine = ShadowEngine(model, tracker, queue)
    idx_a = 4                                    # m05 north2south (straight)
    idx_b = model.partners(idx_a)[0]
    route_a, route_b = model.movement(idx_a)["route"], model.movement(idx_b)["route"]
    edge_a, edge_b = model.movement(idx_a)["from_edge"], model.movement(idx_b)["from_edge"]

    tracker.update(0.0, [snap("vehA", route_a, edge_a, pos=70.0),
                         snap("vehB", route_b, edge_b, pos=70.0)])
    queue.request(0.0, "vehA", idx_a, 16.0, 10.0)
    queue.request(0.0, "vehB", idx_b, 16.0, 10.0)
    engine.step(0.0)
    check("queued vehicles start ELIGIBLE",
          engine.status["vehA"] == "ELIGIBLE" and engine.status["vehB"] == "ELIGIBLE",
          "%s / %s" % (engine.status["vehA"], engine.status["vehB"]))

    tracker.update(1.0, [snap("vehA", route_a, ":center_1", pos=5.0),
                         snap("vehB", route_b, edge_b, pos=60.0)])
    engine.step(1.0)
    check("occupant inside -> ENTERED", engine.status["vehA"] == "ENTERED")
    check("conflicting movement -> BLOCKED", engine.status["vehB"] == "BLOCKED",
          str(engine.status["vehB"]))

    tracker.update(2.0, [snap("vehA", route_a, model.movement(idx_a)["to_edge"], pos=5.0),
                         snap("vehB", route_b, edge_b, pos=50.0)])
    engine.step(2.0)
    check("occupant left -> CLEARED", engine.status["vehA"] == "CLEARED")
    check("cleared conflict without safety gap -> UNDETERMINED",
          engine.status["vehB"] == "UNDETERMINED", str(engine.status["vehB"]))

    tracker.update(3.0, [snap("vehB", route_b, ":center_1", pos=5.0)])
    engine.step(3.0)
    check("entered while UNDETERMINED is logged as a diagnostic",
          "vehB" in engine.entered_while_undetermined)
    check("last decision before entry recorded",
          engine.last_decision_before_entry.get("vehB") == "UNDETERMINED")
    check("no invalid state transitions", not engine.invalid_transitions,
          str(engine.invalid_transitions))


def test_no_control_calls():
    """Static guard.

    The original intent -- "the shadow path never actuates a vehicle" -- must
    still hold now that ``control.py`` exists as a *deliberate* control mode.
    Rather than widening the allow-list (which would let actuation leak back
    into the shadow path unnoticed), the guard is made more precise:

    1. every module except the control mode and this test is actuation-free;
    2. ``runner.py`` (the shadow entry point) is getters-only;
    3. ``control.py`` really does contain the two calls it claims to use.
    """
    banned = ("setSpeed(", "slowDown(", "setStop(", "moveTo(", "moveToXY(",
              "changeLane(", "setLaneChangeMode(", "setSpeedMode(")
    pkg = ROOT / "baselines" / "fcfs_sumo"
    control = "control.py"

    hits = []
    for py in sorted(pkg.glob("*.py")):
        if py.name in ("test_logic.py", control):
            continue
        text = py.read_text(encoding="utf-8")
        hits += ["%s:%s" % (py.name, token) for token in banned if token in text]
    check("actuation confined to control.py", not hits, str(hits))

    runner = (pkg / "runner.py").read_text(encoding="utf-8")
    used = [t for t in banned if t in runner]
    check("runner.py contains no actuation call either", not used, str(used))

    ctl = (pkg / control).read_text(encoding="utf-8")
    check("control.py does call setStop and resume",
          ("setStop(" in ctl) and ("resume(" in ctl), "")


def main():
    model = test_conflict_model()
    test_queue(model)
    test_tracker(model)
    test_engine(model)
    test_no_control_calls()
    print("-" * 78)
    print("failures:", failures if failures else "none")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
