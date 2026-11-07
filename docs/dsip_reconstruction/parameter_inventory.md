# DSIP 参数恢复清单（Stage 0 审计结果）

- 建立日期：**2026-11-07**；审计对象：`paper/submitted/overleaf/…/main.tex`（657 行、26 式、8 图、2 表）、
  `scenarios/`、`experiments/`、`docs/`
- **原 DSIP 源码、checkpoint、逐 run 数据在工作区内不存在**（`grep -rl` 全仓无 `diffusion|xecbs|cbs` 的 py/yaml/json 命中；
  `src/` 与 `evaluation/` 只有 `.gitkeep`）。
- 状态标签：`RECOVERED` / `PAPER_SPECIFIED` / `AUTHOR_SPECIFIED` / `MMD_REFERENCE` / `INFERRED` / `TUNED` / `UNKNOWN`

> ⚠️ 本清单中 **没有任何一项是 `RECOVERED`**——原始实现已丢失，这是本轮重建的出发点。
>
> 📌 **Stage 1（2026-11-07）已回填**：第 1/3/4/5/9/10/11/12 行与第 29/30 行已从
> upstream + checkpoint 得到实测值，**以 §4「Stage 1 回填」为准**（本表保留为 Stage 0 的历史快照）。

---

## 1. 主表

| # | 参数 | 原稿是否明确 | 原代码是否存在 | 当前处理 | 状态 |
|---|---|---|---|---|---|
| 1 | Pretrained checkpoint | **否**（仅写"pre-trained single-agent diffusion planner following [41]"，main.tex:194；全文**无** EmptyNoWait/Empty2D 等模型名） | 否 | 按作者指定使用 `EnvEmptyNoWait2D-RobotPlanarDisk` | **AUTHOR_SPECIFIED** |
| 2 | Low-level planner（MPD / MPDEnsemble） | 否 | 否 | 待 Stage 1 读上游；在无原代码前**不擅自降级为 MPD** | **UNKNOWN** |
| 3 | High-level planner | **写的是 "CBS-based"**（main.tex:194/351/358/371/386/402/413；Alg.1 名 `CBS-Diffusion-Plan`），全文**无** `xECBS`/`ECBS`/`experience reuse`（grep 计数 **0**） | 否 | 按作者指定实现 **MMD-xECBS**（含 Experience Reuse） | **AUTHOR_SPECIFIED**（与稿件**不一致**） |
| 4 | Regular denoising steps | 否（`M` 仅符号，main.tex:249） | 否 | 暂用 MMD 参考值 **25**，Stage 1 到上游代码核实 | **MMD_REFERENCE** |
| 5 | Experience reuse noising steps | 否（稿件完全未提） | 否 | 暂用 MMD 参考值 **3**，同上核实 | **MMD_REFERENCE** |
| 6 | Trajectory horizon `H` | 否（仅符号，main.tex:185/442） | 否 | 从 checkpoint 配置恢复（Stage 1/2） | **UNKNOWN** |
| 7 | Trajectory duration（秒） | 否 | 否 | 由 `H × Δt_MMD` 推出，`Δt_MMD` 亦未知 | **UNKNOWN** |
| 8 | Number of samples / query | 否（全文 `samples` 仅指仿真样本） | 否 | Stage 1/2 从上游 inference 配置恢复 | **UNKNOWN** |
| 9 | Guidance weights `λ_p, λ_g, λ_l, λ_s, λ_c` | **否**（只有符号，main.tex:218/227-236，无数值） | 否 | 先取 MMD Appendix A.4 参考（smooth 0.08 / obstacle 0.02 / strong 0.20 / weak 0.02）作**起点**，再标定 | **UNKNOWN → MMD_REFERENCE 起步** |
| 10 | Guidance step size `η` | 否（仅符号，main.tex:288） | 否 | 同上 | **UNKNOWN** |
| 11 | Collision radius `ρ` | 否（仅符号，main.tex:325/364）；**1.5 m 是评价阈值**（main.tex:135/168），不是扩散半径 | 否 | 需由车长/车道宽 + MMD disk 尺度换算，**不得**直接套 MMD 的 0.10/0.12 | **UNKNOWN** |
| 12 | 约束时间半宽 `Δh` | 否（仅符号，main.tex:365） | 否 | 需与 `Δt_MMD` 对齐后确定 | **UNKNOWN** |
| 13 | Lane guidance | **是**：`L_lane = Σ_{h=0}^{H} d²(x_h, P^lane)`，取到最近参考点距离（main.tex:301-312）；参考点由 TraCI 当前 lane shape 采样（main.tex:384/463） | 否 | 按公式实现 | **PAPER_SPECIFIED** |
| 14 | Goal guidance | 部分：目标点取 route 首/末 edge（main.tex:176/460-462），越界裁剪到 map bounds | 否 | 按描述实现；具体损失形式（欧氏距离？仅末点？）**未指定** | **PAPER_SPECIFIED（形式未定）** |
| 15 | Smoothness guidance | 仅说"suppresses abrupt trajectory changes"（main.tex:236） | 否 | 具体形式**未指定**（一阶/二阶差分？） | **UNKNOWN** |
| 16 | Collision loss | **是**：`b=(c_b,ρ_b,H_b)`、`L_col=Σ_bΣ_{h∈H_b}[ρ_b-d_{i,b,h}]²_+`（main.tex:315-348） | 否 | 按公式实现 | **PAPER_SPECIFIED** |
| 17 | 新增冲突约束 | **是**：`b_{ij,h_c}=(c_{ij,h_c}, ρ_{ij}, [h_c-Δh, h_c+Δh])`（main.tex:359-368） | 否 | 按公式实现 | **PAPER_SPECIFIED** |
| 18 | 状态向量维数 | **是：`x=[x,y]^T`**（main.tex:186-191） | 否 | **与 MMD 冲突**：MMD 状态含速度 `[x,y,vx,vy]`。内部保持上游 4 维，输出层投影为位置 | **PAPER_SPECIFIED + 已知偏差** |
| 19 | Planning interval | **是**：`K_p=4` 步 = **0.4 s**（Alg.1 输入 main.tex:442；main.tex:386/390） | 否 | 0.4 s | **PAPER_SPECIFIED** |
| 20 | SUMO step | **是**：**0.1 s**（main.tex:404/411/442） | 否 | 0.1 s | **PAPER_SPECIFIED** |
| 21 | SUMO 执行方式 | **是**：读轨迹点→越界裁剪→由相邻点算 heading→TraCI 移动到目标位置，保留 SUMO route（main.tex:392/479-484）；速度由位移近似（Eq.24） | 否 | 需确认具体 TraCI API 与 `speedMode`/`laneChangeMode`（**未写**） | **PAPER_SPECIFIED（API 未定）** |
| 22 | 最大速度 | **是**：50 km/h = **13.9 m/s**（main.tex:135） | 场景文件侧已有（`types.typ.xml` maxSpeed=13.9） | 13.9 | **PAPER_SPECIFIED** |
| 23 | 转弯比 | **是**：L:S:R = **1:2:1**（main.tex:122） | `scenarios/flows` 已按此生成 | 1:2:1 | **PAPER_SPECIFIED** |
| 24 | 仿真时长 / 种子 | **是**：**1000 s**、每配置 **30** 个种子、3 路口 × 5 密度 × 5 方法 = 75 配置（main.tex:491） | 种子表 `experiments/seeds_30.txt`（81890–81919，作者口述） | 沿用 | **PAPER_SPECIFIED**（种子为 AUTHOR_SPECIFIED） |
| 25 | 密度表 | **是**：Table I，MinD 240/480 … MaxD 600/1200 veh/(h·lane)（main.tex:101-120） | `scenarios/flows/` 15 个文件 | 见 §2 的实测差异 | **PAPER_SPECIFIED** |
| 26 | 发车间隔分布 | **是**：`ΔT ~ N(3600/(nd), 1)`（Eq.1, main.tex:126-130） | `generate_flows.py` 用 `normal(100/count, 1.0)` | 见 §2 | **PAPER_SPECIFIED** |
| 27 | 安全评价阈值 | **是**：车间距 < **1.5 m** 记为 critical proximity（main.tex:135/168） | 无 | 仅作评价指标，**不得**当扩散半径 | **PAPER_SPECIFIED** |
| 28 | 规划耗时 7.75 ms/query | **是**（main.tex:607/612），硬件 i7-12650H + RTX 4060 + 64 GB，10 000 步→**2500 次**查询 | 否 | **计时边界未说明**（单 forward？整车 sampling？整 cycle？）→ 本轮必须重新分桶测量 | **PAPER_SPECIFIED（口径 UNKNOWN）** |
| 29 | Map bounds / workspace | 部分：从 SUMO 计算 map bounds 并裁剪（main.tex:450/462/481） | 否 | MMD 训练 workspace（2×2 units）与 SUMO 米制的换算关系**未写** | **UNKNOWN（关键）** |
| 30 | MMD 时间采样间隔 `Δt_MMD` | 否 | 否 | 从 checkpoint 配置恢复，**不得**假定等于 0.1 s | **UNKNOWN（关键）** |

---

## 2. 已核验的数值一致性（工作区内可复算）

| 检查 | 结果 |
|---|---|
| Table I 与 `scenarios/flows` 的 lanes3 档 | **精确吻合**：480/600/768/960/1200 veh/(h·lane) |
| Eq.(1) 与 lanes3_density1 发车间隔 | `3600/(3×480)=2.5 s`，文件里正是 `normal(2.5, 1.0)` ✅ |
| lanes2 / lanes4 档 | 实际为 **468/612/756/972/1188**（`3600/(2×468)=3.846 s` 与文件 `normal(3.846153846,1.0)` 一致），**不等于** Table I 的 480/600/768/960/1200 |
| 原因 | `generate_flows.py` 由 `routes.txt` 的"每进口每方向车辆数"反推间隔，取整后 per-lane 率略低 |
| 影响 | lanes2/4 的"S"列与 Table I 有 **2.5% 左右** 的口径偏差；**必须在公平协议里声明**，不得当作完全一致的输入 |

> 结论：Table I 只在 **3 车道档**上被文件精确实现；2/4 车道档是"按同比例缩放"的**近似**。

## 3. 稿件中**根本没有**的参数（重建时必须自定并记录）

1. `M`（总扩散步数）、`η`、`Δh`、`ρ_b`、`λ_*`、`λ_p` 的**任何数值**；
2. 采样数（每车每 query 生成几条轨迹）；
3. `H` 与 `Δt_MMD`；
4. Experience Reuse 的**存在与步数**（稿件完全未提）；
5. checkpoint 身份与版本；
6. TraCI 执行的具体 API/模式；
7. 7.75 ms 的计时边界。

⇒ 这些一律 **`UNKNOWN`**；Stage 1–3 逐项恢复后回填本表，**不得**用 MMD 默认值冒充 DSIP 原值。

---

## 4. Stage 1 回填（2026-11-07，全部为实测）

来源：`third_party/_local/mmd`（HEAD `5c2597eb…`）、`EnvEmptyNoWait2D-RobotPlanarDisk/args.yaml`、
`checkpoints/ema_model_current_state_dict.pth`、`mmd/config/mmd_params.py`。
详见 `checkpoint_manifest.md` 与 `mmd_environment_report.md`。

| # | 参数 | 恢复值 | 状态 |
|---|---|---|---|
| 1 | Pretrained checkpoint | `EnvEmptyNoWait2D-RobotPlanarDisk`（**full 归档**，作者 Q1 裁决）；推理实际加载 `checkpoints/ema_model_current_state_dict.pth`，SHA256 `ed1180b1…3444` | **RECOVERED**（文件存在且已验）＋AUTHOR_SPECIFIED（选 full 版） |
| 2 | Low-level planner（MPD / MPDEnsemble） | 两个类都在（`mpd.py`、`mpd_ensemble.py`）；**默认接哪个待 Stage 2 实测** | **UNKNOWN**（阻塞于 Stage 2） |
| 3 | High-level planner | 上游 `mmd/planners/multi_agent/cbs.py`；`multi_agent_planner_class="XECBS"` 才同时开启 `is_xcbs/is_ecbs`；否则默认是 ECBS | **RECOVERED**（机制）/ 配置值由我们指定（作者 Q3：入口在 `scripts/`） |
| 4 | Regular denoising steps | **25**（`args.yaml:n_diffusion_steps`，且权重内 `betas` 形状 = `[25]` 二次确认） | **RECOVERED** |
| 5 | Experience reuse noising / denoising steps | **3 / 3**（`mmd_params.py`；`run_local_inference(seed, n_noising, n_denoising)`） | **MMD_REFERENCE（默认值）** |
| 6 | Trajectory horizon `H` | **64** | **MMD_REFERENCE** |
| 7 | Trajectory duration / 时间步 | **5.0 s** ⇒ `Δt_MMD = 5.0/64 = 0.078125 s` | **MMD_REFERENCE（INFERRED）** |
| 8 | Number of samples / query | **64**（`n_samples`） | **MMD_REFERENCE** |
| 9 | Guidance weights | collision **0.02**、smoothness **0.08**、constraints(strong) **0.20**、soft(weak) **0.02** | **MMD_REFERENCE** |
| 10 | Guidance step size `η` | 上游以 `weight_grad_cost_*` 承担引导强度，无独立 `η` 参数 | **MMD_REFERENCE**（DSIP 的 η 仍 UNKNOWN） |
| 11 | Collision radius | MMD 侧：robot disk r=**0.05**（直径 0.10）、xECBS 顶点约束半径 **0.12** | **MMD_REFERENCE**；**SUMO 车辆半径的换算仍 UNKNOWN** |
| 12 | 约束时间半宽 `Δh` | 上游用 `start_time_l` + 路径点索引表达时间冲突，无独立 Δh | **UNKNOWN**（需在 DSIP 适配层定义） |
| 29 | Map bounds / workspace | 训练环境 `limits = [[-1,-1],[1,1]]`（2×2 units） | **RECOVERED**（模型侧）；SUMO→MMD 尺度换算仍 **UNKNOWN** |
| 30 | MMD 时间采样间隔 | 见第 7 行：**0.078125 s** | **INFERRED**（= 5.0/64） |

### 4.1 仍未恢复（与上表不冲突）

- DSIP 自己的 `λ_p`（先验权重）与 `η`：上游用固定 `weight_grad_cost_*`，DSIP 论文写
  `L^post = L − λ_p log P_θ`，**两者不是同一参数体系** ⇒ DSIP 侧取值仍 `UNKNOWN`，只能标定后标 `TUNED`。
- SUMO 车辆（长 5.0 m / 宽 ~1.8 m）与 MMD disk（直径 0.10 units）之间的换算系数 `s`。
- TraCI 执行 API 与 `speedMode`/`laneChangeMode`。

### 4.2 一条重要结论

**"25 步"与"3 步"不是同一层面的数字**：25 是常规 DDPM 推理的扩散步数（模型固有，写进权重），
3 是 experience-reuse 局部分支的加噪/去噪步数。**不得**把所有规划都设成 3 步；
也**不得**把 3 当成"总步数"写进论文。

