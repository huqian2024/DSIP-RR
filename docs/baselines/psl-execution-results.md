# PSL 的 SUMO 执行结果（E1 层，2026-11-14）

- 状态：**E1 已实现并跑通；结论是"计划表不可按停走方式执行"**
- 代码：`baselines/psl_sumo/execute_plan.py`
- 产物：`results/psl_exec/`（6 个 run，git-ignored，可完全再生）
- 上游计划：`results/psl_matrix/runs/psl-cross3-d{1,3,5}-s81890/schedule.csv`
- 工况：cross3，seed 81890，1000 s，0.1 s，`types.typ.xml`

---

## 1. 统计口径：严格照 `main.tex` §III-B

| 论文指标 | 实现 |
|---|---|
| **Average TimeLoss**（"following SUMO's standard definition … 在每个 logging step 对当时在途车辆取均值"） | 每 10 s 采样一次在途车队的 `vehicle.getTimeLoss` 均值（`time_loss.series_mean`）；另出 tripinfo 逐车均值（`per_vehicle_mean`） |
| **Average Speed**（"mean instantaneous speed of all vehicles currently active"） | 同样每 10 s 采样 `getSpeed` 均值；另出 `routeLength/duration` |
| **Critical proximity events**（"inter-vehicle gaps below the 1.5 m safety threshold"） | SUMO `--collision.mingap-factor 0.5`，即 `minGap 3.0 m × 0.5 = 1.5 m` 时由 SUMO 自己记录（避免每步轮询 200 万次 leader 查询） |
| **Abrupt deceleration**（"deceleration exceeding SUMO's emergency braking threshold"） | 解析 SUMO 的 `performs emergency braking` 警告（阈值 = vType `decel` = 4.5 m/s²） |
| 采样间隔 | 10 s（与 Figs. 2–4 / as2–as4 一致） |

## 2. 执行机制

- 每辆被协调的车辆在**进口停止线前 3 m** 用 `setStop` 拦住，到其计划时刻用 `resume` 放行。
- `resume` **必须门控**：只有车辆真正到达停位（`lanePos ≥ stop − 1.5 m`）才调用，
  否则 SUMO 每步报 `Failed to resume … reached: 0`（与 FCFS 审计的 D-03 同源缺陷）。
- 计划的停止线穿越时刻由 `in_time − offsets[0] / speed` 反算
  （`in_time` 是轨迹首点即首个冲突点的到达时刻，`offsets[0]` 是该点距停止线的弧长）。
- 右转不参与协调（无内部冲突点），不被拦停。

## 3. 【核心发现】计划表不可按停走方式执行

| run | 计划车辆 | 实际放行 | 车辆进入偏差 mean / p50 / p95 |
|---|---|---|---|
| cross3 d1 | 2378 | 1360 | **142.6 / 37.6 / 383.0 s** |
| cross3 d3 | 3759 | 1950 | **62.8 / 36.5 / — s** |
| cross3 d5 | 5570 | 1913 | **73.7 / 38.3 / — s** |

偏差由两部分构成（`entry_events.csv` 逐车可查）：

1. **放行即晚**：车辆在停止线排队，前车未走就无法到达自己的停位（p50 ≈ 37 s）；
2. **离站加速**：从静止起步跨过停止线并到达首个冲突点需 **2.6–2.7 s**，
   而计划假设 **0.63 s**（13.9 m/s 巡航）。

⇒ `plan_scenario.py` 的占用模型假设**以巡航速度通过**，而 `setStop`/`resume` 的执行必然
**从静止起步**。两者相差一个加速度过程，这个差额无法靠调参消除，只能靠**速度曲线控制**
（即 DSIP 那类轨迹级执行）实现。

## 4. 交通侧指标（cross3，seed 81890，1000 s）

| run | 插入 | 完成 | TimeLoss 序列均 / 逐车均 (s) | 平均速度 序列 / 逐车 (m/s) | 近距事件 (<1.5 m) | 急减速事件 |
|---|---|---|---|---|---|---|
| d1 **none**（无控制） | 2702 | 2644 | 6.83 / 10.22 | 7.32 / 7.57 | **100** | 222 |
| d1 **psl** | 1824 | 1759 | 49.76 / 17.36 | 5.08 / 7.34 | 67 | 140 |
| d3 **none** | 2700 | 2640 | 6.79 / 10.15 | 7.36 / 7.57 | **106** | 220 |
| d3 **psl** | 2610 | 2542 | 7.36 / 10.76 | 7.11 / 7.36 | 83 | 225 |
| d5 **none** | 2728 | 2664 | 6.85 / 10.24 | 7.34 / 7.57 | **127** | 254 |
| d5 **psl** | 2565 | 2497 | 7.89 / 11.55 | 6.93 / 7.36 | 103 | 191 |

### 4.1 只能这样读

- **无控制基线（`none`）不是合格基线**：它之所以 TimeLoss 低，是因为**碰撞被允许**
  （100–127 次 <1.5 m 近距事件、220–254 次急减速）。它只能作为"不控制有多危险"的对照。
- **PSL 执行确实减少了近距事件**（100→67、106→83、127→103），代价是完成车辆数下降、
  逐车 TimeLoss 上升（10.2→17.4 s @ d1）。
- **d1 的序列 TimeLoss 49.8 s 明显高于 d3/d5**：因为 MinD 下网络还有余量容纳计划给出的
  长延误，于是真的排起了队；而 d3/d5 的进口一开始就插不进去（需求 3.75/5.57 veh/s 远超容量），
  被协调的车辆反而更少、排队形态不同。**这条非单调性必须和"不可执行"这个结论一起读**，
  不能简单说"密度越高越差"。

## 5. 结论：这对论文意味着什么

1. **不能把 PSL 的计划表当成可执行的交通方案**。在 86 m 进口、`setStop`/`resume` 执行下，
   进入偏差 63–143 s，计划本身失效。
2. **因此 PSL 只能作为"计划侧"基线**（`docs/baselines/psl-matrix-results.md` 的完成率/延误表），
   或者必须补一层**速度曲线执行器**才能进入交通侧对比。
3. 这同时**正面回应了 R2-3**（物理可行性）：计划侧"零冲突"不等于可执行；
   本文自己的 DSIP 之所以能做到低延误，靠的正是轨迹级（位置/速度）控制而非仅给时刻表。
4. E1 的数字**目前只覆盖 1 个路网 × 3 个密度 × 1 个种子**，属 pilot，**不可进论文**；
   若要进，需先解决第 2 点（速度曲线执行器），再按矩阵铺开。

## 6. 【修订】加入车道资源后重做：d1/d3/d5（cross3，seed 81890）

### 6.1 为什么必须加车道资源

第一版 E1 的进入偏差 63–143 s。定位到根因：`net_to_graph.py --trim-ends` 为了解除上游
"整进口塌缩成一个入口点"的容量上限，把**停止线顶点删掉了**；于是冲突点模型里**没有
"同一车道只能有一辆车同时通过停止线"**这条约束。计划因此会安排同车道两车几乎同时到达，
物理上不可能，执行时必然排队。

修法（`plan_scenario.py`）：给守卫加一个**车道资源** `("lane", (from_edge, lane))`，
占用窗 = 车辆清空停止线所需时间（车长 5 + minGap 3 = 8 m）。

### 6.2 加车道资源后的计划侧（`--speed-mode limit`，w=13.9）

| 密度 | 完成率 | 平均进入延误 | 达成速率 |
|---|---|---|---|
| d1 | 0.650 | 164.4 s | 1.50 veh/s |
| d3 | 0.420 | 269.3 s | 1.49 veh/s |
| d5 | 0.301 | 308.5 s | 1.53 veh/s |

（对比：不加车道资源的矩阵结果是 0.875 / 0.586 / 0.419、速率 2.02/1.99/1.96。
**那批数字偏乐观**，因为它允许同车道并行；以 6.2 表为准。）

### 6.3 执行侧（`--control psl`，`--speed-model constant`）

| 密度 | 计划车 | 实际放行 | 进入偏差 mean / p50 | TimeLoss 序列/逐车 (s) | 均速 序列/逐车 (m/s) | 近距 <1.5 m | 急减速 |
|---|---|---|---|---|---|---|---|
| d1 | 2378 | 1339 | 81.5 / 25.1 s | 24.26 / 16.79 | 5.48 / 6.96 | 51 | 115 |
| d3 | 3759 | 1470 | 33.6 / 23.3 s | 10.38 / 14.88 | 6.17 / — | 61 | 115 |
| d5 | 5570 | 1460 | 48.2 / 25.4 s | 10.42 / 14.87 | 6.22 / — | 56 | 104 |

**无控制对照（同种子、同需求）**：TimeLoss 逐车 10.15–10.24 s、均速 7.3–7.6 m/s、
但近距事件 **100–127**、急减速 **220–254**。

### 6.4 可以写进论文的结论

1. **PSL（计划 + 停走执行）比无控制更安全**：近距事件 100–127 → **51–61**；
   急减速 220–254 → **104–115**。
2. **代价是效率**：逐车 TimeLoss 10.2 → **14.9–16.8 s**，平均速度 7.3 → **5.5–6.2 m/s**。
3. **计划表仍未被完全兑现**：p50 进入偏差约 23–25 s（mean 33–82 s），
   放行率仅 1339/2378、1470/3759、1460/5570。原因是占用模型假设**巡航通过**，
   而 `setStop`/`resume` 必然**静止起步**（跨停止线 2.6 s vs 计划 0.63 s）。
4. ⇒ 这仍**不是**一个可以宣称"PSL 已复现为交通侧基线"的结果；它是
   "**PSL 时刻表 + 停走执行**"的实测，且必须带着偏差分布一起报。

### 6.5 状态：今天能交付什么

| 层级 | 有无 | 位置 |
|---|---|---|
| 计划侧矩阵（3×5×30，含车道约束前） | **有**，但**偏乐观**（缺车道约束） | `docs/baselines/psl-matrix-results.md` |
| 计划侧（含车道约束，3 密度 × 1 种子） | **有** | `results/psl_exec2/plan-cross3-d{1,3,5}` |
| 交通侧（4 项论文指标，3 密度 × 1 种子） | **有**，附偏差分布 | `results/psl_exec2/exec-cross3-d{1,3,5}-psl` |
| 交通侧全矩阵（3×5×30） | **无** | 需先解决 §6.4-3 |

**下一步的最小任务**：把车道清空时间也改用**加速剖面**（`tau(8) ≈ 4 s` 而不是 `8/13.9 = 0.58 s`），
使计划与执行在同一个动力学假设下；预期把 p50 偏差压到几秒级。之后才谈铺开 450 组。


```bash
# 计划侧（已有）
python3 baselines/psl_sumo/plan_scenario.py \
  --instance-dir results/psl_matrix/instances/cross3_trim \
  --demand-dir   results/psl_matrix/demand/cross3_d1_s81890 \
  --run-dir      results/psl_matrix/runs/psl-cross3-d1-s81890 --packer psl --w 13.9

# 执行侧
python3 baselines/psl_sumo/execute_plan.py \
  --net scenarios/original/cross3.net.xml \
  --rou scenarios/flows/lanes3_density1.rou.xml \
  --typ scenarios/original/types.typ.xml \
  --instance-dir results/psl_matrix/instances/cross3_trim \
  --schedule results/psl_matrix/runs/psl-cross3-d1-s81890/schedule.csv \
  --out-dir results/psl_exec/cross3-d1-s81890-psl \
  --seed 81890 --end 1000 --control psl
```

产物：`metrics.json`（论文四项指标 + 偏差分位）、`timeseries.csv`（10 s 采样，直接对应
Figs. 2–4 / as2–as4 的横轴）、`entry_events.csv`（逐车计划/放行/实际进入）、
`collisions.csv`、`tripinfo.xml`、`sumo.log`、`run_manifest.json`（含 net/rou/typ/schedule 的 sha256）。
