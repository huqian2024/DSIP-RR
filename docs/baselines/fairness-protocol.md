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

---

## 7. 对比口径决定（2026-11-15，作者裁决，**A2：交通侧为准**）

**决定**：本轮 PSL baseline 的**正式对比口径 = 交通侧**（SUMO 执行层，论文 §III-B 的四项指标），
**不是**计划侧（completion / entry delay / rate）。计划侧数字降级为**诊断量**，不得作为对比主表。

**依据**：作者在 DSIP 启动闸门复核（`docs/dsip_reconstruction/gate-review-2026-11-15.md` §5 D-A）
中明确选择 A2，理由是：只有执行层数字才与论文的 Fig. 2–7 / Table II 口径同源。

### 7.1 立刻生效的五条后果

1. **G1 判 FAIL**：交通侧目前只有 cross3 × 3 密度 × 5 seeds（pilot），
   必须扩到 **3 路网 × 5 密度 × ≥3 seeds** 才满足闸门。DSIP 重建在此之前不得启动。
2. **计划侧数字的表述**：只能写 "planning-side diagnostic (completion fraction / entry delay)"，
   且必须同时给出计划侧速率与需求速率的比值，不得单独引用。
3. **交通侧数字的表述**：一律写成 **"PSL timetable + stop-and-go execution"**，
   并**必须同表给出 `entry_deviation_p50_s`**（pilot 实测 20.7 / 23.6 / 26.5 s @ d1/d3/d5）。
   禁止表述为 "PSL 按计划执行"。
4. **三方法对比的前提**：FCFS 与 `DSIP-Reconstructed` 也必须给出**交通侧**数字，
   才能进同一张图/表。`DSIP-Reconstructed` 必须声明所用执行模式
   （`paper_faithful` 或 `dynamics_aware`，见 `AGENTS.md`），且不得与 PSL 的停走执行口径混谈。
5. **对照必须同源**：`--control none` 的无控制参考与 PSL 用**同 net / 同 rou / 同 seed**，
   `--mingap-factor 0.5`（= minGap 3.0 × 0.5 = 1.5 m），10 s 采样。

### 7.2 已知弱点（写进论文时必须披露，不得省略）

- 进入偏差 p50 达 20–30 s ⇒ 时刻表**不可精确执行**；PSL 的"协调效果"体现在
  **近距交互减半**（near-miss 106–110.8 → 48.2–54.6），而**不是**吞吐提升。
- per-vehicle TimeLoss 反而上升（10.1–10.2 → 14.4–15.0 s，+42%），必须如实报告。
- 不得据此声称 "PSL 劣于 DSIP"：两者冲突模型不同、无配对重跑。

### 7.3 扩批范围（本裁决的直接产物）

| 维度 | 范围 |
|---|---|
| 路网 | `cross2` / `cross3` / `cross4` |
| 密度 | d1–d5 |
| seeds | `81890 / 81891 / 81892`（与计划矩阵同 seed 集） |
| 控制 | `psl` 与 `none` 各一遍 ⇒ **45 + 45 = 90 run** |
| 计划来源 | 复用 `results/psl_matrix/runs/psl-*`（已 450/450，`w=13.9`），不重新求解 |
