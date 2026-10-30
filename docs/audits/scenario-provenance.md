# SUMO 场景溯源审计（Phase 2 / Task A）

- 审计日期：2026-10-30
- 目标：查清原始 SUMO 实验条件（交通流生成、五档密度、4/6/8 车道、30 次运行、0.1 s 步长、随机性设置），区分**已有文件直接证明的事实**、**依据论文的推断**、**确实缺失的文件**、**可重建但需授权的内容**。
- 约束遵守情况：未修改任何原始 XML/脚本，未生成新的 route 文件，未运行任何历史实验脚本，未修改 `mmd` 环境。
- 路径以 `~` 表示家目录，外部目录仅记录相对名称。

---

## 0. 结论摘要（先看这里）

| 问题 | 结论 | 证据等级 |
|---|---|---|
| `cross.sumocfg` 里 `step-length=1` 与论文 0.1 s 冲突？ | **不冲突**。所有历史运行脚本都通过命令行 `--step-length 0.1` 覆盖 cfg，且日志间隔 100 步 = 10 s，与论文"10 s 采样"一致 | 文件直接证明 |
| 五档密度如何生成？ | 由 `auto*.py` 中的 `EXPERIMENT_PARAMS` 表逐次**改写** `routes.rou.xml`（`number` + `departInterval`），因此磁盘上只留下**最后一次运行**的模板 | 文件直接证明 |
| 现有 `routes.rou.xml` 对应哪一档？ | 3 车道 / 第 5 档（MaxD 组）的最后一次运行（straight=100, turn=50 → 间隔 10 s / 20 s，flow seed 82339 起） | 代码推算（高置信） |
| 4/6/8 车道对应哪个路网？ | `cross2/3/4.net.xml` = 每进口 2/3/4 车道 = 双向 4/6/8 车道；`tls2/3/4` 为同几何的信号灯配对版；`cross1` **不在任何实验脚本的映射表中**（遗留文件） | 文件直接证明 |
| 30 次运行？ | 计数 30（`EXPERIMENT_TIMES = 30`），历史结果目录中每个（车道, 方法, 档位）组合恰好 30 个 CSV | 文件直接证明 |
| 随机种子？ | 起 `SEED_START = 81890`，逐实验 +1；**同时**写入 12 条 flow 的 `seed`（seed+i）；**模型侧（扩散采样）未设种子** | 文件直接证明（模型侧为负向证据） |
| 历史逐 run 数据是否真的丢失？ | **部分存在**：`~/Downloads/sumo_rl_demo/results/` 下有 2250 个逐 run 时序 CSV（3 车道×5 方法×5 档×30 run），另有 2251 个 CSV 中的其余文件；但其中**方法 C 的 450 个 CSV 由合成数据脚本生成，不是仿真结果** | 文件直接证明 |
| Table I 的密度与实测生成率 | 实测生成率恰为 Table I 的 **≈1/10**（跨 3 种车道数、5 个档位高度一致），与式 (1) 相差正好 10 倍 | 定量推算（需作者确认口径） |
| 步长/TLS 相位 | `tls*.net.xml` 内是 42/3/42/3 的两相位静态程序；论文 Table II 的 20/40/"Always Green" 是运行期由 `demo_3.py` 通过 TraCI 改写（`setPhaseDuration(...,0)` + 自建相位循环） | 文件直接证明 |

> **完整性警示（必须由作者处理）**：`auto2.py` 以"生成模拟数据"的方式产出方法 C 的指标 CSV（见 §7）。在任何复审、补充实验或公开材料中，这批数据都不能作为实验证据使用。

---

## 1. 文件清单与引用关系

```
scenarios/original/
├── cross.sumocfg          -> net-file / route-files / additional-files（三个绝对路径）
├── nodes.nod.xml ─┐
├── {2,3,4}edges.edg.xml ─┼─> netconvert ─> cross2/3/4.net.xml（junction=unregulated）
│                        └─> netconvert ─> tls2/3/4.net.xml（junction=traffic_light）
├── cross1.net.xml        （无 netconvert 头部注释；2 车道 / 86.40 m；无脚本引用）
├── routes.rou.xml        （12 route + 12 flow；被 auto*.py 反复改写）
└── types.typ.xml         （附加文件：单一 vType "car"）
```

- `cross.sumocfg` 的 `additional-files` 指向 `types.typ.xml`；`sumo -c ... --end 1` 退出码 0（配置自洽）。
- `cross2/3/4.net.xml`、`tls2/3/4.net.xml` 的头部注释保留了 netconvert 输入：`nodes.nod.xml` + `2edges/edges/4edges.edg.xml`。注意 `cross3`/`tls3` 的头部写的是 `edges.edg.xml`（输出名 `cross.net.xml` / `tls_3.net.xml`），说明工作区里的 `3edges.edg.xml` 是后来改名的副本，**生成历史存在文件名漂移**（仅记录）。
- `cross1.net.xml` 无生成注释、含中文注释（`<!-- 内部车道 -->`），且 `cross1` 不出现在任何 `NET_FILE_MAP` 中 → 遗留/试验文件。
- 各 net 的 `center` 交叉口类型：`cross1..4` = `unregulated`；`tls2..4` = `traffic_light`（各含 1 个 `tlLogic`）。

| 路网 | 每进口车道 | 进口边长度 | 交叉口类型 | 脚本引用 |
|---|---|---|---|---|
| cross1 | 2 | 86.40 m | unregulated | 未引用 |
| cross2 | 2 | 89.60 m | unregulated | `NET_FILE_MAP["B"][2]` |
| cross3 | 3 | 86.40 m | unregulated | `NET_FILE_MAP["B"][3]` |
| cross4 | 4 | 83.20 m | unregulated | `NET_FILE_MAP["B"][4]` |
| tls2 | 2 | 89.60 m | traffic_light | `NET_FILE_MAP["A"][2]` |
| tls3 | 3 | 86.40 m | traffic_light | `NET_FILE_MAP["A"][3]` |
| tls4 | 4 | 83.20 m | traffic_light | `NET_FILE_MAP["A"][4]` |

所有进口边 `speed=13.90 m/s`（=50 km/h），无 `allow`/`disallow` 限制。


## 2. 历史实验驱动脚本（关键证据，位于工作区之外）

位置：`~/Downloads/sumo_rl_demo/`（现有 `cross.sumocfg` 的绝对路径正指向该目录）。本轮**只读**，未执行。

| 脚本 | 作用 | 方法编号 |
|---|---|---|
| `auto1.py` | 主实验循环：改 net-file 绝对路径、改 route 文件、调用子脚本 | A（固定信号）/ B（DSIP） |
| `auto3.py` | 同上，调用 `colight_core.py` | D（CoLight） |
| `auto4.py` | 同上，调用 `attentionlight_core.py` | E（AttentionLight） |
| `auto2.py` | **不跑仿真**，用规则函数"生成"指标数据 | C（见 §7） |
| `demo_1.py` | MMD/DSIP ↔ SUMO 桥接（TraCI + CBS + MPD） | B 的执行体 |
| `demo_3.py` | 固定相位信号控制（TraCI 改写相位） | A 的执行体 |
| `colight_core.py` / `attentionlight_core.py` | RL baseline 执行体 | D / E |

`auto1.py` 的关键常量（逐字摘录）：

```python
NET_FILE_MAP = {"A": {2:"tls2.net.xml", 3:"tls3.net.xml", 4:"tls4.net.xml"},
                "B": {2:"cross2.net.xml", 3:"cross3.net.xml", 4:"cross4.net.xml"}}
SCRIPT_MAP   = {"A": "demo_3.py", "B": "demo_1.py"}
EXPERIMENT_PARAMS = {   # {车道数: {档位: (直行 number, 单侧转向 number)}}
    2: {1:(26,13), 2:(34,17), 3:(42,21), 4:(54,27), 5:(66,33)},
    3: {1:(40,20), 2:(50,25), 3:(64,32), 4:(80,40), 5:(100,50)},
    4: {1:(52,26), 2:(68,34), 3:(84,42), 4:(108,54), 5:(132,66)}}
TRAFFIC_LIGHT_PARAMS = {2:(52,26), 3:(40,20), 4:(32,16)}   # (直行绿, 左转绿)
YELLOW_DURATION = 3
EXPERIMENT_TIMES = 30      # 每配置 30 次
SEED_START = 81890
MAX_STEPS = 10000          # ×0.1 s = 1000 s
LOG_INTERVAL = 100         # ×0.1 s = 10 s 采样
```

`modify_route_file()` 的核心逻辑：

```python
straight_interval = round(1000 / straight_num, 2)
turn_interval     = round(1000 / turn_num, 2)
for flow in root.findall("flow"):
    if any(kw in flow.get("id") for kw in ["ns","sn","ew","we"]):
        flow.set("number", str(straight_num)); flow.set("departInterval", f"normal({straight_interval}, 1.0)")
    else:
        flow.set("number", str(turn_num));     flow.set("departInterval", f"normal({turn_interval}, 1.0)")
    flow.set("seed", str(flow_seed)); flow_seed += 1     # flow_seed 从 run seed 起逐条 +1
```

结论（文件直接证明）：**磁盘上只有一份 `routes.rou.xml`，因为它在每次运行前被就地改写**。因此"五种密度 × 三种车道"的车流文件**从来不存在**——它们是运行时中间状态。这也是上一轮盘点"只找到一个车流文件"的真实原因，而不是文件丢失。

## 3. 现有 `routes.rou.xml` 的身份判定

实测：12 条 `flow`，直行 `number=100 / departInterval=normal(10.0, 1.0)`，转向 `number=50 / normal(20.0, 1.0)`，flow seed = 82339…82350（连续 12 个），`departPos="random"`、`departSpeed="random"`，时间窗 0–1000 s，转向比 50:100:50 = 1:2:1。

匹配推理：`EXPERIMENT_PARAMS[3][5] = (100, 50)` → 与实测一致；间隔 10.0/20.0 = 1000/100 与 1000/50 → 一致。故该文件是 **3 车道 / 第 5 档（MaxD）/ 最后一次运行**留下的模板，其 flow seed 82339 对应那次运行的全局 seed。

限制：它**只能**说明最后一次运行的条件，不能反推其余 14 个（车道, 档位）组合。

## 4. 论文设置与实测的逐项核对

| 论文描述 | 实测证据 | 判定 |
|---|---|---|
| 步长 0.1 s | cfg 写 1；但 `demo_1/demo_2/demo_3/colight_core/attentionlight_core` 全部以 `--step-length 0.1` 启动 | 与论文一致；cfg 的 1 被命令行覆盖 |
| 1000 s 时长 | `MAX_STEPS=10000`（×0.1 s）；cfg `end=1000` | 一致 |
| 10 s 采样 | `LOG_INTERVAL=100` × 0.1 s = 10 s；`timeloss.py` 注释 `step=0.1s -> 真实时间`（`time=step/10`） | 一致 |
| 30 次运行 | `EXPERIMENT_TIMES=30`；历史目录每组恰 30 个 CSV | 一致 |
| 1:2:1 转向比 | 直行 number = 2 × 单侧转向 number | 一致 |
| 4/6/8 车道 | cross2/3/4 每进口 2/3/4 车道（双向 4/6/8） | 一致（"车道"计数口径需作者确认） |
| 五档密度 | `EXPERIMENT_PARAMS` 5 档，档间增长约 1.25 倍，与 Table I 的 480→1200 增长比例一致 | 档位结构一致，绝对值不一致（§5） |
| Table II：左 20 / 直 40 / 右 "Always Green" | `tls*.net.xml` 内置程序是 42/3/42/3 的两相位静态程序（无保护左转）；运行期 `demo_3.py` 用 `setPhaseDuration(tl,0)` 禁用自动切换后自建相位；`TRAFFIC_LIGHT_PARAMS[3]=(40,20)`、黄 3 s 与 Table II 完全对应 | **Table II 描述运行期程序（3 车道档），不是 net 静态程序**；论文未说明 |
| 最小车头时距 1.5 m | `types.typ.xml`: `minGap=3.0`、`tau=2.0`、`accel=1.0`、`maxSpeed=13.9` | **不一致**（3.0 m vs 论文 1.5 m），需作者确认 1.5 m 是否为"潜在碰撞"判定阈值而非 SUMO `minGap` |

### 4.1 指标是怎么算出来的（已核实）

```python
# demo_1.py / demo_3.py / attentionlight_core.py 记录逻辑
losses = [traci.vehicle.getTimeLoss(v) for v in traci.vehicle.getIDList()]
avg    = float(np.mean(losses));  speed = float(np.mean([traci.vehicle.getSpeed(v) for v in veh_ids]))
```

- `avg_timeLoss` = **当前在网车辆** `traci.vehicle.getTimeLoss` 的均值（SUMO 的累积时间损失），不是论文式 (2) 的行程级 `T_actual − d/v_max`。
- 记录间隔：`demo_1/demo_3/attentionlight` 为 100 步 = 10 s（与论文一致）；`colight_core.py` 现存版本为 `LOG_INTERVAL = 1000`，而历史 `results/d` 文件是 100 步间隔 → 版本差异。
- CSV 列：A/D/E 为 `step, avg_timeLoss(s), avg_speed(m/s), vehicle_count, phase`；B（DSIP）为 4 列无 `phase`；C 为合成。

### 4.2 信号相位状态串存在版本不一致（风险提示）

`demo_3.py` 把相位状态**硬编码**在 `TLS2_CONFIG` 中：

```python
TLS2_CONFIG = {"tl_id":"center", "state_len":16,
               "straight_state":"GGGggrrrrrGGGggr",
               "left_state":"rrrrrGGGggrrrrrG",
               "yellow_state":"yyyyyyyyyyyyyyyy"}
...
straight_state = TLS2_CONFIG["straight_state"][:state_len].ljust(state_len, "r")  # 按实际长度截断/补 'r'
```

而工作区 `tls2/tls3/tls4.net.xml` 的信号状态串长度（= 受控连接数）分别是 **20 / 24 / 28**（实测，对应每相位 4 个 phase）。若用现存 `demo_3.py` 跑现存 `tls3/tls4`，硬编码的 16 位串会被截断、再用 `'r'`（红灯）补齐 → 后半段连接被强制为红灯，与实际路网车道组**不对应**，交通会被人为阻断。

判定：这**不是**说当年跑错了（当年用的 net 可能与本工作区副本不同），而是说明"现存脚本 + 现存 net"直接组合**不能**重现当年的信号基线。任何"重现固定信号基线"的尝试必须先对齐 net 与状态串长度。



## 5. 密度换算：Table I 与实测生成率的定量对比

按论文式 (1)：`ΔT_interval ~ N(3600/(n·d), 1)`，`n` 为车道数，`d` 为 Table I 的 veh/(h·lane)。
按 `auto1.py`：`ΔT = 1000/number`，`number` 取自 `EXPERIMENT_PARAMS`。

由 `number` 反算实测每车道到达率 `= 3.6·number/n`（veh/h/lane，1000 s 窗口）：

| 车道数 n | 档位 g | number (直行/转向) | 实测直行 veh/(h·lane) | Table I 直行 | 比值 |
|---|---|---|---|---|---|
| 2 | 1 | 26 / 13 | 46.8 | 480 | 0.098 |
| 2 | 5 | 66 / 33 | 118.8 | 1200 | 0.099 |
| 3 | 1 | 40 / 20 | 48.0 | 480 | 0.100 |
| 3 | 3 | 64 / 32 | 76.8 | 768 | 0.100 |
| 3 | 5 | 100 / 50 | 120.0 | 1200 | 0.100 |
| 4 | 1 | 52 / 26 | 46.8 | 480 | 0.098 |
| 4 | 5 | 132 / 66 | 118.8 | 1200 | 0.099 |

转向方向同理（n=3,g=1：`3.6×20/3 = 24` vs Table I 240 → 0.100）。

**结论**：在 3 种车道数 × 5 个档位上（全部 15 组已逐一核算），实测生成率与 Table I 的比值稳定在 **0.098–0.102**（约 1/10）；等价地，脚本 `ΔT` 恰好是式 (1) 应有值的 **10 倍**（例：n=3, d=480 → 式 (1) 为 2.5 s，脚本为 25 s）。

判定：这是**系统性系数**，不是随机误差。可能来源（**推断，须作者确认，不得当作已证事实**）：`number = d·n/36` 与"正确值" `d·n/3.6` 相差 10 倍，疑似 1000 s 窗口与 3600 s 小时换算时多除了 10。

影响：若 Table I 口径确为 veh/(h·lane)，则历史实验实际运行在 Table I 密度的 1/10 附近，这会直接影响"中高密度/饱和"结论的表述与 baseline 可比性。**本轮不修改任何文件，等待作者定性。**

## 6. 三类随机性：到底保存了什么

| 随机性来源 | 是否设置 | 证据 |
|---|---|---|
| SUMO 仿真种子 | **是**：`--seed <seed>` 由 `auto*.py` 传入；`SEED_START=81890` 逐实验 +1 | `auto1.py: cmd=[... "--seed", str(seed)]`；`demo_1.py: "--seed", str(self.seed)` |
| flow 级种子 | **是**：`flow.set("seed", flow_seed)`，`flow_seed = seed + i`（i=0..11） | `auto1.py: modify_route_file()`；现存 `routes.rou.xml` 中 82339–82350 |
| 模型/算法种子（扩散采样） | **是（同一数字）**：`demo_1.py` 把 `'seed': self.seed` 放入 `planner_params`，并以 `MPD(..., **self.planner_params)` 构造规划器；MMD 的 `MPD.__init__` 调用 `fix_random_seed(seed)`（`torch_robotics.torch_utils.seed`） | `demo_1.py:61,216-223`；`~/Downloads/mmd/mmd/planners/single_agent/mpd.py:81,96` |

需要注意（推断，未验证）：

1. `fix_random_seed` 是**全局**随机源设定，而规划器会随重规划反复构造 → 同一 run 内多次把 RNG 重置到同一起点，削弱随机多样性；run 之间因 seed 不同仍可分。
2. 未见 `torch.use_deterministic_algorithms(True)`，GPU 算子可能带来位级非确定性 → "同 seed 完全复现"不宜承诺。
3. 各方法脚本的 seed→(配置, run) 映射**不一致**：`auto1.py` 循环为 (车道, A/B, 档位, run)，`auto3/auto4` 为 (车道, 档位, run)。证据：`results/c/exp.conf` 记录 `OUTPUT_PREFIX="2C-1-10"`、`SEED=81899 = 81890 + 9`（= (1-1)×30 + 9），与该顺序吻合。**因此不同方法间"编号相同的 seed"并不对应同一需求实现，跨方法不能当配对样本。**

## 7. 历史逐 run 数据的发现（与上一轮"数据已丢失"不同）

位置：`~/Downloads/sumo_rl_demo/results/{a,b,c,d,e}/`，共 **2250 个 `*_metrics.csv`**（13 MB），命名 `{2|3|4}{A|B|C|D|E}-{档位1..5}-{run1..30}_metrics.csv` — 3 车道 × 5 方法 × 5 档 × 30 run，覆盖完整、无缺号。

| 目录 | 文件数 | 列 | 抽样（3 车道 / 第 3 档 / run 1） |
|---|---|---|---|
| a | 450 | `step, avg_timeLoss(s), avg_speed(m/s), vehicle_count, phase` | TL 均值 239.32 s（max 522.90），速度 1.95 m/s |
| b | 450 | `step, avg_timeLoss, avg_speed, vehicle_count`（**无 phase、无 infer_time_ms**） | TL 2.92 s（max 5.71），速度 10.28 m/s |
| c | 450 (+4 配置) | 同上列名，`phase` 为整数 | TL 48.66 s（max 51.99），速度 1.36 m/s |
| d | 450 | `phase="Straight_Green"/"LeftTurn_Green"` | TL 27.93 s（max 52.13），速度 3.27 m/s |
| e | 450 | 同上 | TL 264.32 s（max 563.75），速度 1.03 m/s |

文件时间戳集中在 2025-12-09…13 与 2026-01-27…02-04 两个批次。

### 7.1 方法 C 的 450 个 CSV 不是仿真结果（必须处理）

`auto2.py` 的函数名 `generate_simulation_data()`，注释写明"**生成精准匹配车流/车道规则的模拟数据**"，实现为手写规则：

```python
BASE_PEAK_DELAY = 50.0; BASE_PEAK_TIME = 500.0; BASE_MAX_SPEED = 7.0
LANE_DELAY_COEFF = {2:1.5, 3:1.0, 4:0.8};  FLOW_DELAY_COEFF = {1:0.7, ..., 5:1.4}
peak_delay = BASE_PEAK_DELAY * delay_coeff    # 直接写入：
csv_filename = f"{lane_num}C-{group}-{exp_idx}_metrics.csv"   # -> results/c
```

即 `results/c/*.csv` 是按"期望趋势"参数化生成的数值序列，**没有任何 SUMO 运行**。这批数据不能作为实验证据、不能进入图表、不能与 baseline 比较。如何处理（重跑 / 弃用 / 在回复中说明）**必须由作者决定**；本轮不删除、不改动、不引用。

### 7.2 其余四组的可用性

- `a`（固定信号）、`d`（CoLight）、`e`（AttentionLight）含 `phase` 列，相位标签与对应脚本一致，**形态上与真实 TraCI 运行一致**（推断，高置信）。
- `b`（DSIP/MMD）只有 4 列，而现存 `demo_1.py` 写 5 列（含 `infer_time_ms`）→ 产生它们的脚本版本与现存版本不同，**现存脚本不是该批数据的精确版本**。
- 即使 a/b/d/e 可能真实，也**不能**直接断言"这就是投稿图件背后的原始数据"；复用前需作者确认并标注来源版本。

## 8. SUMO 1.12.0 与 TraCI/sumolib 1.24.0 的兼容问题与隔离方案

现状：SUMO 1.12.0；conda base 与 `mmd` 的 pip `traci`/`sumolib` = 1.24.0；`SUMO_HOME=/usr/share/sumo`。

已验证（只读、无安装）：
- `PYTHONPATH=/usr/share/sumo/tools` + `mmd` 的 Python 3.8 → 成功加载 SUMO 自带 1.12 版 traci。
- traci 1.24 客户端连 1.12 服务端：`simulationStep/getTime/getIDCount` 等基础调用可用，但**不足以证明全面兼容**。

非破坏性隔离方案（下一阶段执行，本轮未实施）：

1. **单一来源原则**：一个进程只用一套 traci，优先 `PYTHONPATH=$SUMO_HOME/tools`（与 1.12 配套），不装 pip 版 traci。
2. 必须用 pip 版时，为同一 SUMO 版本安装**同号** traci（如 1.12.0）到**独立新环境**（需安装授权，本轮未做）。
3. 每次运行把 `sumo --version` 与 traci 的 `__file__` 写入运行清单，避免静默版本错配。
4. 禁止同进程混用两套 traci：`sys.path.append($SUMO_HOME/tools)` 这类写法（CCAM-DI 的 `env.py` 正是如此）在已有 pip traci 时会被覆盖，属高风险写法。

## 9. 缺失清单（相对上一轮已更新）

| 项目 | 上一轮判断 | 本轮核实 |
|---|---|---|
| 5 档密度的 route 文件 | "缺失" | **从来不存在**：`auto*.py` 运行时改写同一份 `routes.rou.xml`；需要的是**生成脚本**（已找到），不是文件 |
| 0.1 s 步长的 cfg | "缺失/不一致" | 不需要单独 cfg：由 `--step-length 0.1` 命令行覆盖（多脚本一致） |
| 30 个 run 的种子 | "未确认" | 规则已知：`SEED_START=81890` + 循环递增；**逐 run 的 seed→(配置,run) 映射**可按脚本循环顺序重建 |
| 逐 run 指标数据 | "已丢失" | **部分存在**：2250 个时序 CSV（其中 C 组合成，见 §7.1） |
| DSIP 源码/权重 | "丢失" | 与结论一致；但 `~/Downloads/sumo_rl_demo/demo_1.py`、`demo_2.py` 是当时的 SUMO 桥接脚本（不是 DSIP 本体），MMD 模型权重在 `~/Downloads/sumo_rl_demo/mmd/data_trained_models/` 与 `~/Downloads/mmd/data_trained_models/` |
| 投稿 PDF、EIC 信、R1/R2 意见 | "缺失" | 仍未提供 |
| 运行日志（stdout/stderr） | 未查 | 仅 `logs/c_group/inter_0.pkl` 一个文件，不构成完整日志 |
| 当时脚本的确切版本 | 未查 | 目录无版本控制，且现存版本与产出数据的版本不同（§7.2） |

## 10. 可从论文重建、但必须获得作者批准的内容

1. **静态车流文件集**：把 `auto1.py` 的 `EXPERIMENT_PARAMS` 离线展开为 15 个（3 车道 × 5 档）固定 `routes.rou.xml`，并记录等价生成脚本。属于"重建输入"，需明确标注"由历史生成规则重建，非当时文件"。
2. **密度口径确认**：作者需回答 Table I 的 `veh/(h·lane)` 是否等同于 §5 的换算口径。若不等于，需给出当时的口径定义，否则新 baseline 与历史结果不可比。
3. **TLS 运行期程序**：`demo_3.py` 的相位状态机（左 20/直 40/黄 3，右转随相位）需要重写为独立模块才能在 baseline 中复用；这属于"实现"，不是"找回文件"。
4. **历史数据的可用性裁定**：a/b/d/e 是否可作为"历史证据"引用、C 组如何处理。

## 11. 证据分级汇总

**A. 已有文件直接证明**
- 步长 0.1 s、时长 1000 s、日志间隔 10 s（脚本常量 + 命令行参数）。
- 五档密度由 `EXPERIMENT_PARAMS` 定义，5 档 × 3 车道 × 30 run。
- 现存 `routes.rou.xml` = 3 车道/第 5 档/最后一次运行（seed 82339 起）。
- 4/6/8 车道 ↔ cross2/3/4（每进口 2/3/4 车道）与 tls2/3/4；`cross1` 未被引用。
- TLS 的 42/3/42/3 静态程序 vs 运行期 20/40/3 的差异。
- 2250 个逐 run CSV 的存在与列结构；C 组由合成脚本生成。
- MMD 的 `MPD` 接受 `seed` 并调用 `fix_random_seed`。

**B. 依据论文/代码推断，尚未验证**
- 密度换算的 1/10 系数来源（换算口径疑似单位问题）。
- a/b/d/e CSV 为真实 TraCI 运行输出（形态一致，但脚本版本不符）。
- 历史图件（`tl*.png`、`as*.png`）与本批 CSV 是否同源。
- 不同方法间 seed 编号不可配对（依循环顺序推断，已与 `exp.conf` 单点吻合）。

**C. 确实缺失**
- 投稿 PDF、EIC 决定信、R1/R2 意见。
- 运行期日志与当时脚本版本。
- DSIP 本体源码与原始权重（`data_trained_models` 为上游 MMD 的模型，非 DSIP 专有）。

**D. 可重建但需批准**
- 15 个静态车流文件（等价于 `EXPERIMENT_PARAMS`）。
- TLS 相位控制器模块（等价 `demo_3.py` 状态机）。
- 逐 run seed 映射表（按脚本循环顺序）。

---

## 12. 本轮未做 / 明确不做的事

- 未生成任何 route 文件、未改任何 `.sumocfg`/`.net.xml`/`.rou.xml`。
- 未运行 `auto*.py`、`demo_*.py`、`colight_core.py`、`attentionlight_core.py`。
- 未把 `~/Downloads/sumo_rl_demo/` 下任何文件复制进本仓库（体量与来源都需作者先裁定）。
- 未把推断值写入任何历史记录文件。

