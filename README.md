# DSIP-RR — Revision Repository for IEEE T-ITS Manuscript T-ITS-26-05-2776

Revision workspace for **“DSIP: A Dynamic Coordination Planner for Signal-Free Intersections Using
Diffusion-Model-Based Multi-Agent Motion Planning”** (Revise & Resubmit).

This repository holds the revision assets, the audited SUMO scenarios, the reconstructed/adapted
baselines and the experiment bookkeeping. **Agent and contributor rules live in [`AGENTS.md`](AGENTS.md)**
and the authoritative asset/status record is [`docs/HANDOFF.md`](docs/HANDOFF.md).

---

## Baseline structure under evaluation

| Layer | Method | Role in the revision |
|---|---|---|
| L1 | **DSIP** | the method under study (historical results only; original code/checkpoints unavailable) |
| L2 | **FCFS** conflict-point reservation (Dresner–Stone inspired) | traditional reservation-based AIM |
| L3 | **PSL** — Priority-Based Search + SIPP + LP | optimisation-based multi-vehicle coordination |
| L4 | **PSB** — Priority-Based Search + SIPP + Bézier kinodynamic optimisation | optimisation-based motion planning |
| Reference | **Fixed-time signal control** | conventional traffic control |
| Optional | **CCAM-DI** (RL) | not implemented in the current scope |

Design rationale, fairness protocol and open questions:

- [`docs/baselines/baseline-strategy.md`](docs/baselines/baseline-strategy.md)
- [`docs/baselines/fairness-protocol.md`](docs/baselines/fairness-protocol.md)
- [`docs/baselines/fcfs-correctness-audit.md`](docs/baselines/fcfs-correctness-audit.md)
- [`docs/baselines/psb-reproduction.md`](docs/baselines/psb-reproduction.md) /
  [`docs/baselines/psl-reproduction.md`](docs/baselines/psl-reproduction.md)
- [`docs/baselines/sumo-adaptation-design.md`](docs/baselines/sumo-adaptation-design.md)
- [`third_party/UPSTREAMS.md`](third_party/UPSTREAMS.md)

## Repository layout

```text
paper/        submitted Overleaf snapshot (immutable), review material, revision sources
scenarios/    original SUMO networks, routes, vehicle types; generated demand flows; smoke tests
baselines/    fcfs_sumo/ (conflict-point reservation), psb_sumo/, psl_sumo/ (adapters)
experiments/  launchers (e.g. run_fcfs_sweep.py) and the 30-seed list
evaluation/   shared metric and plotting code
results/      regenerable run artefacts (mostly git-ignored)
docs/         HANDOFF, audits, decisions, baselines, environment records
third_party/  upstream registration (UPSTREAMS.md); local clones are git-ignored
```

## Environment (verified 2026-11-07)

- Eclipse SUMO **1.12.0**, `traci` / `sumolib` **1.24.0**, Python 3.12
- CMake 3.22, g++ 11.4, Boost 1.74/1.82
- **IBM ILOG CPLEX is not installed**: both optimisation baselines (PSL, PSB) fail to build on
  `ilcplex/ilocplex.h`. See `third_party/UPSTREAMS.md` §3.

## Working agreements

- No fabricated results; historical (submitted) numbers are never rewritten.
- Original submission assets under `scenarios/original/` and `paper/submitted/` are read-only.
- No upstream source is redistributed (neither upstream repository ships a license file).
- Experiments are run **in stages**, one dimension at a time; mass sweeps require explicit
  authorisation. See `AGENTS.md` §2 “Staged experiment gates”.
