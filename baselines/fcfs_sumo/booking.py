#!/usr/bin/env python3
"""Conflict-point time-window booking for the FCFS baseline.

Why this module exists
----------------------
The first controller version used **mutual exclusion on lanes** (``ResourceMap``):
a vehicle locked its via lane and its exit lane until it had physically cleared
them.  Two problems came out of running it at paper density (see
``docs/HANDOFF.md`` 11.5 / 11.5b):

1. it cannot express **crossing** conflicts at all -- two crossing movements use
   different via lanes, so both were admitted and only SUMO's IDM kept them
   apart.  "Zero collisions" was therefore an empirical observation, not a
   structural guarantee;
2. mutual exclusion is far too coarse: throughput collapsed to 0.7-1.3 veh/s
   against 2.7 veh/s with no control at all.

This module implements the reservation model that reservation-based AIM
actually uses (Dresner--Stone / AIM4): a vehicle books **time windows** on the
conflict points it will traverse.  Two vehicles may be inside the junction at
the same time as long as their windows on every shared conflict point are
separated by at least the safety gap.

Resources
---------
``("space", lane)``
    a via lane (or a group of via lanes whose centrelines overlap, which
    physically means the same strip of pavement).  Occupied for the whole
    traversal: ``[t_stop, t_stop + len / v]``.

``("cross", x, y)``
    a crossing point between two via lanes, keyed by its rounded global
    coordinate so that both movements derive the same key.  Occupied for
    ``dT_safe`` around the moment the vehicle passes it.

``("merge", exit_lane)``
    the merge point at the head of an exit lane, shared by every movement that
    ends on that lane.  Occupied for ``dT_safe`` around the merge moment.

All distances along a lane come from ``shapely`` geometry of the net's own
internal lane shapes, i.e. the same evidence ``conflicts.py`` already uses; no
new geometric assumption is introduced.
"""

import itertools

from shapely.geometry import LineString, Point

DT_SAFE_DEFAULT = 2.0
V_DEFAULT = 13.9          # m/s, scenarios/original/types.typ.xml maxSpeed
A_MAX = 1.0               # m/s^2, types.typ.xml accel  (best case)
A_MIN = 0.5               # m/s^2, effective floor (accel 1.0 halved: queueing,
                          # junction friction); used for the late bound only
COORD_ROUND = 1           # decimals used to make crossing keys agree
MAX_ETA = 30.0            # s, ignore vehicles further than this in time


def travel_time(dist, v0, accel, v_max=V_DEFAULT):
    """Time to cover ``dist`` from speed ``v0`` accelerating at ``accel``.

    Straight out of the vType in ``scenarios/original/types.typ.xml``
    (``accel=1.0``, ``maxSpeed=13.9``).  A blanket "V_SLOW = 5 m/s" was wrong in
    the unsafe direction: a vehicle starting from rest needs 6.3 s to cover a
    20 m internal lane, not 4.0 s, so the windows ended too early.
    """
    if dist <= 0.0:
        return 0.0
    v0 = max(0.0, min(v0, v_max))
    accel = max(accel, 0.05)
    d_acc = max(0.0, (v_max * v_max - v0 * v0) / (2.0 * accel))
    if dist <= d_acc:
        return (-v0 + (v0 * v0 + 2.0 * accel * dist) ** 0.5) / accel
    return (v_max - v0) / accel + (dist - d_acc) / v_max


class ConflictPoints:
    """Geometric conflict points and via-lane space groups."""

    def __init__(self, model):
        self.model = model
        self.via_geom = {}
        for edge in model.edges.values():
            if edge["function"] == "internal":
                for ln in edge["lanes"]:
                    self.via_geom[ln["id"]] = LineString(ln["shape"])
        self.via_len = {k: g.length for k, g in self.via_geom.items()}

        # (movement, fromLane) -> (via lane, toLane)
        self.via_of = {}
        for conn in model.connections:
            for m in model.movements:
                if m["from_edge"] == conn["from"] and m["to_edge"] == conn["to"]:
                    self.via_of[(m["index"], conn["fromLane"])] = (
                        conn["via"], conn["toLane"])
                    break

        # crossing table: (va, vb) -> [distance along va, distance along vb]
        self.crossings = {}
        # overlapping via lanes share one space group
        parent = {k: k for k in self.via_geom}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

        keys = sorted(self.via_geom)
        for a, b in itertools.combinations(keys, 2):
            ga, gb = self.via_geom[a], self.via_geom[b]
            if not ga.intersects(gb):
                continue
            inter = ga.intersection(gb)
            if inter.geom_type in ("LineString", "MultiLineString"):
                if inter.length > 0.5:
                    union(a, b)          # same strip of pavement
                continue
            points = _points_of(inter)
            for p in points:
                self.crossings.setdefault((a, b), []).append(
                    (ga.project(p), gb.project(p), p))
                self.crossings.setdefault((b, a), []).append(
                    (gb.project(p), ga.project(p), p))

        self.group = {}
        for k in self.via_geom:
            self.group[k] = find(k)

    def space_key(self, via):
        return ("space", self.group.get(via, via))

    def crossings_of(self, via):
        """[(distance along via, crossing key)] for one via lane."""
        out = []
        for (va, _vb), items in self.crossings.items():
            if va != via:
                continue
            for d_self, _d_other, p in items:
                out.append((d_self, _cross_key(p)))
        return out


def _cross_key(point):
    return ("cross", round(point.x, COORD_ROUND), round(point.y, COORD_ROUND))


def _points_of(geom):
    if geom.geom_type == "Point":
        return [geom]
    if geom.geom_type == "MultiPoint":
        return list(geom.geoms)
    if geom.geom_type == "GeometryCollection":
        return [g for g in geom.geoms if isinstance(g, Point)]
    return []


class WindowBooker:
    """Time-window reservations on conflict points."""

    def __init__(self, points, dt_safe=DT_SAFE_DEFAULT, v_typ=V_DEFAULT):
        self.pts = points
        self.dt_safe = dt_safe
        self.v_typ = v_typ
        self.book = {}          # key -> [(t0, t1)]
        self.n_grant = 0
        self.n_reject = 0
        self.n_prune = 0

    # ---- planning -----------------------------------------------------
    def plan(self, movement_index, from_lane, now, dist_to_stop, speed):
        """Return [(key, t0, t1)] from a kinematic profile of the traversal.

        Times come from :func:`travel_time` with the vType's own accel/maxSpeed.
        The window is the band between the best case (full accel) and the worst
        case (half accel) plus ``dT_safe``, so a vehicle that is slowed later
        still stays inside its booking.
        """
        hit = self.pts.via_of.get((movement_index, from_lane))
        if hit is None:
            return None
        via, to_lane = hit
        m = self.pts.model.movements[movement_index]
        v0 = max(0.0, speed or 0.0)

        def tt(extra, accel):
            return travel_time(dist_to_stop + extra, v0, accel, self.v_typ)

        t_eta_fast = tt(0.0, A_MAX)
        t_eta_slow = tt(0.0, A_MIN)
        if t_eta_slow > MAX_ETA:
            return None

        via_len = self.pts.via_len.get(via, 20.0)
        plan = [(self.pts.space_key(via),
                 now + t_eta_fast,
                 now + tt(via_len, A_MIN) + self.dt_safe)]
        for d, key in self.pts.crossings_of(via):
            plan.append((key,
                         now + tt(d, A_MAX),
                         now + tt(d, A_MIN) + self.dt_safe))
        plan.append((("merge", "%s_%d" % (m["to_edge"], to_lane)),
                     now + tt(via_len, A_MAX),
                     now + tt(via_len, A_MIN) + self.dt_safe))
        return plan

    # ---- admission ----------------------------------------------------
    def free(self, plan, now):
        if not plan:
            return False
        for key, t0, t1 in plan:
            for b0, b1 in self.book.get(key, ()):
                if t0 < b1 + self.dt_safe and b0 < t1 + self.dt_safe:
                    self.n_reject += 1
                    return False
        return True

    def commit(self, plan):
        for key, t0, t1 in plan:
            self.book.setdefault(key, []).append((t0, t1))
        self.n_grant += 1

    def prune(self, now):
        horizon = now - self.dt_safe - 1.0
        for key, items in list(self.book.items()):
            kept = [(a, b) for a, b in items if b >= horizon]
            if len(kept) != len(items):
                self.n_prune += 1
            if kept:
                self.book[key] = kept
            else:
                self.book.pop(key, None)

    def stats(self):
        return {"booked_keys": len(self.book),
                "intervals": sum(len(v) for v in self.book.values()),
                "grants": self.n_grant,
                "rejections": self.n_reject}
