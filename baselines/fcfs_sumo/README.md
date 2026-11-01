# `baselines/fcfs_sumo` — FCFS baseline, SHADOW MODE

Status: **shadow mode only**. The package computes and logs FCFS admission
decisions; it never commands a vehicle. There is **no** `setSpeed`,
`slowDown`, `setStop`, `moveTo`, `moveToXY`, `changeLane`, `setLaneChangeMode`
or `setSpeedMode` call in any module (enforced by `test_logic.py`).

## Modules

| file | role |
|---|---|
| `conflicts.py` | 12 movement table + provisional conflict matrix from `cross3.net.xml`; cross-checks the matrix against `results/smoke/net_analysis.log` (Task 03); adds shared-downstream-lane (merge) and shared-upstream-lane (car-following) relations |
| `tracker.py` | per-step vehicle life cycle: `first_seen` → `enter` → `leave` / `gone`; `roadID` starting with `:` means "inside the junction" |
| `queue.py` | append-only FCFS queue; priority key `(proxy request time, vehicle id)`; frozen after insertion |
| `shadow.py` | request → BLOCKED / ELIGIBLE / UNDETERMINED → ENTERED → CLEARED decision engine, plus divergence diagnostics |
| `runner.py` | the only TraCI entry point (100 s, 1 s step, read-only getters) |
| `analyze_shadow.py` | post-hoc analysis of the produced CSVs (conflicting co-occupancy, timing, distributions) |
| `test_logic.py` | dependency-free self check (`python3 -m baselines.fcfs_sumo.test_logic`) |

## Commands

```bash
python3 -m baselines.fcfs_sumo.test_logic            # pure logic, no SUMO
python3 -m baselines.fcfs_sumo.runner                # one 100 s shadow run
python3 -m baselines.fcfs_sumo.analyze_shadow        # analyse the CSVs
```

Outputs go to `results/fcfs_shadow/` (`vehicle_events.csv`, `requests.csv`,
`decisions.csv`, `shadow_summary.json`, `shadow_run.log`, `shadow_analysis.txt`).

## Status vocabulary

* `BLOCKED` — a conflicting movement is occupied **now** (definitive).
* `ELIGIBLE` — the conflict set has not been occupied at any time since this
  vehicle was queued, so admission is safe regardless of the safety gap.
* `UNDETERMINED` — the conflict set is free now but **was** occupied after the
  request; whether the remaining separation suffices needs the safety-gap
  parameter, which has deliberately **not** been invented.
* `ENTERED` / `CLEARED` — observed (not commanded) junction entry and exit.

## Reproduction prerequisites

| item | value observed in this workspace |
|---|---|
| SUMO binary | `/usr/bin/sumo` 1.12.0 (`SUMO_HOME=/usr/share/sumo`) |
| Python | 3.12.2 (conda `base`) |
| `traci` / `sumolib` (pip) | 1.24.0 (TraCI protocol version 20, verified in Task 03) |
| `shapely` | 2.1.1 (used only by `conflicts.py` geometry) |
| other | standard library only (`csv`, `json`, `statistics`, `xml.etree`) |
| step length / horizon | 1 s / 100 s, taken from `scenarios/smoke/cross3_smoke.sumocfg` |
| randomness | fixed: the 12 flows carry `seed="82339..82350"` and no global seed is overridden, so repeated runs reproduce identical vehicle counts |

Order of operations on a fresh clone:

1. `python3 -m baselines.fcfs_sumo.test_logic` — pure logic, works without SUMO.
2. `python3 scenarios/smoke/net_analysis.py > results/smoke/net_analysis.log`
   — regenerates the Task 03 matrix that `conflicts.py` cross-checks against.
   **If this log is absent the cross-check is reported as `SKIP` / `found=False`;
   the conflict model itself still builds normally.**
3. `python3 -m baselines.fcfs_sumo.runner` then
   `python3 -m baselines.fcfs_sumo.analyze_shadow`.

All paths are derived from `Path(__file__).resolve().parents[2]`, so the
commands work from any working directory.  Nothing in `results/` is required
to exist beforehand.


## Deliberately undefined (needs author input)

Proxy request time (first observation on an approach) is **not** the
Dresner–Stone request time. Not fixed yet: control-zone / arrival (ACZ)
definition, required safety gap, reservation granularity, right-turn policy,
deadlock tie-breaking, metric definitions, safety-detection settings
(`collision.check-junctions`), and the step length (1 s here vs 0.1 s in the
manuscript). Conflict relations are **provisional**: the `center` junction is
`unregulated` and has no `<request>/foes` table, and non-intersecting lane
centrelines do not prove that two movements can run simultaneously.
