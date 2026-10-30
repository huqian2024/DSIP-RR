# AIM baseline 复现可行性（Phase 2 / Task B）

- 审计日期：2026-10-30
- 调查对象：`https://github.com/spartalab/aim`（AIM4/AIM5 分支版本）与 `https://github.com/KULeuven-COSIC/CCAM-DI`
- 调查方式：GitHub REST API + raw 文件只读读取（沙箱直连 `git clone` 被网络阻断，见 §0）
- 未安装任何依赖、未修改上游源码、未训练模型、未运行实验。
- 本机可用的运行时（只读探测）：OpenJDK 11.0.32、Maven 3.6.3、Python 3.10.12（系统）、conda `mmd`（Python 3.8.20）；`ray` / `gymnasium` 在任何环境中均**未安装**。

---

## 0. 调查前提与本轮限制

| 事项 | 结果 |
|---|---|
| `git clone`（两仓库，--depth 1） | **失败**：`Failed to connect to github.com port 443 ... Connection timed out`（超时 ~134 s） |
| 替代途径 | 通过代理读取 GitHub REST API（`/contents`、`/commits`、`/git/trees`）与 `raw.githubusercontent.com` 单文件 |
| 本地克隆 | **未建立**，`third_party/` 仍为空目录（仅有 `.gitkeep`），固定信息记录在 `third_party/README.md` |
| commit 固定 | 已取得两仓库 HEAD SHA（见下），可用于将来复现时 `git checkout <sha>` |

因此：本轮结论基于**源码/文档的静态阅读**，属"可实现性评估"，不等于"已验证可运行"。

---

## 1. `spartalab/aim`（AIM4 / FCFS 参考实现）

### 1.1 仓库固定信息

| 项目 | 值 |
|---|---|
| URL | https://github.com/spartalab/aim |
| 默认分支 | `master` |
| HEAD commit | `2c7a61d9b10049307570aba15f842221e97cc529`（2019-08-30，"Updated Traffic signal phase file reference and deleted target files"） |
| 许可 | GitHub 元数据标注 **GPL-3.0**；但 `aim4/*.java` 文件头是 UT Austin 的 **BSD 三条款式**声明，仓库另含 `COPYRIGHT.txt`（~35 KB）。**许可口径存在不一致，复用前必须确认** |
| 语言/构建 | Java + Maven（`pom.xml`、`Makefile`）；README 要求 Java ≥ 6、Maven ≥ 2.2.1 |
| 规模 | 36 commits；包结构 `aim4/{Main,config,driver,gui,im,noise,sim,util,vehicle}` + `6phases/` + `expr/`(SemiAIM/AIM5) + `plotting/` |

### 1.2 它实际实现的是什么

AIM4 是 **Dresner & Stone 的自主交叉口管理（AIM）协议**在 UT Austin 的完整 Java 仿真实现，**自带车辆动力学与道路模型，不是 SUMO**：

- `aim4/im/v2i/`：V2I 协议的结合管理器（`V2IManager`）、预留网格（`reservation/ReservationGrid`）、准入控制区 ACZ（`AczManager`）。
- `aim4/im/v2i/RequestHandler/`：请求处理器，**`FCFSRequestHandler.java` 就是 FCFS 策略本体**（已读全文，见下）。
- `aim4/im/v2i/policy/`：`BasePolicy`（预留提交/确认/取消/离场）、`AllStopPolicy`、`TimeoutPolicy`。
- 其他处理器：`AllStopRequestHandler`、`TrafficSignalRequestHandler`、`Approx4PhasesTrafficSignalRequestHandler`、`ApproxNPhasesSignalFcfsRequestHandler`（信号+预留混合）、`GoStraightRequestHandler`。
- `expr/`：SemiAIM / AIM5（混合交通 + 信号），对应 Au & Stone 的 TRB 论文。
- `fcfs-signal.condor` + `src/main/java/baseline.csv` + `plotting/eff_spawn_result/*.csv`：作者自己的批处理与绘图产物。

`FCFSRequestHandler.processRequestMsg()` 的关键逻辑（逐字要点）：

```java
if (basePolicy.hasReservation(vin))  -> Reject(CONFIRMED_ANOTHER_REQUEST)
ProposalFilterResult r = BasePolicy.standardProposalsFilter(msg.getProposals(), basePolicy.getCurrentTime());
ReserveParam p = basePolicy.findReserveParam(msg, r.getProposals());
if (p != null) basePolicy.sendComfirmMsg(msg.getRequestId(), p);
else           basePolicy.sendRejectMsg(vin, msg.getRequestId(), Reject.Reason.NO_CLEAR_PATH);
```

即：**先到先服务不是靠排序队列，而是靠"消息到达即处理"的时序 + 时空预留网格的可行性判定**；`BasePolicy` 中 `EARLY_ERROR = LATE_ERROR = 0.01 s`，车辆必须按确认的时间窗到达（早/晚 0.01 s 以内）。

### 1.3 是否适合作为论文的 AIM baseline

- **算法层面：适合，且是最合适的第一顺位**。它给出明确、可引用的 FCFS 预留规则（Dresner & Stone 2008 / AIM4），与审稿人要求的"FCFS reservation-based AIM"完全对应。
- **实现层面：不能直接当 SUMO baseline 跑**。AIM4 有自己的仿真内核（`aim4/sim`、`aim4/vehicle`、`aim4/driver`）、自己的地图与车辆动力学；与 SUMO 无接口。要放进本论文的 SUMO 场景，只能**按协议重写**（与 AGENTS.md "Independent SUMO interfaces / adapters" 一致）。
- **许可风险**：GPL-3.0（元数据）意味着**直接复制 AIM4 代码进本仓库会带来传染性许可义务**。建议：只引用协议与论文，独立实现，不复制 Java 源码。

### 1.4 运行条件与最小可运行测试

| 项目 | 需求 |
|---|---|
| 运行时 | JDK（≥6 语法，本机 JDK 11 可编译但旧 `maven-compiler-plugin` 的 source/target 1.5/1.6 会被 JDK 11 拒绝，需命令行覆盖或调整 pom） |
| 构建 | `mvn -Dmaven.test.skip=true assembly:assembly` → `target/AIM4-1.0-SNAPSHOT-jar-with-dependencies.jar` |
| 运行 | `java -jar <jar>`（GUI）或 `java -cp <jar> <MainClass>` |
| 数据 | 无外部数据/权重；地图在代码中构造 |
| 依赖安装 | Maven 首次构建需联网拉取依赖（本机 Maven 3.6.3 已装，但仓库网络受限，**可能卡在依赖下载**） |

对**本论文**而言"最小可运行测试"不是跑 AIM4 的 App，而是：

> 在我们自己的模块里实现 FCFS 预留（单进口队列 + 冲突区占用判定），用 `cross3.net.xml` + 单 seed、1000 s、一个密度档跑通，并输出与历史 CSV 同构的指标列（`step, avg_timeLoss, avg_speed, vehicle_count`）。

### 1.5 与 SUMO 1.12 + 现有路网对接的要点

1. 冲突区建模：用 `net.xml` 的 `:center_*` 内部车道 + `junction` 的 `request/foes` 位串来构造"占用集合"，比手工画多边形更可追溯（`tls*.net.xml` 里已有 foes 定义，`cross*.net.xml` 没有 → 需由 `netconvert` 的连接关系推导，属离线分析，不修改文件）。
2. 预留粒度：AIM4 是"时空网格 + 到达时间窗"；SUMO 里只能通过 `traci.vehicle.setSpeed/setAcceleration` 或 `slowDown` 让车辆按许可时间通过 → **控制手段不同**，必须在论文中声明这是"FCFS 协议在 SUMO 中的实现"，而非 AIM4 原始执行器。
3. ACZ 概念缺失：SUMO 没有"准入控制区"，需自定义（例如以进口边距停车线 X 米为界），该阈值会显著影响结果 → 必须作为参数记录。
4. 现有 0.1 s 步长与 1000 s 时长可直接复用；但 **密度口径（§5 of scenario-provenance）未定**前，baseline 的需求量无法与历史结果对齐。

### 1.6 哪些适配会改变算法原本的假设

| 适配 | 是否改变行为 |
|---|---|
| 用 SUMO 的跟驰模型替代 AIM4 的 2D 车辆动力学 | **是**（横向运动、转向轨迹、制动能力不同） |
| 用 `setSpeed/setAcceleration` 近似"按时刻到达" | **是**（无法保证 0.01 s 级时间窗） |
| 用进口边距离定义 ACZ | **是**（影响请求时刻与队列长度） |
| 忽略 AIM4 的 proposal 多候选（到点时间窗）而只用单一目标时间 | **是**（FCFS 的"先到"语义会从"最早到达提议"退化为"最早进入队列"） |
| 保留"到达即处理、无重新排序"的时序语义 | 否（这是 FCFS 的核心，必须保留） |

### 1.7 最可能的阻塞

1. 语义保真：SUMO 无法复现 AIM4 的时空预留 + 精确到点，任何实现都是"协议级近似"，需要在论文中说明。
2. 许可：GPL/BSD 口径不清，不能复制源码。
3. 网络：Maven 依赖下载与 pip 安装都可能受阻（本机直连 GitHub 已失败）。
4. 密度口径未定 → 即使跑通，也不能与历史结果比较。

---

## 2. `KULeuven-COSIC/CCAM-DI`

### 2.1 仓库固定信息

| 项目 | 值 |
|---|---|
| URL | https://github.com/KULeuven-COSIC/CCAM-DI |
| 默认分支 | `main` |
| HEAD commit | `c781a644f1df9315a804699296bf3950217886e9`（2026-04-29，"Enhance README with project details and structure"） |
| 许可 | **MIT**（仓库 `LICENSE`，1074 B） |
| 语言/依赖 | Python 3.10.12；`gymnasium==0.28.1`、`ray[rllib]==2.9.3`、`pandas==2.0.0`、`numpy==1.23.5`、`keyboard==0.13.5`、`tensorboardX`、`torch==2.0.1` |
| 文件规模 | 13 commits；`env/`（`env.py` 121 KB + SUMO 网/路 + `randomTrips.py`）、`functions/`（callbacks、对抗函数）、`config.py`、`run.py` |

### 2.2 它实际实现的是什么

沿街级（vehicle-level）**多智能体强化学习**交叉口控制，在 SUMO 中运行：

- `IntersectionEnv(MultiAgentEnv)`：每个进入交叉口的车辆是一个 RL agent（`TERMINATING_AGENTS=True`，车辆通过或碰撞即终止），4 个方向各一个策略（`policy_N/E/S/W`，`MULTI_POLICY=True`）。
- 算法：`config.ALG` 默认 **`DQN`**（可切 `PPO`，PPO 可选 LSTM），RLlib 训练；`REWARD_VALUES='10_-0.1_-20'`（成功通过/在冲突区内/碰撞）。
- 观测：`rel_coord_with_dest`，只看 **最近 1 辆**（`OBS_SPACE_N_CLOSEST=1`）、范围 20 m；动作过滤（无冲突/无邻近车辆时不给动作）。
- 核心贡献（论文）：观测/动作过滤降低状态空间、加速收敛；扩展研究评估**数据完整性攻击**（伪造位置）下的鲁棒性。

### 2.3 是否适合作为 AIM baseline

- **可以作为"学习型 AIM baseline"**，且与论文已有 RL baseline（MP-Light/CoLight/AttentionLight，都是**信号控制**RL）性质不同：CCAM-DI 是**无信号、车辆级**协调，与 DSIP 同类，因此可比性更强。
- 但它是**学习型**基线，必须连权重一起才公平；仓库**没有发布权重**（见 §2.4），且训练成本高。

### 2.4 权重、配置与示例

| 项目 | 实际状态 |
|---|---|
| `saved_model/` | README 声称有，但仓库 tree 中**不存在该目录**（`LICENSE/README.md/config.py/env/ functions/ requirements.txt/run.py` 之外没有其他顶层项）→ **未发布预训练权重** |
| 训练需求 | `TRAIN_TOTAL_TIMESTEPS = 1_000_000`，`config.py` 注释 "HPC run time: 1M steps ~ 10h"；`TRAIN=False` 时 `run.py` 直接从 `SAVED_MODEL_PATH="saved_model"` 加载 → 缺权重则无法直接评测 |
| 示例配置 | `config.py` 即唯一配置（含大量 `*_LIST` 网格搜索项，用于 Tune） |
| 示例场景 | `env/8_8_network.net.xml`（8×8 网格路网）+ `8_8_routes*.rou.xml` + `randomTrips.py`；`8_8_conf*.sumocfg` |

### 2.5 与 SUMO 1.12 + 现有路网/车流的对接

| 维度 | CCAM-DI 现状 | 与 DSIP 场景的差距 |
|---|---|---|
| SUMO 版本 | 未在 `requirements.txt` 固定；`env.py` 用 `sys.path.append($SUMO_HOME/tools)` 后 `import traci`（依赖 SUMO 自带 traci） | 与我们的 SUMO 1.12 可能兼容，但**未声明版本**，需实测；且该 `sys.path.append` 写法在装有 pip traci 的环境里会被覆盖（风险） |
| 路网 | `8_8_network.net.xml`，四个进口的边 id 为 `1/2/3/4` | 我们的 `cross2/3/4` 边 id 是 `north2center/east2center/...` → 需适配层（`start_edge`/`dest_edge` 映射、坐标窗口） |
| 坐标窗口 | 硬编码 `x∈[-30,30]`、`y∈[20,80]`，观测/奖励依赖该 playground | 我们的交叉口在 (100,100)、进口边 ~83–90 m → 必须重标定，否则观测与奖励失真 |
| 车辆控制 | 直接给加速度，`ACCELERATION=20 m/s²`，`MAX_SPEED=35 m/s` | 我们的 `vType` 是 `accel=1.0`、`maxSpeed=13.9`、IDM → 动力学完全不同 |
| 需求注入 | `SUMO_TRAFFIC_INSERTATION_PERIOD=0.8 s`（≈1.25 veh/s）、`SUMO_RANDOM_ROUTE=True` 用 `randomTrips` 随机生成 | 我们用固定 12 条 flow + `normal(ΔT,1)`，且密度口径未定（见另文 §5） |
| 时长 | `EPISODE_LENGTH=5100` 步（注释称 1000/step-length，但 5100×0.1 s ≈ 510 s，与注释不符，需实测确认） | 我们 1000 s；需统一 |
| 碰撞处理 | `RESTART_EPISODE_ON_COLLISION=True`（碰撞即重开 episode） | DSIP 是继续运行并统计；协议不同，会显著影响指标 |

### 2.6 哪些适配会改变算法原本的假设

1. 改坐标窗口与边 id → 观测分布整体变化，**未重训**的权重会失效；文件又说"未发布权重"，所以必须重训。
2. 改 `ACCELERATION`/`MAX_SPEED` → 动作语义改变（同一 action 在不同加速度上限下行为不同）。
3. 改需求注入方式（period → flow/interval）→ 到达过程不同，agent 密度不同。
4. 改 episode 长度与碰撞重开规则 → 训练/评测条件改变。

结论：**这不是"适配"，而是"在新场景上重训"**；任何结果都必须标注 "CCAM-DI (retrained on DSIP routes)"，不能写成"复现原论文结果"。

### 2.7 最小可行验证（不放权重也能做的第一步）

1. 新建独立 conda 环境（Python 3.10 + ray 2.9.3 + torch 2.0.1 + SUMO 兼容版本）——**需作者授权安装**。
2. 跑通"环境可实例化"：`IntersectionEnv(env_config)` + 1 个 episode，随机动作（`action=1` 恒速），确认 SUMO 能启动、观测/动作维度正确。
3. 用其自带 `8_8` 场景训练一个极小步数（如 10k steps）验证训练管线，不做性能结论。
4. 之后再决定是否值得投入 1M steps 重训。

### 2.8 最可能的阻塞

1. **无预训练权重** + 训练 1M steps（作者注 ~10 h/配置）——若需 3 车道 × 5 密度 × 30 seed 的完整网格，成本不可接受。
2. Python 3.10 + ray 2.9.3 与本机 `mmd`（3.8/torch 2.0.0）冲突 → 必须新建环境（本轮禁止安装）。
3. `env.py` 121 KB、强耦合自有路网与坐标窗口 → 适配工作量大。
4. SUMO 版本未声明，1.12 与较新语法（`traci` 订阅、`getSubscriptionResults` 等）可能不兼容。
5. 需求口径不一致会让"CCAM-DI vs DSIP"的比较失去意义。

---

## 3. 两个项目的对比与建议

| 维度 | AIM4 / FCFS | CCAM-DI |
|---|---|---|
| 与 DSIP 的同质性 | 同属"无信号、集中协调" → 可比性强 | 同属"无信号、车辆级协调"，但学习型 |
| 是否有可直接运行的 SUMO 版本 | ❌（自带仿真器） | ✅（原生 SUMO） |
| 是否需要训练/权重 | 不需要（确定性协议） | **需要**，且权重未发布 |
| 实现成本（到"能跑出 1 个 seed"） | 低-中（自己写 FCFS + 冲突区判定，约数百行） | 高（新环境 + 适配 + 重训） |
| 许可风险 | GPL/BSD 口径不清 → 只引用不复制 | MIT → 可复用代码 |
| 审稿人期待 | 明确要求 FCFS（Dresner–Stone） | AGENTS 列为第二基线 |

**建议顺序：先 FCFS，后 CCAM-DI。** 理由：

1. 审稿意见明确点名的就是 FCFS reservation-based AIM；先做它可以直接回应意见。
2. FCFS 是确定性协议，不需要训练/权重，可复现性最强，也最容易在修订说明中解释"我们做了什么"。
3. FCFS 实现过程会顺带把**冲突区建模、ACZ 定义、指标管线、seed 管理**四件事做扎实——这些正是 CCAM-DI 适配的前置条件。
4. CCAM-DI 的成本集中在训练与坐标/拓扑适配，且权缺失；在 FCFS 与统一输入口径确定前启动，容易白做。

---

## 4. 八个问题的直接回答

1. **实现了什么算法**：AIM4 = Dresner–Stone 的 V2I 预留式 AIM（含 `FCFSRequestHandler`、信号/AIM5 变体），自带 Java 仿真器；CCAM-DI = RLlib 的 PPO/DQN 车辆级 MARL，在 SUMO 中运行，含观测/动作过滤与对抗鲁棒性研究。
2. **语言/依赖/最低条件**：AIM4 用 Java ≥6 + Maven ≥2.2.1（本机 JDK 11 + Maven 3.6.3 具备，需覆盖旧 compiler 级别）；CCAM-DI 用 Python 3.10.12 + ray 2.9.3 + gymnasium 0.28.1 + torch 2.0.1（本机**均未安装**）。
3. **是否有权重/配置/示例**：AIM4 无外部数据、无权重（地图在代码里）；CCAM-DI 有 `config.py` 与 `8_8` 示例场景，但**`saved_model/` 未发布**。
4. **如何与 SUMO 1.12 + 现有路网对接**：AIM4 无法"对接"，只能按其协议在我们自己的 TraCI 模块中重写（用 `net.xml` 的 internal lane / `request`-`foes` 构造冲突区）；CCAM-DI 原生 SUMO，但需适配边 id、坐标窗口、加速度/限速、需求注入，且其 `sys.path.append($SUMO_HOME/tools)` 的 traci 加载方式需改。
5. **哪些适配改变原假设**：AIM4 —— 用 SUMO 跟驰模型替代 2D 动力学、用 `setSpeed` 近似时间窗、自定义 ACZ、退化 proposal 选择；CCAM-DI —— 坐标/边 id、加速度与限速、需求注入、episode 长度与碰撞重开。
6. **最小可运行测试**：AIM4 → 写 1 个进口的 FCFS 冲突区判定 + 单 seed 1000 s 跑通并出指标 CSV；CCAM-DI → 新环境 + `IntersectionEnv` 随机动作跑 1 个 episode（不需权重）。
7. **最可能的阻塞**：AIM4 = 语义保真 + GPL/BSD 许可 + 依赖下载；CCAM-DI = 缺权重/训练成本 + 新环境 + 强耦合的坐标与拓扑 + SUMO 版本未声明。
8. **先做哪个**：**FCFS**（见 §3）。

---

## 5. 可比性提示（写给将来的结果表）

| 维度 | DSIP（历史） | AIM4/FCFS（新实现） | CCAM-DI（改造后） |
|---|---|---|---|
| 控制对象 | 每 0.4 s 重规划的轨迹 | 每请求一次的预留 + 时间窗 | 每 0.1 s 一次加速度 |
| 车辆模型 | SUMO IDM（accel 1.0） | SUMO IDM（同上） | 需改 accel=20 或重训 |
| 优化目标 | 多智能体轨迹可行性 | 冲突消解（无效率优化） | 奖励函数（通过/碰撞） |
| 是否需要训练 | 是（已丢失） | 否 | 是（需重训） |
| 需求口径 | 待作者确认（见另文 §5） | 必须与 DSIP 一致 | 必须与 DSIP 一致 |

**注意**：不同方法即使使用相同数值 seed，也不代表相同的交通实现（见 `scenario-provenance.md` §6）；跨方法比较应报告"同一 seed 集合、各自独立实现"的事实，而不是当作配对样本做配对检验。

