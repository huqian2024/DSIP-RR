"""Per-step vehicle tracking for the FCFS shadow controller (read-only).

The tracker classifies every sampled vehicle into one of four states

    approach  -- on one of the four incoming edges
    inside    -- roadID starts with ':' (an internal junction edge)
    exit      -- on one of the four outgoing edges
    gone      -- no longer reported by TraCI

and records the transitions ``first_seen``, ``enter``, ``leave`` and ``gone``.
A vehicle that is still inside the junction when the simulation stops keeps
``leave_t = None`` and is reported as ``open``; it is never silently dropped.
"""

APPROACH, INSIDE, EXIT, GONE = "approach", "inside", "exit", "gone"


class VehicleTracker:
    """Collects per-vehicle life-cycle events from per-step TraCI snapshots."""

    def __init__(self, model):
        self.model = model
        self.approach_edges = {m["from_edge"] for m in model.movements}
        self.exit_edges = {m["to_edge"] for m in model.movements}
        self.records = {}      # vehicle id -> dict
        self.events = []       # list of (t, vehicle_id, event, detail)

    # -- helpers ----------------------------------------------------------
    def classify(self, road_id):
        if road_id is None or road_id == "":
            return GONE
        if road_id.startswith(":"):
            return INSIDE
        if road_id in self.approach_edges:
            return APPROACH
        if road_id in self.exit_edges:
            return EXIT
        return GONE

    # -- main entry point --------------------------------------------------
    def update(self, t, snapshot):
        """``snapshot``: list of dicts with id/routeID/roadID/laneID/lanePos/speed/pos."""
        seen = set()
        for veh in snapshot:
            vid = veh["id"]
            seen.add(vid)
            state = self.classify(veh["roadID"])
            rec = self.records.get(vid)
            if rec is None:
                rec = {
                    "vehicle_id": vid,
                    "route_id": veh["routeID"],
                    "movement_index": self.model.index_of_route(veh["routeID"]),
                    "first_seen_t": t,
                    "first_road": veh["roadID"],
                    "first_lane": veh["laneID"],
                    "first_lane_pos": veh["lanePos"],
                    "first_speed": veh["speed"],
                    "max_speed_seen": veh["speed"],
                    "enter_t": None,
                    "enter_from_road": None,
                    "enter_from_lane": None,
                    "enter_speed": None,
                    "leave_t": None,
                    "leave_to_road": None,
                    "gone_t": None,
                    "inside_now": False,
                    "n_samples": 0,
                    "states": set(),
                    "open_at_end": False,
                }
                self.records[vid] = rec
                self.events.append((t, vid, "first_seen", state))
            rec["n_samples"] += 1
            rec["states"].add(state)
            rec["max_speed_seen"] = max(rec["max_speed_seen"], veh["speed"])

            if state == INSIDE and not rec["inside_now"]:
                if rec["enter_t"] is None:
                    rec["enter_t"] = t
                    rec["enter_from_road"] = veh["roadID"]
                    rec["enter_from_lane"] = veh["laneID"]
                    rec["enter_speed"] = veh["speed"]
                self.events.append((t, vid, "enter", veh["roadID"]))
            elif state != INSIDE and rec["inside_now"]:
                if rec["leave_t"] is None:
                    rec["leave_t"] = t
                    rec["leave_to_road"] = veh["roadID"]
                self.events.append((t, vid, "leave", veh["roadID"]))
            rec["inside_now"] = (state == INSIDE)

        for vid, rec in self.records.items():
            if vid in seen or rec["gone_t"] is not None:
                continue
            rec["gone_t"] = t
            if rec["inside_now"]:
                rec["inside_now"] = False
                self.events.append((t, vid, "gone_inside", "disappeared while inside"))
            else:
                self.events.append((t, vid, "gone", "left the simulation"))

    # -- queries -----------------------------------------------------------
    def movements_inside(self):
        """movement_index -> set(vehicle ids) for vehicles currently inside."""
        occ = {}
        for vid, rec in self.records.items():
            if rec["inside_now"] and rec["movement_index"] is not None:
                occ.setdefault(rec["movement_index"], set()).add(vid)
        return occ

    def events_at(self, t):
        return [e for e in self.events if e[0] == t]

    def open_vehicles(self):
        return [v for v, r in self.records.items()
                if r["enter_t"] is not None and r["leave_t"] is None]
