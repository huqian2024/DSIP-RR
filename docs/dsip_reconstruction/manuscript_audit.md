# 原始稿件审计（Stage 0，只读）

- 审计日期：**2026-11-07**
- 对象：`paper/submitted/overleaf/DSIP_ A Dynamic Coordination Planner …/main.tex`（**657 行**，26 式、8 图、2 表）、
  `refs.bib`（54 条）、`paper/reviews/`、`scenarios/`、`src/`、`experiments/`、`results/`、`evaluation/`
- 未改动论文任何字节；本节所有说法都给出 `main.tex` 行号。

---

## 1. 资料清单

| 资料 | 状态 |
|---|---|
| LaTeX 源 `main.tex` | **存在**（657 行，IEEEtran journal） |
| 参考文献 `refs.bib` | **存在**（54 条；[41] = `shaoul2025` = MMD / ICLR 2025） |
| 图件（8 图，含作者照片） | **存在**（png/jpg） |
| Overleaf 导出 zip | **存在** |
| 投稿版 PDF | **不存在** → 无法比对编译产物 |
| 补充材料 / 附录（Appendix） | **不存在**（全文无 appendix；λ 等数值因此无处可查） |
| 算法伪代码 | **存在 1 个**：Algorithm 1「DSIP coordination process」（main.tex:437-488） |
| 原 DSIP 源码 | **不存在**（`src/` 仅 `.gitkeep`；全仓 grep 无 diffusion/xECBS 代码） |
| checkpoint / 配置 / 训练脚本 | **不存在** |
| 实验 CSV / 逐 run 数据 / 计时日志 | **不存在**（`results/` 只有 FCFS 与 smoke 的新产物） |

## 2. 稿件实际描述的技术路线（可直接作为重建规范的部分）

| 环节 | 稿件说法 | 行号 |
|---|---|---|
| 坐标系 | SUMO 路网投影到全局笛卡尔坐标；lane centerlines/shapes/boundaries/map limits 由 TraCI 获取 | 176, 450 |
| 车辆轨迹定义 | `X_i={x_{i,0..H}}`，状态 **`x=[x,y]^T`（仅位置）** | 179-191 |
| 执行 | 每步读存储轨迹的目标位置→越界裁剪→由相邻点算 heading→TraCI 移动；保留 SUMO route；速度由位移近似 | 192, 392, 479-484, 405-411 |
| 先验 | 用**预训练**单车扩散规划器（引用 [41]），不重新训练 | 194 |
| 目标函数 | `L^post = L − λ_p log P_θ(X)`；`L = λ_g L_goal + λ_l L_lane + λ_s L_smooth + λ_c L_col` | 213-236 |
| 前向/反向扩散 | 标准 DDPM 形式；`μ̂ = μ − ηβ_{m-1}·g`，`g=∇L` | 238-291 |
| Lane 引导 | 从当前 lane shape 采样参考点 `P^lane`；`L_lane=Σ_h d²(x_h,P^lane)`（最近点距离） | 293-312, 384 |
| 冲突要素 | `b=(c_b,ρ_b,H_b)`；`L_col=Σ_bΣ_{h∈H_b}[ρ_b−d_{i,b,h}]²_+` | 314-348 |
| 新增冲突约束 | `b_{ij,h_c}=(c_{ij,h_c},ρ_{ij},[h_c−Δh,h_c+Δh])` | 358-368 |
| 高层协调 | **"CBS-based conflict-resolution module"**，每车一个 diffusion planner，冲突→加约束→受影响车重规划 | 351-374 |
| 规划周期 | 每 **4** 步查询一次 = **0.4 s**；SUMO 步长 **0.1 s** | 386-390, 442 |
| 合法性/安全校验 | 出发前静态检查（start/goal 在 map bounds 内，否则裁剪）+ 每步动态检查；只执行通过边界与冲突检查的轨迹 | 396-402 |
| Algorithm 1 | 初始化 TraCI→提地图→对 t 循环：前进 1 步、取 active、删已离开、新车建 planner、`t mod K_p==0` 时调 `CBS-Diffusion-Plan`、每步按轨迹移动车辆、记录指标 | 437-488 |

## 3. 评价口径（稿件明确）

- **TimeLoss**：`T_actual,i − d_i/v_max,i`，在**每个 logging step 的 active vehicles 上**求平均（145-154）。
  ⇒ 注意：这是"瞬时 active 集合"平均，**不是**逐车完成后的平均；重建时必须**同时**保留逐车数据（任务书 §14 亦要求）。
- **Average speed**：logging step 所有 active 车的瞬时速度均值（156-165）。
- **安全**：车间距 < **1.5 m** 记为 critical proximity；纵向减速度超 SUMO emergency braking 阈值记为 abrupt deceleration（135, 168）。
- **历史声明**：450 次 DSIP run **0 次碰撞警告**、仅 **3 次** abrupt deceleration、约 2 M 车次穿越（581-585）；
  平均推理 **7.75 ms/query**（i7-12650H + RTX 4060 + 64 GB；10 000 步 → **2500** 次查询）（607, 612）。

## 4. 与任务书要求的**三处实质不一致**（必须先解决，不得绕过）

### M-1 高层协调：稿件写 CBS，作者指定 xECBS

- `grep -ciE 'xecbs|ecbs|reuse|experience|warm.?start' main.tex` = **0**。
- 稿件全文只有 "CBS-based"、"CBS-Diffusion-Plan"；Algorithm 1 **不含** Experience Reuse，
  也没有 weak/strong constraint 的区分（只有一种"新增约束"）。
- 作者已确认原实现是 **xECBS**，并明确要求恢复 Experience Reuse（正常 25 步 / 复用 3 步加噪）。
- ⇒ **Alg.1 与真实实现不等价**。本轮按作者口径实现 xECBS（见 `implementation_decisions.md`），
  稿件修订建议单列于 §6，**不在本轮改稿**。

### M-2 状态维数：稿件 2 维位置，模型是 4 维

- 稿件 `x=[x,y]^T`（186-191），而 MMD 的状态含速度（`[x,y,vx,vy]` 量级）。
- ⇒ 重建时**内部保持上游维数**，只在 DSIP 代价层与 SUMO 输出层投影为位置；
  不得把模型内部速度状态"丢掉"（任务书 §5.3 亦要求）。

### M-3 checkpoint 与全部数值参数缺失

- 稿件**从未命名**具体模型（无 `EmptyNoWait`），只写"following [41]"（194）。
- λ/η/ρ/Δh/M/H/采样数/Δt_MMD **全部无数值**；无 Appendix 可查。
- ⇒ EmptyNoWait 属于 **AUTHOR_SPECIFIED**（作者记忆），不是 `PAPER_SPECIFIED`；
  其余数值一律 `UNKNOWN`，只能在 Stage 2/3 从上游代码与 checkpoint 配置恢复，
  再以 `TUNED` 标注（见 `docs/dsip_reconstruction/parameter_inventory.md`）。

## 5. 可用于回答审稿人的"事实性"要点（不改结论）

- R2-3（物理可行性）：稿件已自述"without claiming direct low-level vehicle actuation"（392），
  属于**理想化位置控制**；这与 R2 的批评一致 → 对应任务书 **Mode B（Dynamics-Aware）**，
  但必须与 Mode A 分开报告。
- R2-4（CBS 超时/退化）：稿件**没有**任何 fallback/deadline-miss 描述，Alg.1 里没有超时分支。
  ⇒ 重建必须显式实现"超时→保留上一条有效轨迹→记录 deadline miss"（任务书 §8.4），
  并统计 CBS/xECBS 时间分布。
- R2-1（与 [41] 的区别）：稿件把贡献定为"road adaptation + 动态交通决策 + SUMO 集成"，
  **未主张** xECBS；若改稿加入 xECBS，需同时说明 xECBS 是 [41] 的机制还是本文改动 →
  **需作者判定**（见 `unresolved_questions.md` Q3）。
- R2-8/9/10（Eq.20/23/24）：**当前源码中已一致**（Eq.19/20 均用 `\mathcal{H}_b`；
  Eq.23 的元组与区间完整；Eq.24 前有 `\bar v` 符号）→ 属"当前源码未复现该缺陷"，
  按 `AGENTS.md` §4.2 只需给出平静的事实性回复，不必改数学。

## 6. 稿件修订建议（**只记录，需作者批准后才动**）

1. **术语与算法**：若最终确认 xECBS，则 "CBS-based" 应改为 "xECBS-based"，Algorithm 1 增加
   Experience Reuse 分支（父节点轨迹→有限步加噪→在更新约束下去噪），并补 25/3 步说明。
2. **状态维数**：在 IV-A 明确"规划器内部状态含速度，DSIP 代价定义在位置子空间"。
3. **缺失数值**：至少补 λ 系列、ρ、Δh、H、M、采样数与 checkpoint 名称/来源，否则不可复现。
4. **计时口径**：7.75 ms 需说明边界（单次网络前向？单车采样？整车 xECBS 全周期？）。
5. **失败处理**：补一段 deadline miss / 无解时的降级策略（对应 R2-4）。
6. **安全声明**：把"0 碰撞"限定为"理想化位置控制下"，并给出 Mode B 的可行性统计（对应 R2-3）。

> 以上 6 条**均未执行**；本轮只做重建，不改稿。
