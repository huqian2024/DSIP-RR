# DSIP 重建：未解决问题清单（Stage 0 结束时）

- 日期：**2026-11-07**
- 说明：以下问题**在 Stage 0 无法从工作区内证据回答**。每条都给出"为什么现在答不了"和"最小验证动作"。
- 标记：🔴 阻塞后续阶段 / 🟡 影响参数取值 / 🟢 影响表述与公平性

---

## 0. 作者已回答（2026-11-07，本轮据此执行）

| 问题 | 作者裁决 | 落实位置 |
|---|---|---|
| **Q1** checkpoint 版本 | **full 版本**（`data_trained_models.tar.xz`，gdrive id `1WO3tpvg…`） | `checkpoint_manifest.md`（已下载并校验，含 EnvEmptyNoWait） |
| **Q3** xECBS 入口 | **`scripts/`**（`scripts/inference/*`）；实现本体在 `mmd/planners/multi_agent/cbs.py` | `mmd_environment_report.md` §3；**新增 D-03a：必须显式设 `multi_agent_planner_class="XECBS"`** |
| **Q9** Alg.1 与 xECBS 不一致 | **选项 1：只改术语**（不改算法描述的实质） | `manuscript_audit.md` §6 第 1 条降级为"仅术语"；**本轮仍不动稿** |
| **Q5/Q6/Q7** 数值缺失 | 作者已丢失，但**默认参数当年表现良好**，允许按 MMD 默认值调整 | 上表各参数标 `MMD_REFERENCE`，调参在 Stage 8 标 `TUNED` |
| **Q10** Mode A 是否保留碰撞检测 | **暂时保留碰撞检测** | 新增 **D-14** |
| **Q11** 2/4 车道密度偏差 | **重新生成 flows** | 已执行：`scenarios/flows/*` 全部按 Table I 重生成，校验 15/15 OK |

以下 Q1–Q12 原文保留，作为决策过程记录；已答项不再重复询问。


---

## Q1 🔴 checkpoint 到底是哪一份？

- 现状：稿件只写 "pre-trained single-agent diffusion planner following [41]"，**从未命名模型**；
  `EmptyNoWait` 来自作者指定，不是稿件证据。
- 需确认：MMD 官方两个归档（完整 `data_trained_models.tar.xz` 与 `data_trained_models_small.tar.xz`）
  是否都含 `EnvEmptyNoWait2D-RobotPlanarDisk`；两者 SHA256 与配置是否一致；原 DSIP 用的是哪一个。
- 最小动作：Stage 1 下载后比对文件清单 + SHA256 + 配置，产出 `checkpoint_manifest.md`，交作者裁定。

## Q2 🔴 Low-level planner：`MPD` 还是 `MPDEnsemble`？

- 现状：无原代码，无法确认；仅知道稿件说"single-agent diffusion planner"。
- 风险：Ensemble 会改变采样代价，直接影响 7.75 ms 的量级与轨迹多样性。
- 最小动作：Stage 1 读上游 inference 入口，列出实际默认类；Stage 2 单车复现时两种都试一次（仅一次，非矩阵）。

## Q3 🔴 xECBS 的 weak/strong 约束与 reuse 在上游的确切位置与调用顺序？

- 现状：稿件写 CBS，未提 weak/strong 与 reuse；任务书要求恢复 xECBS。
- 需确认：上游哪个模块实现 xECBS（`deps/motion_planning_baselines/` 还是 `scripts/inference/`）；
  weak constraint 的具体权重（MMD Appendix A.4 的 0.02？）与注入方式。
- 最小动作：Stage 1 只读上源码 + Stage 3 用官方脚本跑通小规模场景，**不自行近似**。

## Q4 🟡 DSIP 是否在 0.4 s 的**规划周期之间**也复用了经验？

- 这是两类不同的"经验复用"：① xECBS 内部父子节点复用（上游机制）；② 跨规划周期复用上一周期已执行轨迹（DSIP 可能自加）。
- 现状：稿件无任何表述；无原代码。
- 影响：若②存在，等于额外的 warm-start，会显著改变耗时与轨迹连续性。
- 建议：默认**只做①**（有上游依据）；② 作为**显式可选开关**，且在结果里分开标记。

## Q5 🟡 λ_p / λ_g / λ_l / λ_s / λ_c、η、ρ_b、Δh 的初值？

- 现状：稿件只有符号；无 Appendix；无源码。
- 计划：先用 MMD Appendix A.4 的 `λ_smooth=0.08 / λ_obstacle=0.02 / λ_strong=0.20 / λ_weak=0.02`
  作为**起点**（标 `MMD_REFERENCE`），其余按 `TUNED` 记录。
- 需作者确认：是否有当年的调参笔记/截图/邮件可参照？若有，优先使用。

## Q6 🟡 `H`（horizon）与 `Δt_MMD`？

- 现状：均未在稿件给出；直接决定"一条轨迹覆盖几秒"与"0.4 s 刷新比例"。
- 最小动作：从 checkpoint 的模型配置 / 训练数据配置读出（Stage 1/2）。

## Q7 🟡 坐标换算 (s, R, b) 的原始取值？

- 现状：稿件只说"SUMO 路网投影到全局笛卡尔坐标"，未给与 MMD 工作空间的换算。
- 风险：MMD 在 2×2 units、disk 直径 0.10 的尺度上训练；SUMO 是米制、车道宽 3.2 m 量级。
  若尺度不匹配，扩散先验会退化（轨迹"太黏"或"太散"）。
- 最小动作：Stage 4 先做**尺度自检**：让模型在无约束下生成直线轨迹，检查可覆盖的道路长度；
  再定 s，并写进决策记录。

## Q8 🟢 7.75 ms 的计时边界是什么？

- 现状：稿件只说 "average inference latency of 7.75 ms per planning query"，
  未说明是否包含 xECBS 搜索、碰撞校验、轨迹更新、以及是"每车"还是"整周期"。
- 影响：重建版若计时更宽（更诚实），会显得"更慢"，必须在文中有口径说明。
- 建议：本轮按 §10 分桶报告，**并明确拒绝**与 7.75 ms 做直接等价比较。

## Q9 🟡 稿件 Algorithm 1 与真实 xECBS 不一致，怎么处理？

- 现状：Alg.1 无 Experience Reuse、无 weak/strong 区分、无超时分支。
- 选项：① 只改术语 + 补 reuse 分支；② 重写 Alg.1 使其与实现一致；③ 保持原样并在正文说明简化。
- **需作者决定**；本轮不动稿件。

## Q10 🟢 Mode A 的"理想化位置执行"是否还保留 SUMO 的碰撞检测？

- 现状：稿件说"移动到轨迹点"，但未说 `speedMode`/`laneChangeMode`/`moveToXY` 的使用细节；
  若用 `moveToXY` 会绕过 SUMO 的跟驰与碰撞逻辑，导致"0 碰撞"失去意义。
- 建议：Mode A 用**位置控制但保留碰撞检测**（`--collision.action warn`），并在文中写明。

## Q11 🟢 lanes2 / lanes4 的需求档与 Table I 有 ~2.5% 偏差，怎么处理？

- 事实：`scenarios/flows` 的 lanes2/4 实际是 468/612/756/972/1188 veh/(h·lane)，
  而 Table I 写 480/600/768/960/1200（只有 3 车道档精确吻合）。
- 选项：① 保持现状并在公平协议里声明；② 重新生成 flows 使 per-lane 率严格等于 Table I。
- 影响：跨车道数比较的口径一致性；**不影响**重建本身。

## Q12 🟢 历史 450 次 DSIP run 的种子是否就是 81890–81919？

- 现状：`experiments/seeds_30.txt` 是作者口述（2026-11-02）"81890 起连续 30 个"，属 `AUTHOR_SPECIFIED`。
- 影响：与历史结果的可比性表述（而非重建正确性）。

---

## 归纳：Stage 1 之前必须由作者回答的

| 优先级 | 问题 | 为什么必须现在答 |
|---|---|---|
| 最高 | **Q1**（checkpoint 版本） | 决定 Stage 1/2 的下载与验证目标 |
| 最高 | **Q3**（xECBS 入口与约束体系） | 决定 Stage 3 复现对象，避免自造近似 |
| 高 | **Q9**（稿件与算法不一致如何处理） | 决定后续写作策略，但不阻塞重建 |
| 中 | **Q5/Q6/Q7**（数值与尺度） | 可在 Stage 2–4 逐项恢复，之后仍需作者确认 |
| 低 | **Q10/Q11/Q12** | 影响表述与公平性，不影响算法恢复 |
