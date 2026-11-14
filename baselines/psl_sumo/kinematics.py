"""Occupancy model shared by the PSL planner adapter and its validator.

The upstream solver assumes **one constant speed per vehicle for its whole path**
(``SIPP.cpp:183-195``) and charges each conflict point a passage time of
``Li/w + Li/v`` (``SIPP.cpp:194``, ``SIPP.h:77-79``).  That model is the right
thing to *report* PSL's own result, but it cannot be executed in our SUMO
scenarios: ``types.typ.xml`` limits vehicles to ``maxSpeed = 13.9`` m/s and, if a
vehicle is held at the stop line, it enters the junction from **rest** and
accelerates at ``accel = 1.0`` m/s².  A 27 m path then takes ≈ 7.4 s instead of
1.96 s at 15 m/s.

Two explicitly named models are therefore provided:

``constant``
    Upstream's model.  ``v`` is the speed the solver returned (its LP bound is
    ``[3, 15]``), so this reproduces exactly what PSL believes it has planned.
    Physically infeasible in our scenarios -- report only as *PSL's own plan*.

``accelerating``
    What our execution stack actually produces: constant acceleration ``a`` from
    rest up to ``vmax``.  This is the fair analogue of the FCFS baseline, which
    also holds vehicles with ``setStop`` and then lets SUMO's IDM drive.

Both models are deterministic functions of (release time, along-path offset), so
the validator can re-derive them without trusting the planner.
"""

from __future__ import annotations

import math

W = 7.0                     # SIPP.h:79
TURN_RADIUS_RIGHT = 10 * 0.3048
TURN_RADIUS_LEFT = 40 * 0.3048
AGENT_LENGTH = 5.0          # Instance.cpp loadVehicles()
V_LIMIT = 13.9              # scenarios/original/types.typ.xml maxSpeed
ACCEL = 1.0                 # scenarios/original/types.typ.xml accel


def li(move, agent_length=AGENT_LENGTH):
    """Upstream passage length ``Li`` (SIPP.cpp:364-380)."""
    if move == "S":
        return agent_length
    radius = TURN_RADIUS_RIGHT if move == "R" else TURN_RADIUS_LEFT
    return 4 * radius * math.asin(agent_length / (2 * radius))


def travel_time(offset, accel=ACCEL, vmax=V_LIMIT):
    """Time to cover ``offset`` from rest, accelerating at ``accel`` up to ``vmax``."""
    if offset <= 0.0:
        return 0.0
    d_acc = vmax * vmax / (2.0 * accel)
    if offset <= d_acc:
        return math.sqrt(2.0 * offset / accel)
    return vmax / accel + (offset - d_acc) / vmax


def occupancy(release, offset, passage, mode="accelerating",
              speed=None, accel=ACCEL, vmax=V_LIMIT, w=W):
    """(enter, leave) interval during which a vehicle blocks a conflict point.

    ``offset``  along-path distance of the conflict point from the movement's
                entry vertex;
    ``passage`` ``Li(move)`` -- how much path length the vehicle needs to clear
                the point with its tail;
    ``release`` time at which the vehicle's head leaves the stop line;
    ``w``       upstream's ``SIPP.h:79`` passage speed (hard-coded to 7 in the
                binary).  It is a parameter *here* so that the effect of a
                different value can be quantified without recompiling; the
                solver itself always uses 7.
    """
    if mode == "constant":
        v = speed if speed else vmax
        t0 = release + offset / v
        return t0, t0 + passage / w + passage / v
    return release + travel_time(offset, accel, vmax), \
        release + travel_time(offset + passage, accel, vmax)


def traversal_time(length, mode="accelerating", speed=None,
                   accel=ACCEL, vmax=V_LIMIT):
    """Head-to-exit time for a path of ``length`` metres."""
    if mode == "constant":
        return length / (speed if speed else vmax)
    return travel_time(length, accel, vmax)
