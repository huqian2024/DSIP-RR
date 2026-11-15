#!/usr/bin/env python3
"""Compare DSIP (MMD-xECBS) against the uncontrolled junction, per scenario.

Both arms use the same net / rou / typ / seed / duration; the uncontrolled arm is
plain SUMO, the DSIP arm runs ``s3_run.py``.  The purpose is the *relative* effect
of a demand change (e.g. turning ratio), which is what the author asked for -- not
absolute parity with the historical numbers.

    python3 src/dsip_reconstruction/run_compare.py \
        --rous scenarios/flows/lanes3_density3.rou.xml,lanes3_density3_r111.rou.xml,... \
        --end 200 --epoch 2 --max-agents 4 --seed 81890 --out results/dsip_compare
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.dsip_reconstruction import upstream_env          # noqa: E402

upstream_env.ensure()

from src.dsip_reconstruction.sumo_runner import traffic_metrics  # noqa: E402

FIELDS = ["scenario", "arm", "seed", "end_s", "n_trips", "n_inserted",
          "time_loss_per_vehicle_mean_s", "duration_mean_s",
          "speed_from_route_mean_mps", "proximity_events_lt1p5m",
          "emergency_braking_events", "n_calls", "n_solved",
          "n_over_budget", "n_planned_vehicles", "n_released_vehicles",
          "wall_p50_s", "wall_max_s", "total_planning_wall_s"]


def run_uncontrolled(net, rou, typ, seed, end, out):
    out.mkdir(parents=True, exist_ok=True)
    cmd = ["sumo", "-n", str(net), "-r", str(rou), "-a", str(typ),
           "--begin", "0", "--end", str(end), "--step-length", "0.1",
           "--seed", str(seed), "--no-step-log", "true",
           "--collision.action", "warn", "--collision.mingap-factor", "0.5",
           "--tripinfo-output", str(out / "tripinfo.xml"),
           "--log", str(out / "sumo.log")]
    (out / "sumo_command.txt").write_text(" ".join(cmd) + "\n")
    subprocess.run(cmd, check=False, capture_output=True, text=True)
    return traffic_metrics(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--net", default="scenarios/original/cross3.net.xml")
    ap.add_argument("--typ", default="scenarios/original/types.typ.xml")
    ap.add_argument("--rous", required=True,
                    help="comma-separated flow files (relative to scenarios/flows)")
    ap.add_argument("--seed", type=int, default=81890)
    ap.add_argument("--end", type=float, default=200.0)
    ap.add_argument("--epoch", type=float, default=2.0)
    ap.add_argument("--max-agents", type=int, default=4)
    ap.add_argument("--budget", type=float, default=0.4)
    ap.add_argument("--out", default="results/dsip_compare")
    ap.add_argument("--no-compile", dest="torch_compile", action="store_false")
    ap.add_argument("--arms", default="none,dsip")
    ap.set_defaults(torch_compile=True)
    args = ap.parse_args(argv)

    out_root = Path(args.out)
    out_root = out_root if out_root.is_absolute() else ROOT / out_root
    out_root.mkdir(parents=True, exist_ok=True)
    net = Path(args.net)
    net = net if net.is_absolute() else ROOT / net
    typ = Path(args.typ)
    typ = typ if typ.is_absolute() else ROOT / typ
    arms = [a.strip() for a in args.arms.split(",") if a.strip()]

    rows = []
    for name in [r.strip() for r in args.rous.split(",") if r.strip()]:
        rou = Path(name)
        if not rou.is_absolute():
            rou = (ROOT / "scenarios" / "flows" / name
                   if not name.startswith("scenarios") else ROOT / name)
        scenario = rou.stem
        print("== %s" % scenario, flush=True)
        for arm in arms:
            out = out_root / ("%s-%s-s%d" % (scenario, arm, args.seed))
            if arm == "none":
                m = run_uncontrolled(net, rou, typ, args.seed, args.end, out)
                row = {"scenario": scenario, "arm": arm, "seed": args.seed,
                       "end_s": args.end}
                row.update(m)
            else:
                t0 = time.time()
                cmd = [sys.executable, str(ROOT / "src/dsip_reconstruction/s3_run.py"),
                       "--net", str(net), "--rou", str(rou), "--typ", str(typ),
                       "--out", str(out), "--seed", str(args.seed),
                       "--end", str(args.end), "--epoch", str(args.epoch),
                       "--max-agents", str(args.max_agents),
                       "--budget", str(args.budget)]
                if not args.torch_compile:
                    cmd.append("--no-compile")
                subprocess.run(cmd, check=False, capture_output=True, text=True)
                rep = json.loads((out / "s3_report.json").read_text())
                row = {"scenario": scenario, "arm": arm, "seed": args.seed,
                       "end_s": args.end}
                row.update({k: rep.get(k) for k in FIELDS if k in rep})
                row["_wall"] = round(time.time() - t0, 1)
            rows.append(row)
            print("   %-4s TL/veh=%s near=%s trips=%s calls=%s p50=%s" % (
                arm, row.get("time_loss_per_vehicle_mean_s"),
                row.get("proximity_events_lt1p5m"), row.get("n_trips"),
                row.get("n_calls"), row.get("wall_p50_s")), flush=True)

    with open(out_root / "compare.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    (out_root / "compare.json").write_text(json.dumps(rows, indent=2))
    print("\nwrote %s" % (out_root / "compare.csv"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
