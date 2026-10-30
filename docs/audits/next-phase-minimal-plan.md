# 下一轮最小实施计划（Phase 2 / Task C）

- 状态：**仅草案，未实施**，等待作者确认。
- 依据：`docs/audits/scenario-provenance.md`（Task A）、`docs/audits/aim-baseline-feasibility.md`（Task B）。
- 约束：不开工前不安装依赖、不改原始 XML、不重建 DSIP。

---

## 0. 开工前必须先由作者裁定的 4 件事

| # | 待裁定 | 为什么阻塞 | 若不裁定会怎样 |
|---|---|---|---|
| 1 | **Table I 密度口径**：`d` 是否为 veh/(h·lane)，历史脚本的 1/10 系数算不算错 | 决定新 baseline 用哪套需求量 | baseline 与历史结果不可比，"中高密度"结论无法自洽 |
| 2 | **历史数据可用性**：`results/a,b,d,e` 能否作为"历史证据"引用；`results/c`（合成）如何处置 | 决定能否画三方法对比图 | 一旦把合成数据写进论文，属严重学术风险 |
| 3 | **是否授权按 `EXPERIMENT_PARAMS` 生成 15 个静态车流文件** | 这是新 baseline 的输入 | 只剩 1 个（3 车道/MaxD）车流可用，基线覆盖面过窄 |
| 4 | **CCAM-DI 是否值得做**（需新 conda 环境 + 可能重训 1M steps） | 决定是否投入 | 若权重始终拿不到，只能得到"重训版"，不能说复现 |

---

## 1. 最小 FCFS 运行测试（推荐先做）

### 1.1 目标

用**我们自己的代码**在现有 SUMO 路网上实现 Dresner–Stone 式 FCFS 预留，跑通 **1 个配置 × 1 个 seed × 1000 s**，输出与历史 CSV 同构的指标，证明管线可用（不追求性能结论）。

### 1.2 输入（全部沿用现有资产，不新建场景）

| 项 | 取值 | 来源 |
|---|---|---|
| 路网 | `scenarios/original/cross3.net.xml`（3 车道 = 双向 6 车道） | 现有文件，md5 记录在 manifest |
| 车流 | 3 车道 / 第 3 档（MedD）：直行 `number=64`、转向 `number=32` | `auto1.py: EXPERIMENT_PARAMS[3][3]` → 需按 §0-3 授权后落地为静态 rou 文件 |
| 步长 / 时长 | 0.1 s / 1000 s | 历史一致 |
| seed | 单 seed（建议 81890，历史起点） | `SEED_START` |
| traci | `PYTHONPATH=$SUMO_HOME/tools`（SUMO 1.12 自带） | 见另文 §8 隔离方案 |

### 1.3 建议模块结构（新代码，放在 `baselines/`）

```
baselines/fcfs_sumo/
├── __init__.py
├── conflict_zone.py     # 由 net.xml 的 internal lane + connection 推导冲突区/占用集合
├── reservation.py       # FCFS 请求队列 + 时空占用判定 + 授权/拒绝
├── controller.py        # TraCI 车辆控制（setSpeed/slowDown），ACZ 边界
├── runner.py            # 命令行入口：--cfg/--net/--rou/--seed/--steps/--out
├── metrics.py           # 与历史同列：step, avg_timeLoss, avg_speed, vehicle_count
└── README.md            # 协议来源（Dresner & Stone / AIM4）、假设、与 AIM4 的差异
```

关键实现约定（必须写进 README，避免"看起来像 AIM4"）：

- 先到先服务语义 = **请求到达顺序**，不重排；被拒绝的车辆在 ACZ 内停车等待重试。
- 冲突区 = 交叉口 internal lane 集合；同一时刻同一 internal lane 只允许一个方向的预留。
- 车辆按预留窗口通过 → 用 `setSpeed`/`slowDown` 近似；**明确声明无法保证 0.01 s 时间窗**（AIM4 的 `EARLY_ERROR/LATE_ERROR`）。
- ACZ 边界（进口边距停车线的距离）作为显式参数记录（默认建议 50 m，可配置）。

### 1.4 验收标准（Definition of Done）

1. `sumo` 以 0.1 s 步长跑完 1000 s，退出码 0；进程无 TraCI 异常。
2. 输出 CSV 列与历史一致（`step, avg_timeLoss, avg_speed, vehicle_count`），行数 ≈ 101。
3. `--collision.action warn` 下统计碰撞数，写入日志（**不宣称零碰撞**，除非实测为 0 且说明检测方式）。
4. 生成 `results/fcfs_sumo/<run_id>/manifest.json`：SUMO 版本、traci 路径、net/rou 的 md5、seed、ACZ 参数、代码 commit。
5. 同一命令重跑两次，指标可复现（或记录不可复现的幅度）。

### 1.5 预估与风险

- 工作量：1–2 人日（冲突区推导 + 预留逻辑 + 指标）。
- 主要风险：冲突区建模错误会导致死锁或假安全 → 必须先用**单进口 × 单车辆**、再**两进口 × 两车辆**的极小用例验证。

---

## 2. 最小 CCAM-DI 验证（第二位，且只做"环境可用性"）

### 2.1 目标

只验证"能否在自己的场景里实例化 + 跑 1 个 episode"，**不训练、不出性能结论**。

### 2.2 前置检查（本轮未能完成）

| 检查 | 状态 |
|---|---|
| PyPI 可达性（能否 `pip install ray[rllib]==2.9.3`） | 未验证；GitHub 直连已失败，pip 可能同样受限 |
| Python 3.10 可用性 | ✅ 系统 `/usr/bin/python3.10`（3.10.12）与要求一致 |
| 是否已有 ray/gymnasium | ❌ base 与 `mmd` 均无 `ray`；base 有 `gymnasium` |
| 预训练权重 | ❌ 仓库无 `saved_model/` |

### 2.3 若作者批准，最小步骤

1. 新建独立环境（**不改 `mmd`**）：`python3.10 -m venv ~/.venvs/ccamdi`。
2. 安装 `ray[rllib]==2.9.3`、`gymnasium==0.28.1`、`torch==2.0.1-cpu`（或按需 CUDA 版）——需授权且需网络。
3. 用其自带 `env/8_8_*.sumocfg` 跑 1 个 episode（随机/恒速动作），只验证观测/动作维度与 SUMO 启动。
4. 记录实际使用的 SUMO 版本（未声明，需实测 1.12 是否可用）。
5. 之后再讨论"是否值得重训 1M steps + 适配我们的路网"。

### 2.4 明确不承诺的事

- 不承诺"复现 CCAM-DI 论文结果"（无权重、需重训）。
- 不承诺在 1.12 上可运行（版本未声明）。

---

## 3. 统一实验输入与指标定义草案

### 3.1 运行标识（run_id）

```
<method>-<net>-L<lanes>-G<density_group>-S<seed>
例：fcfs-cross3-L3-G3-S81890
```

### 3.2 每次运行必须记录的输入清单（manifest）

| 字段 | 说明 |
|---|---|
| `method`, `method_version`, `code_commit` | 方法与代码版本（本仓库 commit） |
| `net_file`, `net_md5` | 路网文件与其 md5 |
| `route_file`, `route_md5`, `route_origin` | 车流文件、md5、来源（`HISTORICAL_TEMPLATE` / `RECONSTRUCTED_FROM_EXPERIMENT_PARAMS` / `AUTHOR_PROVIDED`） |
| `step_length`, `end_time`, `log_interval` | 0.1 s / 1000 s / 10 s（历史一致） |
| `sumo_version`, `traci_source` | `sumo --version` + traci 的 `__file__` |
| `sumo_seed`, `flow_seeds` | 仿真种子与 12 条 flow 的种子列表 |
| `acz_range_m`, `other_params` | 方法特有参数（FCFS 的 ACZ、CCAM-DI 的加速度上限等） |
| `collision_action` | 固定为 `warn` 以便统计 |

### 3.3 指标定义（必须显式区分两种口径）

历史 CSV 用的是**逐 step、对"当前在网车辆"求平均**，具体实现已核实：

```python
# demo_3.py / colight_core.py / attentionlight_core.py 中的记录逻辑
losses = [traci.vehicle.getTimeLoss(v) for v in veh_ids]   # SUMO 的累积时间损失
avg_loss = float(np.mean(losses));  avg_speed = float(np.mean([traci.vehicle.getSpeed(v) for v in veh_ids]))
```

- `avg_timeLoss(t)` = 当前在网车辆 `traci.vehicle.getTimeLoss` 的均值，**每 100 步（=10 s）记录一次**（demo_1/demo_3/attentionlight；`colight_core.py` 现存版本写的是 `LOG_INTERVAL = 1000`，与历史 `results/d` 中 100 步间隔不一致 → 版本差异，需注意）；
- `avg_speed(t)` = 当前在网车辆瞬时速度均值；
- `vehicle_count(t)` = 当前在网车辆数。

**重要口径差异**：`traci.vehicle.getTimeLoss` 返回的是 SUMO 定义的**累积时间损失**（截至当前时刻），而论文式 (2)/(3) 写的是 `T_actual − d_i/v_max`（行程级）。二者相关但不等价。因此：

| 用途 | 指标 | 说明 |
|---|---|---|
| 与历史图件对齐 | 上述 `getTimeLoss` 逐 step 均值的 run 内平均 | 与历史 CSV 同构，可直接对照 |
| 更稳健的主指标（建议新增） | tripinfo 级平均时间损失 | 无"活跃车辆集合"偏差；须在 manifest 声明为**新增口径** |
| 速度 | 稳态窗口（如 400–1000 s）内的 `avg_speed` 均值 | 避免冷启动偏置 |
| 安全 | 最小车头时距 < 1.5 m 的次数、急刹次数、SUMO 碰撞消息数 | 三项分别记录，不合并 |

**禁止**：把历史 CSV 的逐 step 均值与新建 tripinfo 均值直接放进同一张图而不说明口径。


### 3.4 统计与绘图口径（沿用 AGENTS.md 第 6 节）

- 每配置 30 个 run → 箱线图（中位数/四分位），不预先平均掉分布。
- 历史 DSIP **不得**与新 baseline 混在同一箱线图里（无逐 run 数据或来源未确认）。

---

## 4. 缺失车流与随机种子的处理选项

### 4.1 车流（三选一）

| 方案 | 做法 | 优点 | 缺点 |
|---|---|---|---|
| **A（推荐）** | 按 `auto1.py: EXPERIMENT_PARAMS` 生成 15 个**静态** `rou.xml`（3 车道 × 5 档），脚本入库、文件入库、manifest 标注 `RECONSTRUCTED_FROM_EXPERIMENT_PARAMS` | 与历史需求生成规则完全一致；可复现、可审查 | 需作者授权；需说明"当年不存在这些文件" |
| B | 按 Table I + 式 (1) 重新生成（若作者确认 Table I 才是目标密度） | 与论文表述自洽 | 与历史实际运行差约 10 倍，**不能**与历史结果并图 |
| C | 只用现存 1 个车流文件（3 车道/MaxD） | 零新增 | 基线仅有 1 个密度点，"密度-性能"曲线不成立 |

### 4.2 随机种子（三选一）

| 方案 | 做法 | 说明 |
|---|---|---|
| **A（推荐）** | 显式列出 30 个种子（如 `81890..81919`），写入 `experiments/seeds.json`；每个 (方法, 配置) 用**同一列表** | 与历史起点一致；强调"同 seed ≠ 同交通实现" |
| B | 按历史脚本的全局递增规则推导每个 (配置, run) 的 seed | 最贴近历史，但需要重建循环顺序表，且各方法顺序不同 |
| C | 用固定列表 + 明确说明非配对 | 最保守，避免误用配对统计 |

### 4.3 不建议的做法

- 不建议从 `tl*.png`/`as*.png` 反推数值。
- 不建议把 `results/c`（合成）当作任何基线。
- 不建议在未确认口径前把新 baseline 与历史 DSIP 曲线放进同一张图。

---

## 5. 建议的下一步（一条，最小）

> 请作者就 §0 的 4 个问题给出裁定；其中最关键的是 **Table I 密度口径** 与 **是否授权按 `EXPERIMENT_PARAMS` 生成静态车流**。
> 得到裁定后，下一轮只做一件事：**按 §1 实现并跑通 FCFS 的单 seed 最小测试**。
