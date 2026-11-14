# `baselines/psl_sumo` — PSL（PBS + SIPP + LP）SUMO 适配层

状态：**Stage 3 通过（规划侧）**。证据见 `docs/baselines/psl-stage1-runlog.md`。

上游：`https://github.com/theanhhoang/AIM.git`，分支 `AAI22_PBS-SIPP`，
commit `5686e15092fd95a46309a118655a5ab0c23c60fa`，本地只读 checkout
`third_party/_local/AIM-PSL/`（**pristine，不可修改**）。

## 做什么 / 不做什么

**做**：把 DSIP-RR 的 SUMO 路网 + 需求转成上游能吃的两个 JSON，调用上游
**预编译** `AIMPBS` 得到车辆进入/离开时刻表，并独立校验该时刻表的冲突可行性。

**不做**：不修改上游源码；不重新实现 PBS/SIPP/LP；不把计划回灌 SUMO（尚未实现，
见 §"未完成"）；不产生任何交通侧指标。

## 四个模块

| 文件 | 输入 | 输出 |
|---|---|---|
| `net_to_graph.py` | `*.net.xml` | `graph.json`、`pairDistance.json`、`paths.json`、`instance_report.json` |
| `demand.py` | `*.net.xml` + `*.rou.xml` + `*.typ.xml` | `vehicleArrival.json`、`request_manifest.json`、`tripinfo.xml`/`fcd.xml`、`vehroute.xml` |
| `run_psl.py` | 上面两个目录 + `AIMPBS` | `plan.csv`、`output.txt`、`model.lp`、`solution`、`run_manifest.json` |
| `validate_plan.py` | `plan.csv` + `graph.json` + `paths.json` | `validation.json` |

## 全时程实验适配（新增，Stage 3b/4）

| 文件 | 作用 |
|---|---|
| `kinematics.py` | 冲突点占用模型的**单一事实来源**（`constant` / `accelerating`），规划器与校验器共用 |
| `plan_scenario.py` | 全 1000 s 需求的**移动时间框顺序批规划** + 冲突点预约守卫；产出 `schedule.csv`/`summary.json` |
| `group_utilisation.py` | 诊断：各冲突组的占用率，用来判断"延误是模型容量还是求解器问题" |
| `run_matrix.py` | **全量矩阵驱动器**：3 路网 × 5 密度 × 30 seeds = 450 run，断点续跑、可并行 |

```bash
# 1) 图模型（--trim-ends：只保留真实交叉点，见下）
python3 baselines/psl_sumo/net_to_graph.py \
    --net scenarios/original/cross3.net.xml --trim-ends \
    --out-dir results/psl_stage3/instance_cross3_trim

# 2) 全 1000 s 需求（tripinfo 参考运行，体积小）
python3 baselines/psl_sumo/demand.py \
    --net scenarios/original/cross3.net.xml \
    --rou scenarios/flows/lanes3_density1.rou.xml \
    --typ scenarios/original/types.typ.xml \
    --instance-dir results/psl_stage3/instance_cross3_trim \
    --out-dir results/psl_stage3/demand_cross3_d1 --end 1000 --seed 81890

# 3) 全时程规划（--w 13.9 = 占用模型按道路限速标定，见报告 §8）
python3 baselines/psl_sumo/plan_scenario.py \
    --instance-dir results/psl_stage3/instance_cross3_trim \
    --demand-dir results/psl_stage3/demand_cross3_d1 \
    --run-dir results/psl_stage3/runs/psl-cross3-d1-s81890-w13.9 \
    --speed-mode limit --window-size 40 --packer psl --w 13.9

# 4) 独立校验（速度模型与 --w 必须和规划时一致）
python3 baselines/psl_sumo/validate_plan.py \
    --plan results/psl_stage3/runs/psl-cross3-d1-s81890-w13.9/plan.csv \
    --graph results/psl_stage3/instance_cross3_trim/graph.json \
    --paths results/psl_stage3/instance_cross3_trim/paths.json \
    --speed-model constant --w 13.9

# 5) 诊断
python3 baselines/psl_sumo/group_utilisation.py \
    --schedule results/psl_stage3/runs/psl-cross3-d1-s81890/schedule.csv \
    --graph results/psl_stage3/instance_cross3_trim/graph.json \
    --paths results/psl_stage3/instance_cross3_trim/paths.json
```

## 必须知道的五个事实

1. **`AIMPBS` 是上游预编译二进制**，无法本地重编译（缺 CPLEX）。manifest 里记
   `binary_provenance: upstream_prebuilt` + sha256。
2. 二进制**硬编码输入文件名**（`intro_graph_3.json` / `pairDistance_3.json` /
   `vehicleArrival.json`），所以 `run_psl.py` 为每次运行建独立目录。
3. `Instance.h` 的 `samePoint[104][104]` 是**硬预算**：顶点数 > 104 会越界。
4. 入口顶点**必须**至少有一个冲突伙伴，否则 `PBS.cpp:268`
   （`getConflictPoints(...)[0]`）会段错误。`net_to_graph.py` 通过"按进口折叠入口点"
   复现上游语义来保证这一点，并在 `check()` 里显式断言。
5. 上游硬编码 `v_max = 15 m/s`，高于 `types.typ.xml` 的 `maxSpeed = 13.9`。
   这是**已知偏离**，必须在论文中披露。

## 全量矩阵结果（450/450，已保存）

`python3 baselines/psl_sumo/run_matrix.py --out-root results/psl_matrix --jobs 8`
→ 3 路网 × 5 密度 × 30 seeds，3,443 s，全部 `ok`、全部独立校验、**0 冲突违规**、
17.05 亿对冲突顶点。完成率（30 seeds 均值）：

| 车道 | MinD | LowD | MedD | HigD | MaxD |
|---|---|---|---|---|---|
| 2 | 0.913 | 0.742 | 0.587 | 0.478 | 0.392 |
| 3 | 0.861 | 0.717 | 0.586 | 0.494 | 0.419 |
| 4 | 0.647 | 0.542 | 0.449 | 0.382 | 0.327 |

达成速率恒定在 1.45 / 1.99 / 1.8 veh/s（与密度无关）⇒ 容量上限。
详见 `docs/baselines/psl-matrix-results.md`。

## 仍未完成

1. **C 方案已落盘**（饱和点作为结论）：MinD 时程内完成率 **73.7–78.8 %**（cross3 三种子，均值 76.2 %），
   平均进入延误 105–127 s，达成速率 ~1.53 veh/s vs 需求 2.03。6 个 run 全部校验通过
   （约 430 万对冲突顶点，0 违规）。
2. **上限来自上游冲突模型，不是打包**：同实例同需求，`--packer greedy`（无求解器）也到 77.4 %；
   窗口放大、per-lane 路径均无效；冲突组占用率最高 55 %。
3. **A 已完成且无需安装 CPLEX**：`--w` 只改适配层的强制执行模型（二进制仍是 7）。
   `--w 13.9`（= 场景限速，使 `Li/w+Li/v = 2Li/v`）→ MinD 完成率 **0.952–0.979**（三种子均值 0.967），
   平均进入延误 11.5–21.0 s，全部独立校验 0 违规。
4. **B 方案（区域级冲突抽象）评估为不可行**：上游 `Li` 只由车长与转向半径决定，
   与顶点几何尺度无关；把"点"换成"区"会把 27 m 冲突区按 1.07 s 计价（应为 2.3 s），
   **属安全错误，必须改 `SIPP.cpp` ⇒ 与 A 同一 CPLEX 阻塞，且偏离更大**。
   建议改 `w`（7 → ≈11 m/s）。
5. **E1 执行层**：把 `In Time` 变成 SUMO 的 `setStop`/`resume`，才可能有交通侧指标。

详见 `docs/baselines/psl-experiment-adaptation.md`。

## 不要做的事

- 不要 `python3 third_party/_local/AIM-PSL/Controller/controller.py`（~100 次 × 6 档 × 3 方法）。
- 不要为了让数字好看而放宽 `TOUCH_TOL`、改 `v_max`、去掉 `--trim-ends` 的论证、或把
  `kinematic` 模式的结果当作 PSL 的性能。
- 不要把 `schedule_only` 的规划侧结果写成吞吐 / 行程时间 / 碰撞数。
- 不要把本目录的输出与历史 DSIP 结果放进同一张统计图（`AGENTS.md` §6.3）。
