"""Frozen-priority FCFS request queue for the shadow controller.

Design notes (deliberately conservative):

* The *proxy request time* is the first simulation step at which the vehicle is
  observed on an approach edge.  This is NOT the request-time definition of the
  Dresner--Stone / AIM4 protocol (which is defined on an arrival/control-zone
  boundary that has not been fixed for this project yet).  Every log row carries
  ``request_time_basis = first_seen_on_approach`` so the two are never confused.
* Priority is ``(proxy request time, vehicle id)``; the vehicle id breaks exact
  ties deterministically.  Once a request is queued its key is never
  recomputed, so no live ETA can reorder the queue.
* The constant-speed ETA stored on each request is a *diagnostic* only.  It is
  never used for ordering and its speed floor is not a research parameter.
"""

REQUEST_TIME_BASIS = "first_seen_on_approach_proxy"
ETA_SPEED_FLOOR = 0.1   # m/s, numerical guard for the diagnostic ETA only


class Request:
    """One queued vehicle.  All fields are frozen at queue-insertion time."""

    __slots__ = ("seq", "vehicle_id", "movement_index", "t_request",
                 "dist_to_stop_at_request", "speed_at_request",
                 "eta_constant_speed", "rank_at_request")

    def __init__(self, seq, vehicle_id, movement_index, t_request,
                 dist_to_stop, speed):
        self.seq = seq
        self.vehicle_id = vehicle_id
        self.movement_index = movement_index
        self.t_request = t_request
        self.dist_to_stop_at_request = dist_to_stop
        self.speed_at_request = speed
        self.rank_at_request = None
        self.eta_constant_speed = (
            None if dist_to_stop is None
            else t_request + dist_to_stop / max(speed, ETA_SPEED_FLOOR))

    @property
    def priority_key(self):
        return (self.t_request, self.vehicle_id)

    def as_dict(self):
        return {
            "seq": self.seq,
            "vehicle_id": self.vehicle_id,
            "movement_index": self.movement_index,
            "t_request": self.t_request,
            "dist_to_stop_at_request": self.dist_to_stop_at_request,
            "speed_at_request": self.speed_at_request,
            "eta_constant_speed_diagnostic_only": self.eta_constant_speed,
            "request_time_basis": REQUEST_TIME_BASIS,
        }


class RequestQueue:
    """Append-only FCFS queue; one request per vehicle, ever."""

    def __init__(self, model):
        self.model = model
        self.requests = {}
        self.duplicate_attempts = []
        self._previous_order = None
        self.order_changes = 0

    def request(self, t, vehicle_id, movement_index, dist_to_stop=None, speed=0.0):
        if vehicle_id in self.requests:
            self.duplicate_attempts.append((t, vehicle_id))
            return None
        req = Request(len(self.requests) + 1, vehicle_id, movement_index,
                      t, dist_to_stop, speed)
        self.requests[vehicle_id] = req
        return req

    def ordered(self):
        return sorted(self.requests.values(), key=lambda r: r.priority_key)

    def __len__(self):
        return len(self.requests)

    def __iter__(self):
        return iter(self.ordered())

    def ranks(self):
        return {r.vehicle_id: i + 1 for i, r in enumerate(self.ordered())}

    def freeze_ranks(self):
        """Assign and freeze the insertion-time rank for reporting."""
        for rank, req in enumerate(self.ordered(), start=1):
            if req.rank_at_request is None:
                req.rank_at_request = rank
        return self.ranks()

    def check_order_stability(self):
        """Detect any reordering of the queue (should never happen)."""
        order = [r.vehicle_id for r in self.ordered()]
        if self._previous_order is not None:
            kept = [v for v in self._previous_order if v in set(order)]
            now = [v for v in order if v in set(kept)]
            if kept != now:
                self.order_changes += 1
        self._previous_order = order
        return self.order_changes == 0
