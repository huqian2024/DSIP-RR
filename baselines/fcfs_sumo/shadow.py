"""Shadow decision engine: FCFS admission decisions WITHOUT any vehicle control.

Status vocabulary
-----------------
REQUESTED     queued (proxy request time = first observation on an approach)
BLOCKED       a conflicting movement is occupied *right now*
ELIGIBLE      the conflict set has not been occupied at any time since this
              vehicle was queued -> admission is safe irrespective of the
              (still undefined) safety gap
UNDETERMINED  the conflict set is free now, but it *was* occupied after this
              vehicle was queued; deciding whether the remaining separation is
              sufficient requires the safety-gap parameter, which has not been
              fixed.  The engine deliberately does NOT invent it.
ENTERED       the vehicle is observed inside the junction
CLEARED       the vehicle is observed to have left the junction

``resource_state`` is logged separately so a pure "is the conflict set free?"
answer is always available even when the status is UNDETERMINED.

Shadow mode never commands a vehicle, so the observed entry may contradict the
computed decision.  Those contradictions are recorded as diagnostics; they do
not mean FCFS is broken, they mean the controller was not actuated.
"""

STATUSES = ("REQUESTED", "BLOCKED", "ELIGIBLE", "UNDETERMINED", "ENTERED", "CLEARED")

_ALLOWED = {
    ("REQUESTED", "BLOCKED"), ("REQUESTED", "ELIGIBLE"),
    ("REQUESTED", "UNDETERMINED"), ("REQUESTED", "ENTERED"),
    ("BLOCKED", "BLOCKED"), ("BLOCKED", "ELIGIBLE"),
    ("BLOCKED", "UNDETERMINED"), ("BLOCKED", "ENTERED"),
    ("ELIGIBLE", "ELIGIBLE"), ("ELIGIBLE", "BLOCKED"),
    ("ELIGIBLE", "UNDETERMINED"), ("ELIGIBLE", "ENTERED"),
    ("UNDETERMINED", "UNDETERMINED"), ("UNDETERMINED", "BLOCKED"),
    ("UNDETERMINED", "ELIGIBLE"), ("UNDETERMINED", "ENTERED"),
    ("ENTERED", "ENTERED"), ("ENTERED", "CLEARED"),
    ("CLEARED", "CLEARED"),
}


class ShadowEngine:
    """Computes and logs admissions decisions; performs no actuation."""

    def __init__(self, model, tracker, queue):
        self.model = model
        self.tracker = tracker
        self.queue = queue
        self.status = {}
        self.history = []
        self.last_cleared = {}
        self.invalid_transitions = []
        self.violations = []
        self.first_decision = {}
        self.last_decision_before_entry = {}
        self.hard_conflict_at_entry = {}
        self.entered_while_blocked = set()
        self.entered_while_undetermined = set()

    def _absorb_events(self, t):
        for (_te, vid, event, _detail) in self.tracker.events_at(t):
            if event in ("leave", "gone_inside"):
                rec = self.tracker.records.get(vid)
                mv = rec["movement_index"] if rec else None
                if mv is not None:
                    self.last_cleared[mv] = t

    def _decide(self, t, req, rec, occupancy):
        mv = req.movement_index
        if mv is None:
            return ("UNDETERMINED", "unknown", [],
                    "movement could not be mapped to a route: no conflict information")
        partners = self.model.partners(mv)
        active = [p for p in partners if occupancy.get(p)]
        if active:
            vehicles = sorted({v for p in active for v in occupancy.get(p, ())})
            return ("BLOCKED", "occupied",
                    [self.model.label(p) for p in active],
                    "conflicting movement(s) inside: %s" % ", ".join(vehicles))
        recent = [(p, self.last_cleared[p]) for p in partners
                  if self.last_cleared.get(p) is not None
                  and self.last_cleared[p] >= req.t_request]
        if recent:
            p, tc = max(recent, key=lambda kv: kv[1])
            return ("UNDETERMINED", "free", [],
                    "conflicting movement %s cleared at t=%s after this request "
                    "(t=%s); required safety gap is NOT defined"
                    % (self.model.label(p), tc, req.t_request))
        return ("ELIGIBLE", "free", [],
                "conflict set not occupied since request t=%s" % req.t_request)


    def step(self, t):
        self._absorb_events(t)
        occupancy = self.tracker.movements_inside()
        for req in self.queue.ordered():
            vid = req.vehicle_id
            rec = self.tracker.records.get(vid)
            if rec is None:
                continue
            prev = self.status.get(vid, "REQUESTED")
            first = vid not in self.status

            if rec["enter_t"] is not None and rec["leave_t"] is None:
                status, resource, blocking, reason = (
                    "ENTERED", "inside", [], "vehicle observed inside the junction")
            elif rec["leave_t"] is not None:
                status, resource, blocking, reason = (
                    "CLEARED", "free", [], "vehicle observed leaving the junction")
            else:
                status, resource, blocking, reason = self._decide(
                    t, req, rec, occupancy)

            if (prev, status) not in _ALLOWED:
                self.invalid_transitions.append(
                    {"t": t, "vehicle_id": vid, "from": prev, "to": status})
            self.status[vid] = status

            if first:
                self.first_decision[vid] = status
            if status == "ENTERED" and vid not in self.last_decision_before_entry:
                self.last_decision_before_entry[vid] = prev
                mv_label = (self.model.label(req.movement_index)
                            if req.movement_index is not None else "?")
                if prev == "BLOCKED":
                    conflicting = (set(self.model.partners(req.movement_index))
                                   if req.movement_index is not None else set())
                    others = sorted(self.model.label(m) for m in occupancy
                                    if m in conflicting)
                    self.entered_while_blocked.add(vid)
                    self.hard_conflict_at_entry[vid] = others
                    self.violations.append({
                        "t": t, "vehicle_id": vid, "movement": mv_label,
                        "kind": "entered_while_BLOCKED",
                        "conflicting_movements_inside": others})
                elif prev == "UNDETERMINED":
                    self.entered_while_undetermined.add(vid)
                    self.violations.append({
                        "t": t, "vehicle_id": vid, "movement": mv_label,
                        "kind": "entered_while_UNDETERMINED",
                        "conflicting_movements_inside": []})

            self.history.append({
                "t": t,
                "seq": req.seq,
                "vehicle_id": vid,
                "movement": (self.model.label(req.movement_index)
                             if req.movement_index is not None else "?"),
                "previous": prev,
                "status": status,
                "resource_state": resource,
                "blocking_movements": "|".join(blocking),
                "reason": reason,
            })
        self.queue.check_order_stability()
        return occupancy

    def status_counts(self):
        counts = {}
        for row in self.history:
            counts[row["status"]] = counts.get(row["status"], 0) + 1
        return counts
