# DSIP 重建实现决策（Stage 0 定稿 v0）

- 日期：**2026-11-07**；状态：**DECISION v0**（可在 Stage 2/3 依据上游代码事实修订，修订需记录）
- 依据：作者任务书 §0/§4/§5/§6/§8/§9/§10；`docs/dsip_reconstruction/manuscript_audit.md`；`parameter_inventory.md`
- 铁律：**上游 `third_party/_local/mmd/` 保持 pristine**；所有适配代码在 `src/dsip_reconstruction/`

---

## D-01 以上游为库，不在本仓库重写算法

- 用 **wrapper / adapter** 调用上游 MMD 的类与函数（`mmd/`、`scripts/inference/`、`deps/motion_planning_baselines/`）。
- **禁止**把上游源码复制进 `src/`（许可未明 + 无法追溯）。
- 若某功能上游没有（如 SUMO 桥接），才在本仓库新写，并在文件头注明"reconstruction"。

## D-02 模型固定为 EmptyNoWait

- 唯一允许：`EnvEmptyNoWait2D-RobotPlanarDisk`。
- 禁止：Empty2D / Highways2D / Conveyor2D / 自训模型替换；禁止重训练。
- checkpoint 身份、来源、SHA256 记录到 `checkpoint_manifest.md`（Stage 1 产出）。
- 若 checkpoint 不可用 → **停止并报告**，不得换模型继续。

## D-03 高层协调固定为 MMD-xECBS（含 Experience Reuse）

- 必须是 xECBS：**strong + weak constraints** 与 **experience reuse**（父轨迹→有限步加噪→新约束下去噪）。
- 组件级要求：
  1. 正常推理默认 **25** 步（MMD 参考，待上游核实后固定）；
  2. reuse 重规划默认 **3** 步加噪（同上）；
  3. **不得**把全部规划都设成 3 步；
  4. 父节点轨迹必须真正传给子节点；**不得**跨 CT 节点共享不属于自己的缓存；
  5. reuse 失败时必须回落到完整规划。
- **实现顺序**：先在 Stage 3 用**上游原脚本**跑通小规模多机器人 xECBS，
  再在 Stage 5 把 DSIP 的 SUMO 约束接进去。**禁止**先写一个"按文字近似"的 xECBS 再倒推。
- 稿件一致性问题（稿件写 CBS）：已知并记录，**不改稿**；见 `manuscript_audit.md` §4/§6。

## D-04 状态维数：内部 4 维，输出 2 维

- 内部保持上游 state（含速度），不做降维；
- DSIP 代价层（lane/goal/smooth/col）与 SUMO 输出层只使用位置分量；
- 任何"因为稿件写 2 维就把模型改成 2 维"的做法**禁止**。

## D-05 坐标变换：单一相似变换 + 反向变换

`x_MMD = s·R·x_SUMO + b`，**同一组 (s, R, b)** 用于位置、目标点、车道点、速度、半径、map bounds。

- **禁止**对 X/Y 分别缩放（会改变道路几何）；
- 必须实现 `sumo→mmd` 与 `mmd→sumo` 双向，并在 Stage 4 用"往返误差 < 1 mm"作单测；
- 必须核验**比例尺合理性**：`车道宽/车长` 与 `模型 disk 直径/工作空间` 的比值关系要能自圆其说，
  并把数字写进 `implementation_decisions.md` 的修订记录；
- 优先恢复原 DSIP 的换算方式；无原代码时，由 SUMO 实际几何 + checkpoint 训练 workspace 推导，
  并记录为 `INFERRED`。

## D-06 时间尺度：先从 checkpoint 恢复，再对齐

- `Δt_MMD` 未知 → Stage 1/2 从模型配置与训练数据配置读出，**不得**假定其等于 0.1 s；
- 需实现轨迹重采样：`Δt_MMD` ↔ 0.1 s（执行）/ 0.4 s（规划刷新）；
- 三个时间索引必须一致：xECBS 约束时间索引、轨迹点索引、SUMO 步索引；
- 若 `Δt_MMD` 与 0.4 s 不能整除，记录取整策略（并在指标里报告由此产生的误差）。

## D-07 两种执行模式严格分离

| 模式 | 目录 | 内容 |
|---|---|---|
| **Mode A / paper-faithful** | `results/dsip_reconstructed/paper_faithful/` | 理想化位置控制（TraCI 移动到轨迹点），不加动力学约束 |
| **Mode B / dynamics-aware** | `results/dsip_reconstructed/dynamics_aware/` | 在 A 基础上增加 v/a/曲率/航向/矩形车身碰撞/跟踪误差校验，越界即记录失败或重规划 |

- 两模式**永不混表**；Mode B 不得冒充 A。
- 每个结果行的 `run_manifest.json` 必须写 `mode: paper_faithful | dynamics_aware`。

## D-08 仪表化（先写计量，再谈性能）

每次 planning query 记录任务书 §4.3 的 13 项计数：
`initial_agent_planning_calls, regular_denoising_steps, experience_reuse_calls,
experience_reuse_noising_steps, experience_reuse_denoising_steps, low_level_planner_calls,
high_level_expanded_nodes, high_level_generated_nodes, detected_conflicts, resolved_conflicts,
trajectory_reuse_count, planner_timeout_count`（+ `num_active_vehicles`）。

计时分桶（任务书 §10）：
`network_forward_ms, single_agent_sampling_ms, initial_root_planning_ms, experience_replanning_ms,
xecbs_search_ms, collision_validation_ms, trajectory_update_ms, full_planning_cycle_ms`。

- CUDA 计时必须 `torch.cuda.synchronize()` 前后同步；用 `perf_counter`；
- 报告 mean/median/P95/P99/max + **400 ms deadline miss rate**；
- **禁止**把"一次 forward"当成"一次 planning query"；**不得**声称已达 7.75 ms。

## D-09 安全执行：不执行未验证轨迹

每次应用新轨迹前检查：map bounds、起点连续性、终点合法性、多车碰撞、时间索引、车辆状态匹配。

- 任一项失败：**保留上一条有效轨迹**（或明确的安全降级），记录 `deadline_miss` / `invalid_trajectory`；
- **禁止**把规划失败静默当成成功；
- 降级行为在 Mode A 与 Mode B 中分别记录（论文的"理想化执行"必须与降级路径分开说明）。

## D-10 命名与声明纪律

- 所有新结果标 `DSIP-Reconstructed`；论文/文档中不得写成"原始 DSIP 实现"；
- 历史投稿数字（0 碰撞 / 3 次急刹 / 450 runs / 7.75 ms）只作**历史声明**引用，不作为本轮验证结论；
- 不得把 MMD 的机器人实验耗时与 DSIP 的 7.75 ms 直接比。

## D-11 目录（**Stage 4 起才创建**，本轮不建）

按任务书 §15 建 `src/dsip_reconstruction/{config,geometry,mmd_adapter,guidance,coordination,sumo,validation,metrics}`。
本轮（Stage 0）**只写文档**，不建空模块，避免"看起来已实现"。

## D-12 环境策略

- 本机已有 `mmd` conda 环境（Python 3.8.20 / PyTorch 2.0.0+cu118 / RTX 4060 可见），
  见 `docs/env/mmd-environment-audit.md`；Stage 1 先**验证**它是否满足克隆 commit 的 `requirements.txt`。
- **不修改** base、`mmd` 之外的任何 conda 环境；
- 若需新建环境，用独立名字（如 `dsip-recon`），并记录 `conda list --export`。
- traci/sumolib 1.24.0 ↔ SUMO 1.12.0 的版本偏差是已知风险，Stage 6 集成时复核。

## D-13 分阶段闸门（与 `AGENTS.md` §2 一致）

Stage 0 审计 → 1 环境/checkpoint → 2 单车 → 3 上游 xECBS → 4 DSIP 单车适配 → 5 多车适配 →
6 SUMO 单场景 → 7 pilot → 8 调参 → 9 正式实验。
**每阶段结束保存证据并停下等作者**；450 次矩阵只在 Stage 9 且需**单独授权**。

---

## D-02a 低层规划器的默认选择（Stage 1 修订）

- 上游同时提供 `MPD` 与 `MPDEnsemble`；`scripts/inference/*` 通过 `model_ids` 构造，
  具体默认分支**尚未实测确认**。
- 因此：Stage 2 必须先读出"官方入口实际实例化的是哪一个"，并在报告中写明；
  若无原 DSIP 代码证据要求相反，则**沿用官方入口的选择**，不擅自换成另一个。
- 记录字段：`run_manifest.json → low_level_planner_class`。

## D-03a xECBS 必须由调用方显式开启（**关键**）

- `CBS.__init__` 默认 `is_xcbs=False, is_ecbs=True` ⇒ **默认跑的是 ECBS**；
- `scripts/inference/inference_multi_agent.py:112-113` 依据
  `multi_agent_planner_class` 在 `["XECBS","XCBS"]` 中才把 `is_xcbs` 置真；
- ⇒ 我们的所有多车实验配置必须写 **`multi_agent_planner_class: "XECBS"`**；
- 每次 planning 记录 `is_xcbs / is_ecbs / experience_reuse_strategy` 三个字段到
  `planner_statistics.json`，并在 Stage 3 用"是否出现 `experience_reuse_calls > 0`"作为
  **xECBS 真的被启用的判据**。

## D-14 Mode A 保留 SUMO 碰撞检测（作者 2026-11-07 裁决）

- Mode A（`paper_faithful`）仍是理想化位置控制，但**必须同时开启**
  `--collision.action warn` 并采集 `simulation.getCollisions()`；
- 目的：让"0 碰撞"这一历史声明有可复算的口径，而不是靠关闭检测得到；
- 若未来改用 `moveToXY` 一类绕过 SUMO 动力学的接口，必须在结果中显式标注
  "collision detection bypassed"，且不得与 Mode A 的其它运行混表。

## D-15 需求车流以稿件 Table I 为权威（作者 2026-11-07 裁决）

- `scenarios/flows/*.rou.xml` 已于 2026-11-07 **全部重生成**：
  `μ = 3600/(n_lanes·density)`（Eq.1）、`number = round(1000/μ)`、σ=1.0；
- 三种车道配置现在实现**同一** per-lane 需求（480/600/768/960/1200 与 L&R 240/300/384/480/600）；
- `scenarios/original/routes.txt` **不再是输入**（仅作生成脚本里的信息性交叉核对）；
- ⚠️ 2026-11-07 之前用旧车流跑出的任何结果（含 `results/fcfs_sweep/`）**不可与新结果混比**；
- 校验：`python3 scenarios/flows/validate_flows.py` → **15/15 OK**（exit 0）。

