# 公平比较协议（FCFS / PSL / PSB / DSIP）

- 版本：**v0（2026-11-07）**，在 Stage 5 的 Pilot 之前可修订；一经开始正式实验即冻结并记录版本号。
- 适用范围：所有**新**实验。历史 DSIP 结果按 `AGENTS.md` §6 单列，不与新协议混合。

---

## 1. 输入同一化（必须逐项记录，不许"同 seed 即同输入"）

| 项 | 固定为 | 来源 / 校验 |
|---|---|---|
| 路网 | `scenarios/original/cross{2,3,4}.net.xml` | sha256 记录进 `run_manifest.json` |
| 需求 | `scenarios/flows/lanes{L}_density{D}.rou.xml` | 同上 |
| 车辆类型 | `scenarios/original/types.typ.xml` | accel 1.0 / decel 4.5 / length 5.0 / minGap 3.0 / maxSpeed 13.9 / tau 2.0 / IDM |
| 步长 | 0.1 s（命令行覆盖，**不新建 cfg**） | 与投稿口径一致 |
| 仿真时长 | 1000 s | `--end 1000` |
| 种子 | `experiments/seeds_30.txt`（81890–81919） | **同号 seed ≠ 同随机流**，故必须记录 `request_manifest` |
| 转向比 | 1:2:1（由 `routes.rou.xml` / `generate_flows.py` 决定） | 不得为某方法单独调流 |

**`request_manifest.json` 必须逐车记录实际请求**：vehID、departTime、entry lane、exit lane、
turning、initialSpeed、length、accel、decel、speedLimit。
这是"输入真的相同"的唯一证据；仅比对 seed 数字**不构成**证据。

## 2. 运动学同一化

- 四个方法必须使用**同一份** vType 参数。
- PSB 论文的运动学约束（更高加速度、更短车长）**不得**直接搬进 SUMO 场景；
  若上游硬编码了不同参数，在 `run_manifest.json` 里记 `kinematics_deviation`，
  并在论文里报告该差异——**不允许"为了公平"改 SUMO 车辆参数**。

## 3. 指标定义（统一定义、统一单位）

| # | 指标 | 定义 | 来源 |
|---|---|---|---|
| 1 | Throughput | 完成行程车辆数 / 仿真时长（veh/s） | `tripinfo` 计数 / `--end` |
| 2 | Average vehicle delay | `tripinfo.duration − tripinfo.routeLength / vType.maxSpeed` 的均值 | tripinfo |
| 3 | Average TimeLoss | `tripinfo.timeLoss` 均值（**与 #2 并列报告，不互相替代**） | tripinfo |
| 4 | Average speed | `routeLength / duration` 均值（m/s） | tripinfo |
| 5 | Travel time | `tripinfo.duration` 均值（s） | tripinfo |
| 6 | Collision count | `simulation.getCollisions()` 去重后的**事件数**（按 lane+victim+other 0.5 s 聚类） | TraCI |
| 7 | Vehicle insertion rate | 插入数 / 需求车辆数 | `getDepartedNumber` |
| 8 | Completed vehicle count | `n_arrived` | `getArrivedNumber` |
| 9 | Failed vehicle count | 需求中未插入 + 未完成 | 需求文件 vs 结果 |
| 10 | Planning runtime | 算法求解 wall time（**仅规划侧**） | 适配器计时 |
| 11 | Timeout count | 求解超时次数 | 适配器 |

**铁律**：
- 规划运行时间（#10）与 SUMO 仿真时间**必须分列**，不得相加、不得互相换算；
- 只报 TimeLoss 与速度而**不报碰撞与完成率**的报告视为不合格；
- 交叉口内部碰撞与出口汇流碰撞**分列**（D9 双轨口径）。

## 4. 实验标识与产物

```text
results/new_baselines/<method>/<experiment_id>/
├── config.json            # 方法、上游 commit、适配器版本、参数
├── request_manifest.json  # 逐车请求（§1）
├── run_manifest.json      # 见下
├── metrics.csv            # 本 run 的 §3 指标
├── stdout.log / stderr.log
├── trajectory/            # 仅当真有轨迹输出时才创建
└── summary.json
```

`experiment_id` 规范：`{method}-{net}-{flow}-s{seed}`，例如
`fcfs-cross3-lanes3_density2-s81890`。

`run_manifest.json` 必填：
`algorithm`、`upstream_commit`、`adapter_version`、`sumo_version`（1.12.0）、
`cplex_version`（如适用）、`scenario_sha256{net,rou,typ}`、`seed`、`density`、`lanes`、
`turning_ratio`、`duration_s`、`step_length_s`、`command`、`status`、
`metric_definition_version`、`kinematics_deviation`、`planning_runtime_s`。

**失败/崩溃的 run 也必须落盘**（`status: error|timeout|collision_abort`）。

## 5. 分阶段执行闸门（不得跳过）

| Stage | 内容 | 闸门 |
|---|---|---|
| 5 | 1 lane config × 1 density × 3–5 seeds | 结果合理（碰撞/完成率/求解时间）才可扩 |
| 6a | 10 seeds | 同上 |
| 6b | 30 seeds | 同上 |
| 6c | 加 density | 每次只扩一个维度 |
| 6d | 加 lane config | 最后才扩 |

**450 次（30 seeds × 5 density × 3 lanes）不在本轮自动执行范围内**，需作者单独授权。

## 6. 报告纪律

- 任何"新 baseline 已复现"的表述必须有：可执行文件来源（自编译/预编译）、
  输入 manifest、原始输出文件路径；
- 预编译二进制（PSL 的 `AIMPBS`）若被使用，必须在 `run_manifest.json` 标注
  `binary_provenance: "upstream_prebuilt"` 并说明无法本地重编译的原因；
- 历史 DSIP 数字只能以"历史投稿结果"引用，永不与新实验结果做配对统计检验。
