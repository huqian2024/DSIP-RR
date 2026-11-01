#!/usr/bin/env python3
"""Task 03 - read-only geometry / route / conflict analysis (cross3).

Reads ONLY in-workspace files:
    scenarios/original/cross3.net.xml
    scenarios/original/routes.rou.xml

and prints
  1. intersection geometry (junction type/position, approach lanes, stop lines);
  2. the 12 OD movements used by the route file and the internal lanes each one
     traverses (taken from the ``via`` attribute of <connection>);
  3. a movement-level conflict matrix derived from the *geometry* of the
     internal lane shapes (shapely), because the ``center`` junction is
     ``unregulated`` and carries no <request>/foes table;
  4. maximal sets of movements that are mutually non-conflicting.

Nothing is written to disk and no SUMO process is started.

IMPORTANT: item 3 is a geometric derivation, not a statement of the paper's or
SUMO's own conflict model.  It must be validated before being used as a
control-table for FCFS.
"""

import itertools
import xml.etree.ElementTree as ET

from shapely.geometry import LineString, Point

NET = "scenarios/original/cross3.net.xml"
ROU = "scenarios/original/routes.rou.xml"
SHARED_ORIGIN_TOL = 1.5   # m: intersections this close to both lane starts are
                          # treated as the shared stop line, not a conflict
MIN_OVERLAP = 0.5         # m: intersection length above which we call it overlap


def parse_net(path):
    root = ET.parse(path).getroot()
    edges, juncs, conns = {}, {}, []
    for e in root.findall("edge"):
        lanes = []
        for ln in e.findall("lane"):
            shape = tuple(tuple(float(v) for v in p.split(","))
                          for p in ln.get("shape").split())
            lanes.append({
                "id": ln.get("id"),
                "index": int(ln.get("index")),
                "speed": float(ln.get("speed")),
                "length": float(ln.get("length")),
                "shape": shape,
            })
        edges[e.get("id")] = {
            "id": e.get("id"),
            "function": e.get("function", "normal"),
            "from": e.get("from"),
            "to": e.get("to"),
            "lanes": lanes,
        }
    for j in root.findall("junction"):
        shape = tuple(tuple(float(v) for v in p.split(","))
                      for p in (j.get("shape") or "").split()) if j.get("shape") else ()
        juncs[j.get("id")] = {
            "x": float(j.get("x")),
            "y": float(j.get("y")),
            "type": j.get("type"),
            "incLanes": (j.get("incLanes") or "").split(),
            "intLanes": (j.get("intLanes") or "").split(),
            "shape": shape,
            "n_request": len(j.findall("request")),
        }
    for c in root.findall("connection"):
        conns.append({
            "from": c.get("from"),
            "to": c.get("to"),
            "fromLane": int(c.get("fromLane")),
            "toLane": int(c.get("toLane")),
            "via": c.get("via"),
            "dir": c.get("dir"),
        })
    return edges, juncs, conns


def parse_routes(path):
    root = ET.parse(path).getroot()
    routes = {r.get("id"): r.get("edges").split() for r in root.findall("route")}
    flows = [(f.get("id"), f.get("route"), int(f.get("number")))
             for f in root.findall("flow")]
    return routes, flows


def classify(a, b):
    """Return None (no conflict) or 'cross' / 'overlap' for two internal lanes."""
    inter = a.intersection(b)
    if inter.is_empty:
        return None
    if inter.geom_type in ("LineString", "MultiLineString"):
        return "overlap" if inter.length > MIN_OVERLAP else None
    pts = []
    if inter.geom_type == "Point":
        pts = [inter]
    elif inter.geom_type == "MultiPoint":
        pts = list(inter.geoms)
    elif inter.geom_type == "GeometryCollection":
        pts = [g for g in inter.geoms if g.geom_type == "Point"]
    else:
        return inter.geom_type.lower()
    for p in pts:
        near_a = p.distance(Point(a.coords[0])) < SHARED_ORIGIN_TOL
        near_b = p.distance(Point(b.coords[0])) < SHARED_ORIGIN_TOL
        if not (near_a and near_b):
            return "cross"
    return None


def main():
    edges, juncs, conns = parse_net(NET)
    routes, flows = parse_routes(ROU)
    center = juncs["center"]

    print("=" * 78)
    print("1) INTERSECTION GEOMETRY (from cross3.net.xml)")
    print("=" * 78)
    xs = [p[0] for p in center["shape"]]
    ys = [p[1] for p in center["shape"]]
    print("junction 'center': type=%s  pos=(%.1f, %.1f)  internal lanes=%d  "
          "<request> elements=%d"
          % (center["type"], center["x"], center["y"],
             len(center["intLanes"]), center["n_request"]))
    print("junction shape bbox: x in [%.2f, %.2f], y in [%.2f, %.2f]  "
          "(conflict area extent)" % (min(xs), max(xs), min(ys), max(ys)))
    print()
    print("approach edges (incoming) / exit edges (outgoing):")
    for eid in ("north2center", "east2center", "south2center", "west2center"):
        e = edges[eid]
        lens = [ln["length"] for ln in e["lanes"]]
        stop = e["lanes"][0]["shape"][-1]
        print("  %-13s %d lanes, length=%.2f m, speed=%.2f m/s, stop line at (%.2f, %.2f)"
              % (eid, len(e["lanes"]), lens[0], e["lanes"][0]["speed"], stop[0], stop[1]))
    for eid in ("center2north", "center2east", "center2south", "center2west"):
        e = edges[eid]
        print("  %-13s %d lanes, length=%.2f m (exit)"
              % (eid, len(e["lanes"]), e["lanes"][0]["length"]))
    print()
    print("internal (junction) edges: %d, connections: %d"
          % (sum(1 for e in edges.values() if e["function"] == "internal"), len(conns)))

    # ---- movements ---------------------------------------------------------
    movements = []
    for rid in sorted(routes):
        eds = routes[rid]
        fr, to = eds[0], eds[-1]
        mc = [c for c in conns if c["from"] == fr and c["to"] == to]
        movements.append({
            "id": rid,
            "from": fr,
            "to": to,
            "dir": mc[0]["dir"] if mc else "?",
            "fromLanes": sorted({c["fromLane"] for c in mc}),
            "vias": [c["via"] for c in mc],
        })

    print()
    print("=" * 78)
    print("2) THE 12 OD MOVEMENTS (from routes.rou.xml + <connection> of the net)")
    print("=" * 78)
    print("%-12s %-13s %-13s %-4s %-10s %s"
          % ("route", "from", "to", "dir", "fromLanes", "internal lanes (via)"))
    for m in movements:
        print("%-12s %-13s %-13s %-4s %-10s %s"
              % (m["id"], m["from"], m["to"], m["dir"],
                 ",".join(map(str, m["fromLanes"])), " ".join(m["vias"])))
    print()
    print("flow counts in routes.rou.xml: %d flows, total %d vehicles over 0-1000 s"
          % (len(flows), sum(f[2] for f in flows)))
    dirs = {}
    for m in movements:
        dirs[m["dir"]] = dirs.get(m["dir"], 0) + 1
    print("direction mix: %s  (s=straight, l=left, r=right)"
          % ", ".join("%s=%d" % kv for kv in sorted(dirs.items())))

    # ---- geometric conflicts ----------------------------------------------
    internal = {}
    for e in edges.values():
        if e["function"] == "internal":
            for ln in e["lanes"]:
                internal[ln["id"]] = LineString(ln["shape"])

    n = len(movements)
    conflict = [[None] * n for _ in range(n)]
    detail = {}
    for i, j in itertools.combinations(range(n), 2):
        kinds, points = set(), []
        for va in movements[i]["vias"]:
            for vb in movements[j]["vias"]:
                if va not in internal or vb not in internal:
                    continue
                kind = classify(internal[va], internal[vb])
                if kind:
                    kinds.add(kind)
                    inter = internal[va].intersection(internal[vb])
                    if inter.geom_type == "Point":
                        points.append((round(inter.x, 2), round(inter.y, 2)))
        if kinds:
            kind = "overlap" if "overlap" in kinds else "cross"
            conflict[i][j] = conflict[j][i] = kind
            detail[(i, j)] = (kind, sorted(set(points)))

    print()
    print("=" * 78)
    print("3) MOVEMENT-LEVEL CONFLICTS, DERIVED FROM INTERNAL-LANE GEOMETRY")
    print("   (the center junction has no request/foes table, so this is a")
    print("    geometric derivation, NOT a validated control table)")
    print("=" * 78)
    labels = ["m%02d" % (i + 1) for i in range(n)]
    print("     " + " ".join("%-4s" % lb for lb in labels))
    for i in range(n):
        row = []
        for j in range(n):
            row.append("--" if i == j else {"cross": " X ", "overlap": " = "}.get(conflict[i][j], " . "))
        print("%-4s " % labels[i] + " ".join("%-4s" % c for c in row))
    print("legend: X = crossing, = = lane overlap/merge, . = no geometric conflict")
    print()
    print("legend table:")
    for i, m in enumerate(movements):
        print("  %s  %-12s %-13s -> %-13s dir=%s conflicts_with=%d"
              % (labels[i], m["id"], m["from"], m["to"], m["dir"],
                 sum(1 for j in range(n) if conflict[i][j])))
    print()
    print("conflicting movement pairs and the crossing point(s):")
    for (i, j), (kind, pts) in sorted(detail.items()):
        print("  %s x %s  %-8s %s" % (labels[i], labels[j], kind,
                                      pts[:4] if pts else "(overlap, no single point)"))

    # ---- maximal compatible sets -----------------------------------------
    compatible = [[conflict[i][j] is None for j in range(n)] for i in range(n)]
    maximal = []
    for size in range(n, 0, -1):
        for combo in itertools.combinations(range(n), size):
            if not all(compatible[a][b] for a, b in itertools.combinations(combo, 2)):
                continue
            if any(set(combo) <= set(mx) for mx in maximal):
                continue
            maximal.append(combo)
    maximal.sort(key=len, reverse=True)

    print()
    print("=" * 78)
    print("4) MAXIMAL MUTUALLY NON-CONFLICTING MOVEMENT SETS")
    print("=" * 78)
    for combo in maximal:
        print("  size %2d : %s" % (len(combo),
                                   ", ".join(movements[i]["id"] for i in combo)))
    print()
    print("NOTE: a size-%d set is the largest group that could in principle enter"
          % (max(len(c) for c in maximal) if maximal else 0))
    print("      together without geometric crossing. This is a geometric upper")
    print("      bound only; timing/safety margins are NOT included.")


if __name__ == "__main__":
    main()
