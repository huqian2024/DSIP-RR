#!/usr/bin/env python3
"""S3 -- run one SUMO scenario under DSIP (MMD-xECBS) control.

Stage gate: stops here for author review.

    python3 src/dsip_reconstruction/s3_run.py \
        --net scenarios/original/cross3.net.xml \
        --rou scenarios/flows/lanes3_density3.rou.xml \
        --junction J0 --end 200 --epoch 2.0 --max-agents 6 \
        --out results/dsip_s3
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.dsip_reconstruction import upstream_env          # noqa: E402

upstream_env.ensure()

from src.dsip_reconstruction import sumo_runner           # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--net", default="scenarios/original/cross3.net.xml")
    ap.add_argument("--rou", default="scenarios/flows/lanes3_density3.rou.xml")
    ap.add_argument("--typ", default="scenarios/original/types.typ.xml")
    ap.add_argument("--junction", default="auto")
    ap.add_argument("--out", default="results/dsip_s3")
    ap.add_argument("--seed", type=int, default=81890)
    ap.add_argument("--end", type=float, default=200.0)
    ap.add_argument("--epoch", type=float, default=2.0)
    ap.add_argument("--commit-window", type=float, default=0.0)
    ap.add_argument("--max-agents", type=int, default=6)
    ap.add_argument("--replan-active", action="store_true",
                    help="include vehicles that are already executing a plan in"
                         " every batch, so cross-epoch interactions are"
                         " coordinated instead of being fixed at commit time")
    ap.add_argument("--time-scale", type=float, default=1.0,
                    help="global time dilation of every committed plan:"
                         " arc profile is replayed at t/lambda, which divides the"
                         " commanded acceleration by lambda^2 while preserving"
                         " the relative order of all vehicles")
    ap.add_argument("--road-speed", type=float, default=13.9,
                    help="m/s used to scale the planning box: one frame unit is"
                         " 0.5 * road_speed * 5 s (the prior's fixed horizon)")
    ap.add_argument("--budget", type=float, default=0.4)
    ap.add_argument("--cbs-timeout", type=float, default=20.0)
    ap.add_argument("--max-wall", type=float, default=0.0,
                    help="stop after this much wall-clock seconds (0 = no cap)")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--no-compile", dest="torch_compile", action="store_false")
    ap.add_argument("--planner-cache", dest="planner_cache", action="store_true")
    ap.set_defaults(torch_compile=True, planner_cache=False)
    args = ap.parse_args(argv)

    for name in ("net", "rou", "typ"):
        p = Path(getattr(args, name))
        setattr(args, name, p if p.is_absolute() else ROOT / p)

    if args.junction == "auto":
        args.junction = pick_junction(args.net)
    print("junction:", args.junction)

    record = sumo_runner.run(args)
    print(json.dumps({k: record[k] for k in
                      ["sim_time_reached_s", "n_calls", "n_solved",
                       "n_over_budget", "n_planned_vehicles",
                       "n_released_vehicles", "wall_p50_s", "wall_max_s",
                       "real_time_factor"]}, indent=2))
    return 0


def pick_junction(net_path):
    """Pick the junction with the most incident edges (the conflict area)."""
    import xml.etree.ElementTree as ET
    root = ET.parse(str(net_path)).getroot()
    score = {}
    for edge in root.findall("edge"):
        if edge.get("function") == "internal":
            continue
        for field in ("from", "to"):
            jid = edge.get(field)
            if jid:
                score[jid] = score.get(jid, 0) + 1
    if not score:
        return "J0"
    return max(score, key=score.get)


if __name__ == "__main__":
    sys.exit(main())
