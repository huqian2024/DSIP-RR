"""Provisional movement-level conflict model for one intersection.

Sources
-------
1. ``scenarios/original/cross3.net.xml`` and ``scenarios/original/routes.rou.xml``
   -- geometric crossing points between the *internal lane centrelines* of two
   movements (identical method to ``scenarios/smoke/net_analysis.py``, Task 03
   step 3).  The resulting matrix is additionally cross-checked against the
   matrix printed in ``results/smoke/net_analysis.log`` by
   :func:`validate_against_net_analysis_log`.
2. Structural checks that geometry alone cannot provide:
   * shared **downstream** lane  -> potential merge conflict after the exit;
   * shared **upstream** lane    -> car following, *not* a crossing conflict.

All of it is **PROVISIONAL**.  The ``center`` junction is ``unregulated`` and
carries no ``<request>/<foes>`` table, so the network provides no authoritative
right-of-way model.  Two movements whose centrelines do not intersect are NOT
thereby proven safe to run simultaneously: vehicles have width, turning paths
are smoothed, and clearance times are unknown.  Occupancy/safety margins must
be fixed by the author before any of this is used for control.
"""

import itertools
import re
from pathlib import Path
import xml.etree.ElementTree as ET

from shapely.geometry import LineString, Point

ROOT = Path(__file__).resolve().parents[2]
NET_PATH = ROOT / "scenarios" / "original" / "cross3.net.xml"
ROU_PATH = ROOT / "scenarios" / "original" / "routes.rou.xml"
TASK03_LOG = ROOT / "results" / "smoke" / "net_analysis.log"

SHARED_ORIGIN_TOL = 1.5   # m, same convention as Task 03
MIN_OVERLAP = 0.5         # m
PROVISIONAL = True


def load_network(path=NET_PATH):
    """Return (edges, junctions, connections) parsed from a SUMO net file."""
    root = ET.parse(path).getroot()
    edges, junctions, connections = {}, {}, []
    for e in root.findall("edge"):
        lanes = []
        for ln in e.findall("lane"):
            shape = tuple(tuple(float(v) for v in p.split(","))
                          for p in ln.get("shape").split())
            lanes.append({"id": ln.get("id"), "index": int(ln.get("index")),
                          "length": float(ln.get("length")), "shape": shape})
        edges[e.get("id")] = {"id": e.get("id"),
                              "function": e.get("function", "normal"),
                              "lanes": lanes}
    for j in root.findall("junction"):
        junctions[j.get("id")] = {"id": j.get("id"),
                                  "type": j.get("type"),
                                  "x": float(j.get("x")), "y": float(j.get("y")),
                                  "intLanes": (j.get("intLanes") or "").split(),
                                  "n_request": len(j.findall("request"))}
    for c in root.findall("connection"):
        connections.append({"from": c.get("from"), "to": c.get("to"),
                            "fromLane": int(c.get("fromLane")),
                            "toLane": int(c.get("toLane")),
                            "via": c.get("via"), "dir": c.get("dir")})
    return edges, junctions, connections


def load_routes(path=ROU_PATH):
    root = ET.parse(path).getroot()
    return {r.get("id"): r.get("edges").split() for r in root.findall("route")}


def build_movements(edges, connections, routes):
    """One entry per route, ordered by route id -> movement ids m01, m02, ..."""
    movements = []
    for index, rid in enumerate(sorted(routes)):
        sub = routes[rid]
        src, dst = sub[0], sub[-1]
        conns = [c for c in connections if c["from"] == src and c["to"] == dst]
        movements.append({
            "index": index,
            "id": "m%02d" % (index + 1),
            "route": rid,
            "from_edge": src,
            "to_edge": dst,
            "dir": conns[0]["dir"] if conns else "?",
            "from_lanes": sorted({c["fromLane"] for c in conns}),
            "to_lanes": sorted({c["toLane"] for c in conns}),
            "vias": [c["via"] for c in conns],
        })
    return movements


def _classify(a, b):
    inter = a.intersection(b)
    if inter.is_empty:
        return None
    if inter.geom_type in ("LineString", "MultiLineString"):
        return "overlap" if inter.length > MIN_OVERLAP else None
    if inter.geom_type == "Point":
        points = [inter]
    elif inter.geom_type == "MultiPoint":
        points = list(inter.geoms)
    elif inter.geom_type == "GeometryCollection":
        points = [g for g in inter.geoms if g.geom_type == "Point"]
    else:
        return inter.geom_type.lower()
    for p in points:
        near_a = p.distance(Point(a.coords[0])) < SHARED_ORIGIN_TOL
        near_b = p.distance(Point(b.coords[0])) < SHARED_ORIGIN_TOL
        if not (near_a and near_b):
            return "cross"
    return None


def geometric_conflicts(edges, movements):
    """Crossing/overlap relations derived from internal lane centrelines."""
    internal = {}
    for e in edges.values():
        if e["function"] == "internal":
            for ln in e["lanes"]:
                internal[ln["id"]] = LineString(ln["shape"])
    out = {}
    for a, b in itertools.combinations(movements, 2):
        kinds, points = set(), []
        for va in a["vias"]:
            for vb in b["vias"]:
                if va not in internal or vb not in internal:
                    continue
                kind = _classify(internal[va], internal[vb])
                if kind:
                    kinds.add(kind)
                    inter = internal[va].intersection(internal[vb])
                    if inter.geom_type == "Point":
                        points.append((round(inter.x, 2), round(inter.y, 2)))
        if kinds:
            out[(a["index"], b["index"])] = {
                "kind": "overlap" if "overlap" in kinds else "cross",
                "points": sorted(set(points)),
                "basis": "internal lane centreline geometry (PROVISIONAL)",
            }
    return out


def following_relations(movements):
    """Movements sharing an upstream lane -> car following, not crossing."""
    out = {}
    for a, b in itertools.combinations(movements, 2):
        if a["from_edge"] == b["from_edge"]:
            shared = sorted(set(a["from_lanes"]) & set(b["from_lanes"]))
            if shared:
                out[(a["index"], b["index"])] = {
                    "shared_from_lanes": shared,
                    "basis": "same approach lane -> longitudinal car following "
                             "(handled by SUMO IDM, NOT a crossing conflict)",
                }
    return out


def merge_relations(movements):
    """Movements sharing a downstream lane -> possible merge conflict."""
    out = {}
    for a, b in itertools.combinations(movements, 2):
        if a["to_edge"] == b["to_edge"]:
            shared = sorted(set(a["to_lanes"]) & set(b["to_lanes"]))
            if shared:
                out[(a["index"], b["index"])] = {
                    "shared_to_lanes": shared,
                    "basis": "shared downstream lane -> possible merge conflict "
                             "(PROVISIONAL, not covered by lane-centreline crossing)",
                }
    return out


def validate_against_net_analysis_log(path, movements, matrix):
    """Compare our recomputed matrix with the matrix printed in Task 03."""
    result = {"path": str(path), "found": False, "match": None, "mismatches": []}
    p = Path(path)
    if not p.exists():
        return result
    text = p.read_text(encoding="utf-8", errors="replace")
    start = text.find("3) MOVEMENT-LEVEL CONFLICTS")
    if start < 0:
        return result
    rows, n = {}, len(movements)
    for line in text[start:].splitlines():
        m = re.match(r"^(m\d\d)\s+(.*)$", line.rstrip())
        if not m:
            continue
        tokens = re.findall(r"--|X|=|\.", m.group(2))
        if len(tokens) == n:
            rows[m.group(1)] = tokens
        if len(rows) == n:
            break
    if len(rows) != n:
        return result
    result["found"] = True
    symbol = {"cross": "X", "overlap": "=", None: "."}
    for i, mi in enumerate(movements):
        tokens = rows[mi["id"]]
        for j in range(n):
            expected = "--" if i == j else symbol[matrix[i][j]]
            if tokens[j] != expected:
                result["mismatches"].append(
                    "%s x m%02d: task03=%s recomputed=%s"
                    % (mi["id"], j + 1, tokens[j], expected))
    result["match"] = not result["mismatches"]
    return result


class ConflictModel:
    """Movement table + provisional conflict matrix for one intersection."""

    def __init__(self, net_path=NET_PATH, rou_path=ROU_PATH, task03_log=TASK03_LOG):
        self.edges, self.junctions, self.connections = load_network(net_path)
        self.routes = load_routes(rou_path)
        self.movements = build_movements(self.edges, self.connections, self.routes)
        self.route_to_index = {m["route"]: m["index"] for m in self.movements}
        self.geometric = geometric_conflicts(self.edges, self.movements)
        self.following = following_relations(self.movements)
        self.merges = merge_relations(self.movements)
        self.matrix = self._build_matrix()
        self.symmetric = self._check_symmetric()
        self.task03_check = validate_against_net_analysis_log(
            task03_log, self.movements, self.matrix)
        self.center = self.junctions.get("center", {})

    def _build_matrix(self):
        n = len(self.movements)
        matrix = [[None] * n for _ in range(n)]
        for (a, b), info in self.geometric.items():
            matrix[a][b] = matrix[b][a] = info["kind"]
        return matrix

    def _check_symmetric(self):
        n = len(self.movements)
        return all(self.matrix[i][j] == self.matrix[j][i]
                   for i in range(n) for j in range(n))

    def index_of_route(self, route_id):
        return self.route_to_index.get(route_id)

    def movement(self, index):
        return self.movements[index]

    def conflicts(self, i, j):
        return self.matrix[i][j] is not None

    def partners(self, i):
        return [j for j in range(len(self.movements))
                if j != i and self.matrix[i][j] is not None]

    def merge_partners(self, i):
        return [j for j in range(len(self.movements))
                if i != j and (min(i, j), max(i, j)) in self.merges]

    def label(self, index):
        return self.movements[index]["id"]

    def summary(self):
        dirs = {}
        for m in self.movements:
            dirs[m["dir"]] = dirs.get(m["dir"], 0) + 1
        return {
            "n_movements": len(self.movements),
            "direction_mix": dirs,
            "junction_type": self.center.get("type"),
            "junction_request_elements": self.center.get("n_request"),
            "n_geometric_conflict_pairs": len(self.geometric),
            "n_merge_pairs": len(self.merges),
            "n_following_pairs": len(self.following),
            "matrix_symmetric": self.symmetric,
            "task03_matrix_check": self.task03_check,
            "provisional": PROVISIONAL,
        }
