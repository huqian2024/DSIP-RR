"""Build the upstream PSL ``vehicleArrival.json`` from a SUMO route file.

The upstream ``Instance::loadVehicles`` (``Instance.cpp:44-95``) reads, per
vehicle::

    ag.name                <- doc[id]["id"]          (unused downstream)
    ag.importance          <- doc[id]["importance"]
    ag.earliest_start_time <- doc[id]["arrivalTime"]
    ag.trajectory          <- doc[id]["trajectory"]  (vertex names)

``lane`` is written by upstream but **not read** by the binary; it is emitted
here for provenance only.  ``Instance.cpp`` also hard-codes ``v_min = 3``,
``v_max = 15`` and ``length = 5``, so those are *not* configurable here -- see
``docs/baselines/psl-reproduction.md`` for the kinematics deviation.

Where does ``arrivalTime`` come from?
``arrivalTime`` is the earliest time the vehicle's front can reach the stop
line of its approach.  Two estimates are produced:

* ``observed``  -- the first FCD timestep in which the vehicle sits on an
  internal (``:``) lane, i.e. it already crossed the stop line.  This is
  measured in a reference SUMO run that has **no intersection control** (the
  junction is ``uncontrolled``), so vehicles only decelerate for downstream
  blockage and that run may actually collide.  Never use it as a safety
  reference; it only supplies timing.
* ``freeflow``  -- constant-acceleration kinematics from the vehicle's first
  FCD observation (position, speed, lane) to the stop line, using the vType's
  ``accel``/``maxSpeed``.  This is the model that matches the upstream
  Poisson-arrival abstraction.  **Default.**

The reference run is started once per invocation and its FCD file is kept, so
every request time in the manifest is reproducible from a stored artefact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net_to_graph import load_network, lane_of  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
VEH_LENGTH = 5.0          # Instance.cpp loadVehicles(): ag.length = 5


def parse_routes(rou_path):
    root = ET.parse(rou_path).getroot()
    routes = {r.get("id"): r.get("edges").split() for r in root.findall("route")}
    vehicles = {}
    for v in root.findall("vehicle"):
        vehicles[v.get("id")] = {"route": v.get("route"),
                                 "depart": float(v.get("depart"))}
    return routes, vehicles


def parse_vtype(typ_path):
    """accel / maxSpeed / length of the first vType (all flows use ``car``)."""
    root = ET.parse(typ_path).getroot()
    for vt in root.iter("vType"):
        return {"id": vt.get("id"),
                "accel": float(vt.get("accel")),
                "maxSpeed": float(vt.get("maxSpeed")),
                "length": float(vt.get("length")),
                "decel": float(vt.get("decel")),
                "in_vTypeDistribution": root.tag == "vTypeDistribution"}
    raise SystemExit("no <vType> found in %s" % typ_path)


def run_reference_sumo(net, rou, typ, begin, end, step, seed, outdir,
                       source="tripinfo"):
    """Reference SUMO run (no intersection control); emits route + timing data.

    ``source="tripinfo"`` (default) writes ``--tripinfo-output`` with
    ``write-unfinished``: every vehicle then has ``depart``/``departLane``/
    ``departPos``/``departSpeed``.  This is far smaller than FCD and therefore
    works for the full 1000 s experiment horizon.

    ``source="fcd"`` keeps the original first-observation route (small windows).
    """
    vehroute = outdir / "vehroute.xml"
    cmd = ["sumo", "-n", str(net), "-r", str(rou), "-a", str(typ),
           "--begin", str(begin), "--end", str(end),
           "--step-length", str(step),
           "--vehroute-output", str(vehroute),
           "--vehroute-output.exit-times", "true",
           "--vehroute-output.write-unfinished", "true",
           "--no-step-log", "true", "--seed", str(seed),
           "--duration-log.statistics", "true"]
    if source == "fcd":
        fcd = outdir / "fcd.xml"
        cmd += ["--fcd-output", str(fcd)]
        artifact = fcd
    else:
        trip = outdir / "tripinfo.xml"
        cmd += ["--tripinfo-output", str(trip),
                "--tripinfo-output.write-unfinished", "true"]
        artifact = trip
    log = outdir / "reference_sumo.log"
    with open(log, "w") as fh:
        rc = subprocess.call(cmd, stdout=fh, stderr=subprocess.STDOUT)
    if rc != 0:
        raise SystemExit("reference SUMO run failed (rc=%d), see %s" % (rc, log))
    return cmd, artifact, vehroute, log


def parse_vehroute(path):
    """vehicle id -> route edges, from ``--vehroute-output`` (flow vehicles)."""
    root = ET.parse(path).getroot()
    out = {}
    for v in root.iter("vehicle"):
        r = v.find("route")
        if r is not None:
            out[v.get("id")] = r.get("edges").split()
    return out


def tripinfo_departures(path):
    """vehicle id -> {'t','pos','speed','lane'} at insertion.

    ``tripinfo`` is written when a trip ends (or is still running with
    ``write-unfinished``), so this covers the whole horizon, not just the first
    observation.  Field names: ``depart``, ``departPos``, ``departSpeed``,
    ``departLane``.
    """
    root = ET.parse(path).getroot()
    out = {}
    for ti in root.iter("tripinfo"):
        vid = ti.get("id")
        try:
            out[vid] = {"t": float(ti.get("depart")),
                        "pos": float(ti.get("departPos")),
                        "speed": float(ti.get("departSpeed")),
                        "lane": ti.get("departLane")}
        except (TypeError, ValueError):
            continue
    return out



def first_observations(fcd_path):
    """vehicle id -> {'t','pos','speed','lane'} at the first timestep seen."""
    first, seen = {}, set()
    t = None
    # ``start`` on <timestep> fires before its <vehicle> children, which is what
    # we need: the timestamp must be known when the first <vehicle> is read.
    for event, elem in ET.iterparse(str(fcd_path), events=("start", "end")):
        if event == "start":
            if elem.tag == "timestep":
                t = float(elem.get("time"))
            continue
        if elem.tag == "timestep":
            elem.clear()
        elif elem.tag == "vehicle":
            vid = elem.get("id")
            if vid not in seen:
                seen.add(vid)
                first[vid] = {"t": t,
                              "pos": float(elem.get("pos")),
                              "speed": float(elem.get("speed")),
                              "lane": elem.get("lane")}
            elem.clear()
    return first


def freeflow_time(distance, v0, accel, vmax):
    """Time to cover ``distance`` accelerating at ``accel`` up to ``vmax``."""
    if distance <= 0:
        return 0.0
    if v0 >= vmax:
        return distance / vmax
    t_acc = (vmax - v0) / accel
    d_acc = v0 * t_acc + 0.5 * accel * t_acc * t_acc
    if distance <= d_acc:
        return (-v0 + (v0 * v0 + 2 * accel * distance) ** 0.5) / accel
    return t_acc + (distance - d_acc) / vmax


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def flow_departures(rou_path, routes, paths, vt, seed_offset=0):
    """Generate departures from the ``<flow>`` definitions themselves.

    Why not read them back from a SUMO run?  At HighD/MaxD the approach edges
    (86 m, 3 lanes) cannot store the queue, so a reference run inserts only part
    of the demand -- measured at density 5: 828 of 2400 vehicles inside 300 s,
    and the realised coordinated count was 2026 (MinD) vs 2063 (MaxD), i.e. the
    density dimension collapses.  The *demand* is the departure process the flow
    file specifies, not the subset SUMO managed to insert.

    Each flow is ``departInterval="normal(mu, sigma)"`` with ``number=N``.  That
    process is resampled here with a per-flow RNG seeded from the flow's own
    ``seed`` attribute, so it is reproducible.  It is statistically equivalent to
    SUMO's realisation but not bit-identical -- recorded in the manifest as
    ``demand_source: flow_resample``.
    """
    import random

    root = ET.parse(rou_path).getroot()
    by_pair = {}
    for p in paths:
        by_pair.setdefault((p["from_edge"], p["to_edge"]), []).append(p)
    lane_len = {}
    for e in root.iter("lane"):                # not present in .rou.xml
        lane_len[e.get("id")] = float(e.get("length"))

    departures, route_of = {}, {}
    for fl in root.findall("flow"):
        route_id = fl.get("route")
        route_edges = routes.get(route_id)
        if not route_edges or len(route_edges) < 2:
            continue
        cand = by_pair.get((route_edges[0], route_edges[-1]))
        if not cand:
            continue
        number = int(fl.get("number") or 0)
        begin = float(fl.get("begin") or 0.0)
        end = float(fl.get("end") or 1e9)
        spec = fl.get("departInterval") or "normal(1,1)"
        mu, sigma = 1.0, 0.0
        if spec.startswith("normal("):
            mu, sigma = (float(x) for x in spec[7:-1].split(","))
        elif spec.startswith("exp("):
            mu = float(spec[4:-1])
        rng = random.Random(int(fl.get("seed") or 0) + seed_offset)
        t = begin
        for k in range(1, number + 1):
            t += max(rng.gauss(mu, sigma), 0.1) if sigma > 0 else mu
            if t > end:
                break
            vid = "%s.%d" % (fl.get("id"), k)
            path = cand[rng.randrange(len(cand))]
            pos = rng.uniform(0.0, max(1.0, path["length"] - 15.0))
            speed = rng.uniform(0.0, vt["maxSpeed"])
            departures[vid] = {"t": t, "pos": pos, "speed": speed,
                               "lane": "%s_%d" % (path["from_edge"],
                                                  path["fromLane"])}
            route_of[vid] = route_edges
    return departures, route_of


def build_requests(edges, fcd_first, routes, vehicles, vehroute_routes, vt,
                   paths_by_pair, arrival_model, limit, paths_by_key=None):
    """Assemble one request per vehicle that reached the junction."""
    requests, rejected = [], []
    for vid, obs in fcd_first.items():
        lane_id = obs["lane"]
        if not lane_id or lane_id.startswith(":"):
            rejected.append([vid, "first observation already inside the junction"])
            continue
        edge, lane = lane_of(edges, lane_id)
        if edge is None:
            rejected.append([vid, "unknown lane %r" % lane_id])
            continue
        # flow-generated vehicles are not <vehicle> elements in the route file,
        # so the realised route comes from --vehroute-output
        route_edges = vehroute_routes.get(vid)
        if not route_edges:
            route_id = vehicles.get(vid, {}).get("route")
            route_edges = routes.get(route_id) if route_id else None
        if not route_edges or len(route_edges) < 2:
            rejected.append([vid, "no 2-edge route"])
            continue
        pair = (route_edges[0], route_edges[-1])
        path = ((paths_by_key or {}).get((pair[0], pair[1], lane["index"]))
                or paths_by_pair.get(pair))
        if path is None:
            rejected.append([vid, "movement %r not in the generated graph" % (pair,)])
            continue

        remaining = lane["length"] - obs["pos"] - VEH_LENGTH
        vcap = min(vt["maxSpeed"], lane["speed"])
        requests.append({
            "vehicle_id": vid,
            "route": vehicles.get(vid, {}).get("route") or
                     " ".join(route_edges),
            "from_edge": pair[0],
            "to_edge": pair[1],
            "prefix": path["prefix"],
            "lane": lane["index"],
            "lane_id": lane_id,
            "first_seen_t": obs["t"],
            "first_seen_pos": obs["pos"],
            "first_seen_speed": obs["speed"],
            "remaining_to_stopline_m": round(remaining, 4),
            "arrival_freeflow": round(
                obs["t"] + freeflow_time(remaining, obs["speed"],
                                         vt["accel"], vcap), 6),
            "trajectory": path["vertices"],
        })
    requests.sort(key=lambda r: (r["arrival_freeflow"], r["vehicle_id"]))
    if limit:
        requests = requests[:limit]
    return requests, rejected


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Build upstream PSL vehicleArrival.json from a SUMO route file.")
    ap.add_argument("--net", required=True)
    ap.add_argument("--rou", required=True)
    ap.add_argument("--typ", required=True)
    ap.add_argument("--instance-dir", required=True,
                    help="output directory of net_to_graph.py (needs paths.json)")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--begin", type=float, default=0.0)
    ap.add_argument("--end", type=float, default=60.0)
    ap.add_argument("--step", type=float, default=0.1)
    ap.add_argument("--seed", type=int, default=81890)
    ap.add_argument("--arrival-model", choices=("freeflow", "observed"),
                    default="freeflow")
    ap.add_argument("--reference-source", choices=("tripinfo", "fcd", "flows"),
                    default="tripinfo",
                    help="how insertion position/speed is read from the reference "
                         "run (tripinfo works for the full 1000 s horizon)")
    ap.add_argument("--limit", type=int, default=0,
                    help="keep only the N earliest requests (0 = all)")
    args = ap.parse_args(argv)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    edges, junctions, connections = load_network(args.net)
    routes, vehicles = parse_routes(args.rou)
    vt = parse_vtype(args.typ)

    paths = json.loads((Path(args.instance_dir) / "paths.json").read_text())["paths"]
    lane_mode = json.loads(
        (Path(args.instance_dir) / "paths.json").read_text()).get("lane_mode")
    # ``per-lane`` instances have one path per internal lane, so the movement
    # alone is ambiguous; ``movement`` instances keep the (from, to) key.
    paths_by_key = {}
    for p in paths:
        key = ((p["from_edge"], p["to_edge"], p["fromLane"])
               if lane_mode == "per-lane" else (p["from_edge"], p["to_edge"]))
        paths_by_key[key] = p
    paths_by_pair = {}
    if lane_mode == "per-lane":
        groups = {}
        for p in paths:
            groups.setdefault((p["from_edge"], p["to_edge"]), []).append(p)
        for k, v in groups.items():
            paths_by_pair[k] = v[len(v) // 2]      # fallback: median lane
    else:
        paths_by_pair = paths_by_key
    if args.reference_source == "flows":
        # demand taken from the flow definitions, independent of what SUMO could
        # insert (see flow_departures())
        departures, vehroute_routes = flow_departures(
            args.rou, routes, paths, vt, seed_offset=args.seed)
        cmd, artifact, log = ["flow_resample"], None, None
    else:
        cmd, artifact, vehroute, log = run_reference_sumo(
            args.net, args.rou, args.typ, args.begin, args.end, args.step,
            args.seed, out, source=args.reference_source)
        departures = (first_observations(artifact)
                      if args.reference_source == "fcd"
                      else tripinfo_departures(artifact))
        vehroute_routes = parse_vehroute(vehroute)
    requests, rejected = build_requests(
        edges, departures, routes, vehicles, vehroute_routes, vt,
        paths_by_pair, args.arrival_model, args.limit,
        paths_by_key=paths_by_key)

    payload = {}
    for i, r in enumerate(requests):
        payload[str(i)] = {"id": i, "importance": 1,
                           "trajectory": r["trajectory"],
                           "lane": r["lane"],
                           "arrivalTime": r["arrival_freeflow"]}
    (out / "vehicleArrival.json").write_text(json.dumps(payload, indent=1))

    manifest = {
        "net": str(args.net), "rou": str(args.rou), "typ": str(args.typ),
        "net_sha256": sha256(args.net), "rou_sha256": sha256(args.rou),
        "typ_sha256": sha256(args.typ),
        "reference_sumo_command": cmd,
        "reference_sumo_log": str(log),
        "reference_source": args.reference_source,
        "demand_source": ("flow_resample" if args.reference_source == "flows"
                          else args.reference_source),
        "reference_artifact": str(artifact) if artifact else None,
        "reference_artifact_sha256": sha256(artifact) if artifact else None,
        "rou_sha256_used": sha256(args.rou),
        "seed": args.seed, "step_length_s": args.step,
        "window_s": [args.begin, args.end],
        "arrival_model": args.arrival_model,
        "arrival_field_used": "arrival_freeflow",
        "vtype": vt,
        "psl_hardcoded": {"v_min": 3, "v_max": 15, "length": 5,
                          "note": "Instance.cpp loadVehicles(); not configurable"},
        "n_requests": len(requests),
        "n_rejected": len(rejected),
        "requests": requests,
        "rejected": rejected[:50],
    }
    (out / "request_manifest.json").write_text(json.dumps(manifest, indent=1))
    print(json.dumps({"n_requests": len(requests), "n_rejected": len(rejected),
                      "first": requests[0] if requests else None}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

