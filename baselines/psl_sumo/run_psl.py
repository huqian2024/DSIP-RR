"""Run the upstream PSL binary on one generated instance.

The upstream ``Driver.cpp`` hard-codes its file names::

    Instance instance("intro_graph_3.json");     // graph
    instance.loadVehicles("vehicleArrival.json", step);
    pbs.run("output.txt");

``Instance.cpp`` additionally hard-codes ``PDFile = "pairDistance_3.json"`` and
writes ``model.lp`` / ``solution`` into the working directory.  So every run is
executed in its **own** directory, populated with copies under those exact
names.  Nothing is written into ``third_party/``.

``step`` is a *count index*, not a count: ``loadVehicles`` loops ``i <= step``,
so ``N`` vehicles need ``step = N - 1``.

Provenance
----------
``--binary`` defaults to the upstream prebuilt ``PBS-SIPP-ver2/AIMPBS``.  It
cannot be rebuilt locally (CPLEX is not installed); the manifest records
``binary_provenance: upstream_prebuilt`` plus the binary sha256.

CPLEX
-----
The prebuilt binary links CPLEX statically and the CPLEX runtime licence check
passes on this machine for the instance sizes used here (verified, see
``docs/baselines/psl-stage1-runlog.md``).  No licence is bypassed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BINARY = ROOT / "third_party" / "_local" / "AIM-PSL" / "PBS-SIPP-ver2" / "AIMPBS"
# hard-coded inside the binary (Driver.cpp / Instance.cpp)
GRAPH_NAME = "intro_graph_3.json"
PAIR_NAME = "pairDistance_3.json"
ARRIVAL_NAME = "vehicleArrival.json"
OUTPUT_NAME = "output.txt"

COLUMNS = ["in_point", "out_point", "length", "earliest_arrival", "in_time",
           "out_time_head", "out_time_tail", "time_spend", "speed", "importance"]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_output(path, vehicle_ids):
    """Parse ``output.txt`` into one dict per vehicle, in file order."""
    rows = []
    with open(path) as fh:
        header = fh.readline().strip()
        reader = csv.reader(fh, delimiter=";")
        for i, rec in enumerate(reader):
            if not rec or len(rec) < len(COLUMNS):
                continue
            rec = [c.strip() for c in rec]
            row = dict(zip(COLUMNS, rec))
            for k in COLUMNS[2:9]:
                row[k] = float(row[k])
            row["row_index"] = i
            # upstream writes plan[] in agent order = order of the JSON keys
            row["load_index"] = i
            row["vehicle_id"] = vehicle_ids[i] if i < len(vehicle_ids) else None
            rows.append(row)
    return {"header": header, "rows": rows}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Run PSL on one generated instance.")
    ap.add_argument("--instance-dir", required=True,
                    help="directory holding graph.json + pairDistance.json")
    ap.add_argument("--demand-dir", required=True,
                    help="directory holding vehicleArrival.json")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--binary", default=str(DEFAULT_BINARY))
    ap.add_argument("--timeout", type=float, default=900.0)
    args = ap.parse_args(argv)

    binary, inst, dem, run = (Path(args.binary), Path(args.instance_dir),
                              Path(args.demand_dir), Path(args.run_dir))
    if not binary.exists():
        raise SystemExit("PSL binary not found: %s" % binary)
    for p in (inst / "graph.json", inst / "pairDistance.json",
              dem / "vehicleArrival.json"):
        if not p.exists():
            raise SystemExit("missing input: %s" % p)

    run.mkdir(parents=True, exist_ok=True)
    # The binary is executed by absolute path with ``cwd=run`` so that its
    # cwd-relative hard-coded file names resolve here, while the 41.7 MB
    # upstream artefact is never copied into a results directory.
    shutil.copy2(inst / "graph.json", run / GRAPH_NAME)
    shutil.copy2(inst / "pairDistance.json", run / PAIR_NAME)
    shutil.copy2(dem / ARRIVAL_NAME, run / ARRIVAL_NAME)
    for extra in (inst / "paths.json", dem / "request_manifest.json"):
        if extra.exists():
            shutil.copy2(extra, run / extra.name)

    arrivals = json.loads((run / ARRIVAL_NAME).read_text())
    n_vehicles = len(arrivals)
    if n_vehicles < 1:
        raise SystemExit("vehicleArrival.json is empty")
    step = n_vehicles - 1

    cmd = [str(binary.resolve()), str(step)]
    t0 = time.perf_counter()
    timed_out = False
    try:
        proc = subprocess.run(cmd, cwd=str(run), capture_output=True, text=True,
                              timeout=args.timeout)
        stdout, stderr, rc = proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired as exc:
        def _txt(v):
            return v.decode() if isinstance(v, bytes) else (v or "")
        stdout, stderr, rc, timed_out = _txt(exc.stdout), _txt(exc.stderr), -1, True
    wall = time.perf_counter() - t0

    (run / "stdout.log").write_text(stdout)
    (run / "stderr.log").write_text(stderr)

    reported = None
    for line in stdout.strip().splitlines():
        try:
            reported = float(line.strip())
        except ValueError:
            continue

    out_path = run / OUTPUT_NAME
    plan = {"header": None, "rows": []}
    if out_path.exists():
        vehicle_ids = [arrivals[k]["id"] for k in
                       sorted(arrivals, key=lambda s: int(s))]
        plan = parse_output(out_path, vehicle_ids)
        with open(run / "plan.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=COLUMNS + ["row_index",
                                                        "load_index", "vehicle_id"])
            w.writeheader()
            for row in plan["rows"]:
                w.writerow(row)

    solution_status = None
    sol = run / "solution"
    if sol.exists():
        for line in sol.read_text(errors="replace").splitlines():
            if "solutionStatusString" in line:
                solution_status = line.split("=")[-1].strip().strip('">/ ')

    manifest = {
        "method": "psl",
        "binary_provenance": "upstream_prebuilt",
        "binary_path": str(binary),
        "binary_sha256": sha256(binary),
        "upstream_repo": "https://github.com/theanhhoang/AIM.git",
        "upstream_branch": "AAAI22_PBS-SIPP",
        "upstream_commit": "5686e15092fd95a46309a118655a5ab0c23c60fa",
        "local_rebuild": "impossible: CPLEX not installed (ilcplex/ilocplex.h)",
        "command": cmd,
        "cwd": str(run),
        "step_argument": step,
        "n_vehicles_loaded": n_vehicles,
        "exit_code": rc,
        "timed_out": timed_out,
        "wall_time_s": round(wall, 6),
        "solver_reported_runtime_s": reported,
        "cplex_solution_status": solution_status,
        "n_plan_rows": len(plan["rows"]),
        "cplex_licence_error": ("licen" in (stderr or "").lower()),
        "inputs": {GRAPH_NAME: sha256(run / GRAPH_NAME),
                   PAIR_NAME: sha256(run / PAIR_NAME),
                   ARRIVAL_NAME: sha256(run / ARRIVAL_NAME)},
        "outputs": sorted(p.name for p in run.iterdir() if p.is_file()),
    }
    (run / "run_manifest.json").write_text(json.dumps(manifest, indent=1))
    print(json.dumps({k: manifest[k] for k in
                      ("exit_code", "timed_out", "wall_time_s",
                       "solver_reported_runtime_s", "cplex_solution_status",
                       "n_plan_rows", "cplex_licence_error")}, indent=1))
    return 0 if rc == 0 and not timed_out else 1


if __name__ == "__main__":
    raise SystemExit(main())
