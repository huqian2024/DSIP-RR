"""Generate the upstream PSL graph model from a SUMO network.

Why this module exists
----------------------
The PSL upstream (``theanhhoang/AIM`` @ ``AAI22_PBS-SIPP``) does **not** read a
SUMO network.  ``Instance`` loads two hand-written files:

* ``intro_graph_3.json``  -- vertices (conflict points) + ``vertex_conflicts``;
* ``pairDistance_3.json`` -- along-path distance between every vertex pair.

The upstream geometry is a *stylised* intersection (all approach lanes collapsed
onto one entry point, 6 ft lane pitch) and cannot describe
``scenarios/original/cross{2,3,4}.net.xml``.  This module therefore builds an
equivalent graph **from the SUMO net** instead of renaming upstream vertices.

Modelling contract (must stay true to ``Instance.cpp`` / ``SIPP.cpp``)
---------------------------------------------------------------------
1. A **vertex** is a waypoint on one movement's path (stop line, a geometric
   crossing point inside the junction, or the exit point).  A path is
   ``[stop_line, conflict points..., exit]`` ordered by along-path distance.
   Different movements that occupy the *same physical point* get **separate**
   vertices that list each other in ``vertex_conflicts`` -- exactly the
   upstream convention (``WSR_0`` / ``WER_0`` share ``pos``).
2. Vertex names must pass the upstream direction classifier
   (``Instance.cpp:163-181``), which is a **substring** test on the name::

       EW / WE / NS / SN -> straight (2)
       EN / WS / NW / SE -> right    (1)
       otherwise         -> left     (0)

   so names are ``<FROM><TO><MOVE>_<k>`` with ``<MOVE>`` in ``S``/``R``/``L``
   and ``<FROM>``/``<TO>`` from junction geometry (not from edge names).
3. ``pairDistance[a][b]`` is the absolute along-path distance.  The upstream
   file is symmetric and the solver only ever queries forward offsets
   (``SIPP::estimate_cost``, ``SIPP.cpp:382``), so symmetric absolute distance
   is the faithful choice.
4. ``Instance.h:114`` declares ``bool samePoint[104][104]`` and
   ``Instance::loadSamePoint`` loops ``i < 104``.  A graph with **more than 104
   vertices would overflow the prebuilt binary**, so the generator refuses to
   emit one.  ``<= 104`` is safe (the extra rows stay unused).

Nothing here writes into ``third_party/``; outputs go wherever ``--out-dir``
points.
"""

from __future__ import annotations

import argparse
import json
import math
import xml.etree.ElementTree as ET
from itertools import combinations
from pathlib import Path

from shapely.geometry import LineString, Point

ROOT = Path(__file__).resolve().parents[2]

# Instance.h hard-codes ``bool samePoint[104][104]``.
MAX_VERTICES = 104

# Upstream collapses near-coincident crossings into a single conflict point.
POINT_TOL = 0.30          # m, cluster intersections along one path

DIR_TO_MOVE = {"l": "L", "s": "S", "r": "R",
               "L": "L", "S": "S", "R": "R"}


# --------------------------------------------------------------------------- #
# network parsing
# --------------------------------------------------------------------------- #
def load_network(path):
    """Parse a SUMO net into edges (with lane shapes) and connections."""
    root = ET.parse(path).getroot()
    edges, junctions, connections = {}, {}, []
    for e in root.findall("edge"):
        lanes = []
        for ln in e.findall("lane"):
            lanes.append({
                "id": ln.get("id"),
                "index": int(ln.get("index")),
                "length": float(ln.get("length")),
                "speed": float(ln.get("speed")),
                "shape": [tuple(float(v) for v in p.split(","))
                          for p in ln.get("shape").split()],
            })
        lanes.sort(key=lambda d: d["index"])
        edges[e.get("id")] = {
            "id": e.get("id"),
            "from": e.get("from"),
            "to": e.get("to"),
            "function": e.get("function", "normal"),
            "lanes": lanes,
        }
    for j in root.findall("junction"):
        junctions[j.get("id")] = {
            "id": j.get("id"),
            "type": j.get("type"),
            "x": float(j.get("x")),
            "y": float(j.get("y")),
        }
    for c in root.findall("connection"):
        connections.append({
            "from": c.get("from"),
            "to": c.get("to"),
            "fromLane": int(c.get("fromLane")),
            "toLane": int(c.get("toLane")),
            "via": c.get("via"),
            "dir": c.get("dir"),
        })
    return edges, junctions, connections


def lane_of(edges, lane_id):
    """Return (edge, lane) for a lane id such as ``:center_19_1``."""
    for e in edges.values():
        for ln in e["lanes"]:
            if ln["id"] == lane_id:
                return e, ln
    return None, None


def pick_junction(edges, connections):
    """Junction with the most incoming connections (the intersection under study)."""
    score = {}
    for c in connections:
        f, t = edges.get(c["from"]), edges.get(c["to"])
        if not f or not t:
            continue
        if f["function"] == "internal" or t["function"] == "internal":
            continue
        # a connection joins two non-internal edges at the junction
        # ``from.to == to.from``
        junction = f["to"]
        if junction != t["from"]:
            continue
        score[junction] = score.get(junction, 0) + 1
    if not score:
        raise SystemExit("no non-internal connections found in the net")
    return max(score, key=score.get)


def leg_letters(junction, junctions):
    """Compass letter of each leg node, derived from geometry only."""
    jx, jy = junctions[junction]["x"], junctions[junction]["y"]
    out = {}
    for jid, j in junctions.items():
        if jid == junction or jid.startswith(":"):
            continue
        dx, dy = j["x"] - jx, j["y"] - jy
        if abs(dx) < 1e-6 and abs(dy) < 1e-6:
            continue
        if abs(dx) >= abs(dy):
            out[jid] = "E" if dx > 0 else "W"
        else:
            out[jid] = "N" if dy > 0 else "S"
    return out


# --------------------------------------------------------------------------- #
# movements and paths
# --------------------------------------------------------------------------- #
def build_movements(edges, connections, junction, letters):
    """One entry per (inbound edge, outbound edge) pair, U-turns excluded."""
    inbound = {e["id"]: e["from"] for e in edges.values()
               if e["function"] != "internal" and e["to"] == junction}
    outbound = {e["id"]: e["to"] for e in edges.values()
                if e["function"] != "internal" and e["from"] == junction}

    by_pair = {}
    for c in connections:
        if c["from"] in inbound and c["to"] in outbound and c["via"]:
            by_pair.setdefault((c["from"], c["to"]), []).append(c)

    movements = []
    for (src, dst), conns in sorted(by_pair.items()):
        from_leg, to_leg = inbound[src], outbound[dst]
        if from_leg == to_leg:              # U-turn: not in routes.rou.xml
            continue
        a, b = letters.get(from_leg), letters.get(to_leg)
        if a is None or b is None:
            raise SystemExit("cannot assign compass letters to legs %r/%r"
                             % (from_leg, to_leg))
        move = DIR_TO_MOVE.get(conns[0]["dir"])
        if move is None:
            raise SystemExit("unsupported connection dir %r for %s->%s"
                             % (conns[0]["dir"], src, dst))
        movements.append({
            "from_edge": src, "to_edge": dst,
            "from_leg": from_leg, "to_leg": to_leg,
            "from_letter": a, "to_letter": b,
            "move": move,
            "prefix": a + b + move,
            "connections": sorted(conns, key=lambda c: c["fromLane"]),
        })
    return movements


def movement_paths(edges, movement, lane_mode):
    """Return one path dict per representative lane of a movement."""
    conns = movement["connections"]
    if lane_mode == "movement":
        conns = [conns[len(conns) // 2]]        # median lane of the movement
    out = []
    for c in conns:
        _, fl = lane_of(edges, "%s_%d" % (c["from"], c["fromLane"]))
        _, vl = lane_of(edges, c["via"])
        _, tl = lane_of(edges, "%s_%d" % (c["to"], c["toLane"]))
        if fl is None or vl is None or tl is None:
            raise SystemExit("cannot resolve lanes for connection %r" % (c,))
        coords = [fl["shape"][-1]] + list(vl["shape"]) + [tl["shape"][0]]
        clean = [coords[0]]
        for p in coords[1:]:
            if math.hypot(p[0] - clean[-1][0], p[1] - clean[-1][1]) > 1e-9:
                clean.append(p)
        line = LineString(clean)
        out.append({
            "label": "%s_L%d" % (movement["prefix"], c["fromLane"]),
            "line": line,
            "length": float(line.length),
            "fromLane": c["fromLane"],
            "toLane": c["toLane"],
            "via": c["via"],
        })
    return out


# --------------------------------------------------------------------------- #
# conflict points
# --------------------------------------------------------------------------- #
def _intersection_points(a, b):
    """All crossing points of two paths, plus the endpoints of shared segments."""
    inter = a.intersection(b)
    pts = []
    if inter.is_empty:
        return pts
    if inter.geom_type == "Point":
        pts = [inter]
    elif inter.geom_type == "MultiPoint":
        pts = list(inter.geoms)
    elif inter.geom_type in ("LineString", "MultiLineString"):
        segs = [inter] if inter.geom_type == "LineString" else list(inter.geoms)
        for s in segs:
            pts.extend([Point(s.coords[0]), Point(s.coords[-1])])
    elif inter.geom_type == "GeometryCollection":
        for g in inter.geoms:
            if g.geom_type == "Point":
                pts.append(g)
            elif g.geom_type in ("LineString", "MultiLineString"):
                segs = [g] if g.geom_type == "LineString" else list(g.geoms)
                for s in segs:
                    pts.extend([Point(s.coords[0]), Point(s.coords[-1])])
    return pts


def _cluster(entries, tol):
    """Merge points that lie within ``tol`` along one path."""
    out = []
    for offset, pt in sorted(entries, key=lambda e: e[0]):
        if out and abs(offset - out[-1][0]) <= tol:
            continue
        out.append((offset, pt))
    return out


def build_graph(edges, movements, lane_mode, point_tol=POINT_TOL,
                collapse_ends=True, trim_ends=False):
    """Return (vertices, paths, pair_distances) for all movements."""
    paths = []
    for mv in movements:
        for p in movement_paths(edges, mv, lane_mode):
            p["movement"] = mv
            p["points"] = []           # (offset, shapely Point)
            paths.append(p)

    for pa, pb in combinations(paths, 2):
        for pt in _intersection_points(pa["line"], pb["line"]):
            pa["points"].append((pa["line"].project(pt), pt))
            pb["points"].append((pb["line"].project(pt), pt))

    vertices = []
    for p in paths:
        # With ``per-lane`` every parallel internal lane is its own path, so the
        # vertex name must carry the lane; otherwise three straight lanes would
        # generate identical names.  ``movement`` mode keeps the old names so
        # that the already-recorded Stage-3 runs stay reproducible.
        p["token"] = (p["label"] if lane_mode == "per-lane"
                      else p["movement"]["prefix"])
        pts = _cluster(p["points"], point_tol)
        first = Point(p["line"].coords[0])
        last = Point(p["line"].coords[-1])
        if not pts or pts[0][0] > point_tol:
            pts.insert(0, (0.0, first))
        if pts[-1][0] < p["length"] - point_tol:
            pts.append((p["length"], last))
        pts[0] = (0.0, first)
        pts[-1] = (p["length"], last)
        if trim_ends:
            # Keep only genuine crossing points.  The stop-line / exit vertices
            # carry no crossing information: after upstream's per-approach
            # collapse they merely serialise the whole approach onto one point,
            # which caps the approach at 1/(Li/w + Li/v) ~= 0.60 veh/s -- less
            # than Table I MinD (0.80 veh/s).  Dropping them is also more
            # faithful to the geometry: vehicles on different lanes have
            # independent stop lines.
            pts = [pt for pt in pts if 0.0 + point_tol < pt[0] < p["length"] - point_tol]
            if len(pts) < 2:
                p["conflict_free"] = True
                p["ordered"] = []
                p["vertex_ids"] = []
                continue
            pts[0] = (pts[0][0], pts[0][1])
        p["conflict_free"] = False
        p["ordered"] = pts
        p["vertex_ids"] = []
        for k, (off, pt) in enumerate(pts):
            p["vertex_ids"].append(len(vertices))
            vertices.append({
                "name": "%s_%d" % (p["token"], k),
                "pos": [round(pt.x, 5), round(pt.y, 5)],
                "vertex_conflicts": [],
                "_path": p["label"],
                "_offset": off,
                "_kind": ("entry" if k == 0 else
                          "exit" if k == len(pts) - 1 else "internal"),
                "_edge": (p["movement"]["from_edge"] if k == 0 else
                          p["movement"]["to_edge"] if k == len(pts) - 1 else None),
            })

    # ------------------------------------------------------------------ #
    # conflict grouping
    #
    # Upstream collapses *all* lanes of one approach onto a single entry point
    # (``WSR_0`` and ``WER_0`` share ``pos``), and all movements leaving on the
    # same edge onto a single exit point (``WSR_1`` ~ ``NSR_7``).  That is not
    # cosmetic: ``PBS.cpp:268`` and ``PTNode.cpp:287`` evaluate
    # ``getConflictPoints(trajectory[0])[0]``, i.e. an **entry vertex with an
    # empty conflict list segfaults the binary**.  Collapsing entry/exit points
    # per approach/exit edge restores upstream's guarantee that every entry
    # vertex has at least one partner, and it is the conservative choice: two
    # vehicles of one approach can never be planned onto the same stop line at
    # the same time.
    # ------------------------------------------------------------------ #
    groups = {}
    if collapse_ends:
        for v in vertices:
            if v["_kind"] == "entry":
                groups.setdefault(("entry", v["_edge"]), []).append(v)
            elif v["_kind"] == "exit":
                groups.setdefault(("exit", v["_edge"]), []).append(v)
        for key, members in groups.items():
            cx = sum(m["pos"][0] for m in members) / len(members)
            cy = sum(m["pos"][1] for m in members) / len(members)
            for m in members:
                m["pos"] = [round(cx, 5), round(cy, 5)]

    for v in vertices:
        if collapse_ends and v["_kind"] in ("entry", "exit"):
            v["_group"] = (v["_kind"], v["_edge"])
        else:
            v["_group"] = ("pos", round(v["pos"][0], 2), round(v["pos"][1], 2))

    by_group = {}
    for v in vertices:
        by_group.setdefault(v["_group"], []).append(v)
    for group in by_group.values():
        for a in group:
            for b in group:
                if a is not b and b["name"] not in a["vertex_conflicts"]:
                    a["vertex_conflicts"].append(b["name"])

    # pair distances: symmetric absolute along-path offset difference
    pair = {}
    for p in paths:
        names = [vertices[i]["name"] for i in p["vertex_ids"]]
        offs = [o for o, _ in p["ordered"]]
        for i, ni in enumerate(names):
            row = pair.setdefault(ni, {})
            for j, nj in enumerate(names):
                row[nj] = round(abs(offs[j] - offs[i]), 5)

    return vertices, paths, pair


# --------------------------------------------------------------------------- #
# self-checks
# --------------------------------------------------------------------------- #
def upstream_direction(name):
    """Replicate Instance.cpp:163-181 exactly."""
    if any(s in name for s in ("EW", "WE", "NS", "SN")):
        return 2
    if any(s in name for s in ("EN", "WS", "NW", "SE")):
        return 1
    return 0


def check(vertices, paths, pair):
    problems = []
    want = {"S": 2, "R": 1, "L": 0}
    for p in paths:
        if p.get("conflict_free"):
            continue
        expect = want[p["movement"]["move"]]
        for k in range(len(p["vertex_ids"])):
            name = "%s_%d" % (p["token"], k)
            got = upstream_direction(name)
            if got != expect:
                problems.append("direction mismatch: %s -> %d, expected %d"
                                % (name, got, expect))
    if len(vertices) > MAX_VERTICES:
        problems.append("vertex budget exceeded: %d > %d "
                        "(Instance.h samePoint[104][104])"
                        % (len(vertices), MAX_VERTICES))
    name_to_v = {v["name"]: v for v in vertices}
    for v in vertices:
        for other in v["vertex_conflicts"]:
            if v["name"] not in name_to_v[other]["vertex_conflicts"]:
                problems.append("asymmetric conflict %s <-> %s" % (v["name"], other))
    # PBS.cpp:268 / PTNode.cpp:287 index [0] of an entry vertex's conflict list
    for p in paths:
        if p.get("conflict_free"):
            if p["vertex_ids"]:
                problems.append("conflict-free path %s still has vertices"
                                % p["label"])
            continue
        entry = vertices[p["vertex_ids"][0]]
        if not entry["vertex_conflicts"]:
            problems.append("entry vertex %s has no conflict partner -> "
                            "PBS.cpp:268 would index an empty vector"
                            % entry["name"])
        last = vertices[p["vertex_ids"][-1]]
        if not last["vertex_conflicts"]:
            problems.append("trajectory end %s has no conflict partner"
                            % last["name"])
    for p in paths:
        if p.get("conflict_free"):
            continue
        names = [vertices[i]["name"] for i in p["vertex_ids"]]
        for ni in names:
            for nj in names:
                if nj not in pair.get(ni, {}):
                    problems.append("missing pair distance %s -> %s" % (ni, nj))
    return problems


def summarise(vertices, paths, movements):
    per_move = {}
    for p in paths:
        mv = p["movement"]
        entry = per_move.setdefault(mv["prefix"], {
            "paths": 0, "vertices": 0,
            "from_edge": mv["from_edge"], "to_edge": mv["to_edge"],
            "move": mv["move"]})
        entry["paths"] += 1
        entry["vertices"] += len(p["vertex_ids"])
    return {
        "n_movements": len(movements),
        "n_paths": len(paths),
        "n_vertices": len(vertices),
        "vertex_budget": MAX_VERTICES,
        "n_conflict_pairs": sum(len(v["vertex_conflicts"]) for v in vertices) // 2,
        "per_movement": per_move,
    }


# --------------------------------------------------------------------------- #
# cli
# --------------------------------------------------------------------------- #
def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Generate the upstream PSL graph model from a SUMO net.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--net", required=True)
    ap.add_argument("--junction", default=None,
                    help="junction id (default: auto-detect the busiest one)")
    ap.add_argument("--lane-mode", choices=("movement", "per-lane"),
                    default="movement")
    ap.add_argument("--no-collapse", action="store_true",
                    help="do NOT collapse entry/exit points per approach/exit "
                         "edge (upstream does collapse them; without it the "
                         "prebuilt binary segfaults on unconflicted entries)")
    ap.add_argument("--trim-ends", action="store_true",
                    help="drop the stop-line and exit vertices; trajectories then "
                         "contain only real crossing points.  Needed for the "
                         "paper's densities: the per-approach collapse caps an "
                         "approach at ~0.60 veh/s < Table I MinD 0.80 veh/s")
    ap.add_argument("--point-tol", type=float, default=POINT_TOL,
                    help="merge along-path crossings closer than this (m)")
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args(argv)

    edges, junctions, connections = load_network(args.net)
    junction = args.junction or pick_junction(edges, connections)
    letters = leg_letters(junction, junctions)
    movements = build_movements(edges, connections, junction, letters)
    vertices, paths, pair = build_graph(edges, movements, args.lane_mode,
                                        point_tol=args.point_tol,
                                        collapse_ends=not args.no_collapse,
                                        trim_ends=args.trim_ends)

    problems = check(vertices, paths, pair)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    graph = {
        "vertices": [{k: v for k, v in vt.items() if not k.startswith("_")}
                     for vt in vertices],
        "edges": [{"fro": "%s_%d" % (p["token"], k),
                   "to": "%s_%d" % (p["token"], k + 1),
                   "value": round(p["ordered"][k + 1][0] - p["ordered"][k][0], 5)}
                  for p in paths if not p.get("conflict_free")
                  for k in range(len(p["ordered"]) - 1)],
    }
    (out / "graph.json").write_text(json.dumps(graph, indent=1))
    (out / "pairDistance.json").write_text(json.dumps(pair, indent=1))
    (out / "paths.json").write_text(json.dumps({
        "junction": junction,
        "lane_mode": args.lane_mode,
        "trim_ends": args.trim_ends,
        "paths": [{
            "label": p["label"],
            "prefix": p["token"],
            "movement_prefix": p["movement"]["prefix"],
            "from_edge": p["movement"]["from_edge"],
            "to_edge": p["movement"]["to_edge"],
            "move": p["movement"]["move"],
            "fromLane": p["fromLane"],
            "toLane": p["toLane"],
            "via": p["via"],
            "length": round(p["length"], 5),
            "conflict_free": bool(p.get("conflict_free")),
            "vertices": [vertices[i]["name"] for i in p["vertex_ids"]],
            "offsets": [round(o, 5) for o, _ in p["ordered"]],
            "polyline": [[round(x, 5), round(y, 5)] for x, y in p["line"].coords],
        } for p in paths],
    }, indent=1))
    report = summarise(vertices, paths, movements)
    report["trim_ends"] = args.trim_ends
    report["n_conflict_free_paths"] = sum(1 for p in paths
                                          if p.get("conflict_free"))
    report.update({"net": str(args.net), "junction": junction,
                   "lane_mode": args.lane_mode,
                   "problems": problems, "ok": not problems})
    (out / "instance_report.json").write_text(json.dumps(report, indent=1))

    print(json.dumps({k: report[k] for k in
                      ("net", "junction", "lane_mode", "n_movements", "n_paths",
                       "n_vertices", "vertex_budget", "n_conflict_pairs", "ok")},
                     indent=1))
    for p in problems[:20]:
        print("PROBLEM:", p)
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())

