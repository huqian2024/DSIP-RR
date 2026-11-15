#!/usr/bin/env python3
"""S2 -- multi-vehicle coordination through upstream MMD-xECBS.

Follows the upstream call order in ``scripts/inference/inference_multi_agent.py``:

1. build one ``MPD`` per agent (same prior, different start/goal),
2. ``CBS(planners, starts, goals, reference_task, reference_robot,
   is_xcbs=True, is_ecbs=True,
   conflict_type_to_constraint_types={PointConflict: {MultiPointConstraint}})``,
3. ``planner.plan(runtime_limit=...)``.

``is_xcbs=True`` makes every CT expansion feed the agent's previous path batch in
as ``PathBatchExperience``, so the low level runs the *local* inference path
(3 noising / 3 denoising steps) instead of a fresh 25-step denoising chain.
``is_ecbs=True`` adds soft constraints from the other agents' current paths.

The scenario is given as JSON::

    [{"id": "ew", "start": [-0.8, 0.0], "goal": [0.8, 0.0], "start_time": 0}, ...]

Stage gate: stops here for author review.

    python3 src/dsip_reconstruction/s2_multi_agent.py --scenario scenarios/dsip/s2_cross4.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.dsip_reconstruction import upstream_env          # noqa: E402

upstream_env.ensure()

import torch                                              # noqa: E402

from src.dsip_reconstruction import prior                 # noqa: E402


def build_planners(agents, device, seed, compile_models):
    planners = []
    for agent in agents:
        tensor_args = {"device": torch.device(device), "dtype": torch.float32}
        start = torch.tensor(agent["start"], **tensor_args)
        goal = torch.tensor(agent["goal"], **tensor_args)
        planners.append(prior.build_mpd(start, goal, device=device, seed=seed,
                                        torch_compile=compile_models))
    return planners


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--out", default="results/dsip_s2")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--runtime-limit", type=float, default=60.0)
    ap.add_argument("--no-compile", action="store_true")
    args = ap.parse_args(argv)

    out = Path(args.out)
    out = out if out.is_absolute() else ROOT / out
    out.mkdir(parents=True, exist_ok=True)
    scenario_path = Path(args.scenario)
    if not scenario_path.is_absolute():
        scenario_path = ROOT / scenario_path
    agents = json.loads(scenario_path.read_text())

    resolved = upstream_env.assert_inside()
    t0 = time.time()
    planners = build_planners(agents, args.device, args.seed,
                              not args.no_compile)
    build_s = time.time() - t0

    from mmd.common.conflicts import PointConflict
    from mmd.common.constraints import MultiPointConstraint
    from mmd.planners.multi_agent import CBS

    tensor_args = {"device": torch.device(args.device), "dtype": torch.float32}
    starts = [torch.tensor(a["start"], **tensor_args) for a in agents]
    goals = [torch.tensor(a["goal"], **tensor_args) for a in agents]
    start_times = [int(a.get("start_time", 0)) for a in agents]

    reference = planners[0]
    cbs = CBS(planners, starts, goals,
              start_time_l=start_times,
              is_xcbs=True, is_ecbs=True,
              conflict_type_to_constraint_types={PointConflict: {MultiPointConstraint}},
              reference_robot=reference.robot,
              reference_task=reference.task)

    t1 = time.time()
    paths, n_expansions, status, n_conflicts = cbs.plan(
        runtime_limit=args.runtime_limit)
    plan_s = time.time() - t1

    # Independent check: pairwise clearance in the returned solution.
    min_clear = None
    if paths:
        pos = torch.stack([p[:, :2] for p in paths])       # (n, H, 2)
        n = pos.shape[0]
        worst = float("inf")
        for i in range(n):
            for j in range(i + 1, n):
                d = torch.linalg.norm(pos[i] - pos[j], dim=-1).min()
                worst = min(worst, float(d))
        min_clear = worst
    radius = float(reference.robot.radius)

    record = {
        "stage": "S2",
        "scenario": str(scenario_path.relative_to(ROOT)),
        "n_agents": len(agents),
        "is_xcbs": True,
        "is_ecbs": True,
        "conflict_type": "PointConflict -> MultiPointConstraint",
        "n_local_inference_noising_steps": int(planners[0].n_local_inference_noising_steps),
        "n_local_inference_denoising_steps": int(planners[0].n_local_inference_denoising_steps),
        "n_diffusion_steps": int(planners[0].model.n_diffusion_steps),
        "n_samples": int(planners[0].num_samples),
        "robot_radius": radius,
        "build_time_s": round(build_s, 3),
        "planning_time_s": round(plan_s, 3),
        "ct_expansions": int(n_expansions),
        "success_status": str(status),
        "conflicts_left": int(n_conflicts),
        "min_pairwise_clearance": None if min_clear is None else round(min_clear, 5),
        "clearance_ok": (min_clear is not None and min_clear >= 2 * radius - 1e-6),
        "upstream_modules": resolved,
    }
    (out / "s2_report.json").write_text(json.dumps(record, indent=2))
    if paths:
        torch.save([p.cpu() for p in paths], out / "s2_paths.pt")

    print(json.dumps({k: record[k] for k in
                      ["n_agents", "ct_expansions", "success_status",
                       "planning_time_s", "min_pairwise_clearance",
                       "clearance_ok"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
