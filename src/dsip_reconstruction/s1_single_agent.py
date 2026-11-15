#!/usr/bin/env python3
"""S1 -- single-vehicle inference with the fixed prior.

Loads ``EnvEmptyNoWait2D-RobotPlanarDisk`` through upstream ``MPD`` (see
``prior.py`` for the dataset shim), plans one start/goal pair in the normalised
planning frame, and records: loading time, dimensions, denoising configuration,
GPU, per-call wall time, endpoint error and the sampled trajectories.

No simulation, no SUMO: this stage only proves the prior runs and states what it
produces.  Stage gate: stops here for author review.

    python3 src/dsip_reconstruction/s1_single_agent.py --out results/dsip_s1
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


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="results/dsip_s1")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--start", default="-0.8,0.0",
                    help="start position in the planning frame (data units)")
    ap.add_argument("--goal", default="0.8,0.0")
    ap.add_argument("--no-compile", action="store_true",
                    help="disable torch.compile (upstream default is enabled)")
    args = ap.parse_args(argv)

    out = Path(args.out)
    out = out if out.is_absolute() else ROOT / out
    out.mkdir(parents=True, exist_ok=True)

    resolved = upstream_env.assert_inside()
    tensor_args = {"device": torch.device(args.device), "dtype": torch.float32}
    start = torch.tensor([float(x) for x in args.start.split(",")], **tensor_args)
    goal = torch.tensor([float(x) for x in args.goal.split(",")], **tensor_args)

    t0 = time.time()
    planner = prior.build_mpd(start, goal, device=args.device, seed=args.seed,
                              torch_compile=not args.no_compile)
    load_s = time.time() - t0

    t1 = time.time()
    output = planner(start, goal)
    infer_s = time.time() - t1

    trajs = output.trajs_final                       # (B, H, 4) data units
    best = trajs[output.idx_best_traj] if output.idx_best_traj is not None else None
    pos = trajs[..., :2]

    start_err = float(torch.linalg.norm(pos[:, 0] - start, dim=-1).mean())
    goal_err = float(torch.linalg.norm(pos[:, -1] - goal, dim=-1).mean())
    inside = float(((pos.abs() <= 1.0).all(dim=-1).float().mean()))

    record = {
        "stage": "S1",
        "model_id": upstream_env.MODEL_ID,
        "dataset_source": "shim",
        "upstream_modules": resolved,
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
        "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
        "torch_compile": not args.no_compile,
        "seed": args.seed,
        "n_support_points": int(planner.n_support_points),
        "n_samples": int(planner.num_samples),
        "n_diffusion_steps": int(planner.model.n_diffusion_steps),
        "n_local_inference_noising_steps": int(planner.n_local_inference_noising_steps),
        "n_local_inference_denoising_steps": int(planner.n_local_inference_denoising_steps),
        "n_guide_steps": int(planner.n_guide_steps),
        "t_start_guide": int(planner.t_start_guide),
        "start": start.tolist(),
        "goal": goal.tolist(),
        "load_time_s": round(load_s, 3),
        "inference_time_s": round(infer_s, 3),
        "t_total_reported_s": round(float(output.t_total), 4),
        "n_free_trajs": int(output.trajs_final_free.shape[0])
        if output.trajs_final_free is not None else 0,
        "n_trajs": int(trajs.shape[0]),
        "idx_best_traj": int(output.idx_best_traj)
        if output.idx_best_traj is not None else None,
        "mean_start_error": round(start_err, 6),
        "mean_goal_error": round(goal_err, 6),
        "fraction_inside_box": round(inside, 4),
    }
    (out / "s1_report.json").write_text(json.dumps(record, indent=2))
    torch.save({"trajs": trajs.cpu(),
                "best": None if best is None else best.cpu()},
               out / "s1_trajs.pt")

    # A quick plot so the shapes can be eyeballed (no data is invented).
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(4, 4))
    for i in range(min(trajs.shape[0], 8)):
        ax.plot(pos[i, :, 0].cpu(), pos[i, :, 1].cpu(), lw=0.8, alpha=0.6)
    if best is not None:
        ax.plot(best[:, 0].cpu(), best[:, 1].cpu(), "k-", lw=1.6, label="best")
    ax.plot(*start.cpu().tolist(), "go", ms=5, label="start")
    ax.plot(*goal.cpu().tolist(), "rx", ms=6, label="goal")
    ax.set_xlim(-1.05, 1.05)
    ax.set_ylim(-1.05, 1.05)
    ax.set_aspect("equal")
    ax.grid(alpha=0.3, lw=0.4)
    ax.legend(fontsize=7)
    ax.set_title("S1 prior samples (%d of %d)" % (min(trajs.shape[0], 8),
                                                  trajs.shape[0]), fontsize=8)
    fig.tight_layout()
    fig.savefig(out / "s1_samples.png", dpi=150)
    plt.close(fig)

    print(json.dumps({k: record[k] for k in
                      ["load_time_s", "inference_time_s", "n_trajs",
                       "n_free_trajs", "mean_start_error", "mean_goal_error",
                       "fraction_inside_box"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
