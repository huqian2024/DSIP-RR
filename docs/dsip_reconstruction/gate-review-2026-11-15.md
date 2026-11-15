# 闸门复核（启动 DSIP 重建前，2026-11-15）

- 触发：作者 2026-11-15 指令「启动 DSIP 的还原。首先把闸门的要求理一遍。」
- 本文件**只做复核**：把适用闸门逐条列出、逐条对照工作区实际证据、给出结论与待决项。
- **未启动任何重建阶段**：没有下载权重、没有跑推理、没有改上游、没有在 `src/dsip_reconstruction/` 里写任何代码。
- 相关文件：`AGENTS.md`（§"DSIP reconstruction scope"）、`docs/dsip_reconstruction/reconstruction-plan.md`、
  `docs/baselines/{fairness-protocol,psl-matrix-results,psl-execution-results,fcfs-correctness-audit}.md`

---

## 1. 一共适用**三层**闸门，别只看第一层

| 层 | 来源 | 作用 |
|---|---|---|
| **L1 启动闸门 G1–G4** | `reconstruction-plan.md` §2 | 决定**能不能开工** |
| **L2 资产与不可协商边界** | `AGENTS.md` DSIP scope | 开工后**每一步都要满足** |
| **L3 阶段闸门 S0–S8** | `reconstruction-plan.md` §4 | 每个阶段结束**停下等作者确认**；全矩阵另需单独授权 |

---

## 2. L1：G1–G4 逐条复核

### G1 至少一个 AIM 基线在论文口径下产出可报告数字

**要求原文**：3 路网 × 5 密度 × 30 seeds × 1000 s × 0.1 s。

**实际证据**（本次复核实测）：

| 层级 | 规模 | 证据 |
|---|---|---|
| PSL **计划侧** | **450 / 450 run**（3 路网 × 5 密度 × 30 seeds） | `results/psl_matrix/matrix_summary.csv`：`status=ok` 450 行、15 个 cell、30 个 seed、**违规 0**；17.05 亿对冲突顶点 |
| PSL **交通侧** | **15 run**（cross3 × 3 密度 × 5 seeds，另 15 个无控制对照） | `results/psl_tr/`、`evaluation/figures/psl_baseline/psl_traffic_by_seed.csv`（30 行） |

⇒ **结论取决于 G2 的口径选择**：
- 若口径 = **计划侧** ⇒ G1 **PASS**（450/450 已完整覆盖论文协议）；
- 若口径 = **交通侧** ⇒ G1 **FAIL**（只有 1 路网 × 3 密度 × 5 seeds，是 pilot）。

### G2 执行/对比口径已定案并可辩护

**要求**：写进 `docs/baselines/fairness-protocol.md`。

**实际状态**：**FAIL（未定案）**。该文件有输入同一化、运动学同一化、指标定义、产物规范，
但**没有一条"本次对比以计划侧还是交通侧为准"的决定**。

**为什么现在必须定**：交通侧实测表明 PSL 的时刻表**不能被精确执行**——
进入偏差 p50 **20.7 / 23.6 / 26.5 s**（d1/d3/d5），计划侧速率恒定 1.52–1.55 veh/s
而 MinD 协调需求 2.38 veh/s（`psl-execution-results.md` §7）。所以两种口径给出的"PSL 数字"
**不是同一个东西**，必须二选一并在论文里说清。

### G3 FCFS 的 D-03 崩溃缺陷已修且有单测

**实际状态**：**PASS**。

- D-03 已修（`stopped_ok` / `stop_failed` 拆分、`resume` 门控、升级释放、重试封顶）；
- **同日又修了 D-01**（`A_MIN` 0.5 m/s²，窗口带宽度 0 → 2.62 s）与 **D-02**（`dt_safe` 只计一次）；
- 单测：`python3 -m baselines.fcfs_sumo.test_logic` → `failures: none`（含 D-01/D-02/D-03 共 14 项断言）；
- 真实运行 200 s：`rc=0`、`Failed to resume` 119 → 18、无 heap/连接错误。

**残留（不阻塞 G3，但必须登记）**：`dt_safe = 2.0 s` 在本场景**处于临界**——
100 s 测试里 seed 81890 出现 1 次碰撞（81891/81892/81893 均 0）。正式扫描前需重标定。

### G4 作者明确下达"开始重建"指令

**实际状态**：**PASS**（2026-11-15 本指令）。

### L1 小结

| 闸门 | 结论 |
|---|---|
| G1 | ⚠️ **取决于 G2**：计划侧 PASS / 交通侧 FAIL |
| **G2** | ❌ **FAIL —— 唯一阻塞项** |
| G3 | ✅ PASS（附带 1 项残留：`dt_safe` 待重标定） |
| G4 | ✅ PASS |

⇒ **只要 G2 一定案（选计划侧），L1 立即全绿。**

---

## 3. L2：开工后每一步都要满足的边界（复核资产是否就绪）

| # | 要求 | 现状（本次实测） |
|---|---|---|
| 1 | 固定 prior **只用** `EnvEmptyNoWait2D-RobotPlanarDisk` | ✅ 权重在位：`third_party/_local/_assets/data_trained_models/EnvEmptyNoWait2D-RobotPlanarDisk/checkpoints/ema_model_current.pth` 等，SHA256 已记在 `checkpoint_manifest.md` §4 |
| 2 | 固定协调器 **MMD-xECBS + Experience Reuse** | ✅ 上游 `third_party/_local/mmd/` 在 `5c2597eb…`（与清单一致），`mmd/planners/multi_agent/cbs.py` 在位 |
| 3 | 上游保持 **pristine** | ⚠️ **一处偏离**：`third_party/_local/mmd/` 下有若干 **untracked `__pycache__/`**（此前使用留下）。源码未改，但严格意义上不是 pristine → S0 里清理并记录 |
| 4 | 适配代码只在 `src/dsip_reconstruction/` | ✅ 该目录尚不存在内容（`src/` 只有 `.gitkeep`），**这正是待建的地方，目前为空** |
| 5 | 不重训、不改架构 | 代码侧尚无任何改动，符合 |
| 6 | 运行环境 | ✅ conda `mmd` 环境：Python 3.8.20、PyTorch **2.0.0+cu118**、`cuda.is_available() == True`、RTX 4060 Laptop 8 GB（与 `mmd_environment_report.md` §5 一致） |
| 7 | 两种执行模式不混用（`paper_faithful` / `dynamics_aware`） | 尚未实现 → S3/S4 才涉及 |
| 8 | 结果一律标 `DSIP-Reconstructed` | 尚未产出结果 |

**结论**：资产与环境**已在位**，唯一需要动手清理的是第 3 项（`__pycache__`）。

---

## 4. L3：阶段闸门（每阶段停下汇报）

| Stage | 内容 | 停点 |
|---|---|---|
| S0 | 环境/权重复核（复用既有审计）+ 清理 `__pycache__` | 停 |
| S1 | **单次单车**推理（`EnvEmptyNoWait2D`）：加载/维度/去噪步数/GPU | 停 |
| S2 | 多车 **MMD-xECBS + Experience Reuse** 链路：调用顺序、约束生成、日志 | 停 |
| S3 | SUMO 接口：路线提取、轨迹下发、步长对齐，1 场景端到端 | 停 |
| S4 | 新统计量 A：**最大加速度 / jerk** | 停 |
| S5 | 新统计量 B：**时延 {0,50,100} ms × 丢包 {0,1,5} %** | 停 |
| S6 | 新统计量 C：**CBS 时延分布 + 400 ms 超时率 + 真实回落机制** | 停 |
| S7 | 小规模复核（1 路网 × 1 密度 × 3–5 seeds） | 停 |
| S8 | 全矩阵提案 | **未确认不跑** |

另：**450-run DSIP 全矩阵**需要在上述之外**再单独授权**（`AGENTS.md`）。

---

## 5. 需要作者裁决的两件事（都只差一句话）

### D-A（阻塞 L1）：PSL 的对比口径选哪个？

| 选项 | G1 是否通过 | 论文里怎么写 | 代价 |
|---|---|---|---|
| **A1 计划侧为准** | ✅ 立即通过（450/450 已在手） | "PSL as a planning-side optimisation baseline: completion fraction / entry delay / effective rate" | 无吞吐/行程时间/碰撞 |
| **A2 交通侧为准** | ❌ 仍需扩到 3 路网 × 5 密度 × ≥3 seeds，且必须带"停走执行 + 进入偏差" | "PSL timetable + stop-and-go execution" | 需再跑批，且口径更弱 |
| **A3 混合（建议）** | ✅ 通过（以 A1 为 G1 依据） | 主表用计划侧；交通侧作为**次级安全/效率表**，明确标注偏差 | 无额外跑批 |

**我的建议：A3。** 它既满足闸门，又不丢弃已经测到的交通侧安全性证据。

### D-B（不阻塞，但影响 S4/S5 的解释）：`sumo-vehicle-dynamics.md` 的 8 项待调研

`emergencyDecel`、车宽、jerk 阈值、`speedFactor`、换道参数、IDM 其余参数、
`sigma=0.5` 是否有意、单一 `vTypeDistribution`。
在这些回填前，S4 的加速度/jerk **只能报分布，不能下"是否可行"的结论**。

### 另需确认（有备而来，不必今天答）

- 转向比敏感性：已按你的指示**只给 DSIP**、**只做 cross3 × MedD** 一个工况，
  flow 文件已生成（`lanes3_density3_r111/r122.rou.xml`），等 S7 之后再用。
- 稿件只写 **CBS**、未提 xECBS / Experience Reuse / checkpoint 名 → 只登记，不改稿。

---

## 6. 复核结论

> **L1 只剩 G2 一项未过，且它是"一句话裁决"而不是技术工作量。
> L2 的资产与环境全部就位（仅需清理上游的 `__pycache__`）。
> L3 的 S0–S8 停点已明确。**
>
> ⇒ 作者确认口径（建议 A3）后，**S0 可立即执行**；S0 本身不跑仿真，只做复核与清理。
