# UPSTREAMS — 上游第三方实现登记表

- 建立日期：**2026-11-07**
- 授权范围：作者在 2026-11-07 的本轮任务书中**明确授权**克隆以下两个公开仓库
  （`https://github.com/JingtianYan/PSB-RAL.git`、`https://github.com/theanhhoang/AIM.git`），
  以及为编译它们所必需的系统依赖。该授权**不扩展到**任何其他研究项目。
- 本文件取代 `README.md` 中已作废的"MMD / AIM4 / CCAM-DI"外部路径与 commit 记录
  （见 `AGENTS.md` §0.8）。**MMD/AIM4/CCAM-DI 的旧记录不在本轮授权范围内，不予引用。**

---

## 0. 本地存放策略（重要）

| 项 | 决定 |
|---|---|
| 克隆位置 | `third_party/_local/PSB-RAL/`、`third_party/_local/AIM-PSL/` |
| 是否入库 | **否**。`.gitignore` 的 `third_party/*/` 已覆盖 `third_party/_local/`，`git status` 干净 |
| 是否修改上游 | **否**。两份 checkout 均 pristine（`git status --porcelain` 为空）；编译采用 **out-of-source**（`third_party/_local/_build/`） |
| 复用方式 | 只作**本地复现参考**；适配代码放 `baselines/psb_sumo/`、`baselines/psl_sumo/` |
| 公开再分发 | **禁止**——两个仓库均无许可证文件（见 §1.3 / §2.3），不得将其源码复制进本仓库公开版本 |

---

## 1. PSB（核心优化类 baseline 之一）

### 1.1 仓库标识（**已验证**，本机实测）

| 项 | 值 |
|---|---|
| URL | `https://github.com/JingtianYan/PSB-RAL.git` |
| 克隆日期 | 2026-11-07（经本地代理 `127.0.0.1:7890`） |
| 当前分支 | `main` |
| HEAD commit | `0b3f6eb34bf69a6d6d6a0fc2db5505073c90af24` |
| HEAD 提交时间 / 说明 | 2024-02-22 15:25:15 −0500 — "update code for RA-L" |
| 提交总数 | 4 |
| 体积 | 29 MB（含 `.git`） |
| 论文 | Yan, J. and Li, J. (2024). *Multi-Agent Motion Planning With Bézier Curve Optimization Under Kinodynamic Constraints*. IEEE RA-L. arXiv:2311.14145 |

### 1.2 目录与本轮关注点

```text
PSB-RAL/
├── Intersection/PSB-Intersection/     <-- 本轮唯一研究对象
│   ├── CMakeLists.txt
│   ├── src/{Driver,PBS,PTNode,SIPP,Instance,milp_cache,berstein,tgp_node}.cpp
│   ├── include/{PBS,SIPP,PTNode,Instance,milp_cache,berstein,tgp_node,Common}.h + rapidjson/
│   └── data/{intro_graph_3.json, pairDistance_3.json, vehicleArrival.json,
│             500vphpl/vehicleArrival_500vphpl_random{1..25}.json,
│             800vphpl/vehicleArrival_800vphpl_random{1..25}.json}
└── gridmap/PSB-MAPF/                  <-- 普通 MAPF，本轮不研究
```

### 1.3 许可证（**风险项**）

- 仓库内**不存在** `LICENSE` / `COPYING` / `NOTICE`（`find` 实测为空）。
- 结论：**无明确许可证 = 未授予再分发权**。可以本地复现研究，但：
  1. 不得把其源码提交进 `DSIP-RR`；
  2. 论文/回复中只能引用论文与仓库 URL，不得声称我们"再发布"了代码。
- 源码内是否含 CPLEX/IBM 专有头文件条款，取决于 IBM CPLEX 许可（见 §3）。

### 1.4 依赖（**已验证**）

| 依赖 | 要求 | 本机状态 |
|---|---|---|
| C++ 标准 | C++14（`set(CMAKE_CXX_STANDARD 14)`） | g++ 11.4.0 ✅ |
| CMake | ≥ 3.10 | 3.22.1 ✅ |
| Boost | `program_options`、`system`、`filesystem` | conda Boost 1.82.0 被 CMake 找到 ✅ |
| **IBM ILOG CPLEX + Concert** | **硬编码** `/opt/ibm/ILOG/CPLEX_Studio128` | **缺失 ❌（唯一硬阻塞）** |
| 开发环境 | Ubuntu 20.04（官方） | 本机 Ubuntu 22.04.5（可配置，未验证运行） |

### 1.5 编译状态（**实测失败，原因唯一**）

```bash
cmake -S third_party/_local/PSB-RAL/Intersection/PSB-Intersection \
      -B third_party/_local/_build/psb-intersection      # Configure done
cd third_party/_local/_build/psb-intersection && make -j4
# fatal error: ilcplex/ilocplex.h: No such file or directory
#   from include/SIPP.h:11  <-- 被 PBS.cpp / Driver.cpp 包含
```

**CPLEX 用在何处**（`src/SIPP.cpp`）：SIPP 在**生成速度剖面**时构造并求解 LP/MILP
（`IloModel`/`IloCplex` 出现在 29/59、120/199、302/389 行）。因此**无法通过"跳过某模块"绕过**，
它是算法本体的一部分（安全区间内的运动学可行速度）。

### 1.6 输出产物（决定 SUMO 适配可行性）

| 产物 | 内容 | 分类 |
|---|---|---|
| `output.txt`（`PTNode::writeToFile`，路径在 `Driver.cpp` **硬编码**） | 每车一行：`In Point;Out Point;Length;Earliest Arrival;In Time;Out Time Head;Out Time Tail;Time spend;Speed;Importance;Optimal T; Start Time; Control Points;` | **`schedule_only` + Bézier 控制点**（尚非时间索引轨迹） |
| `-c` 指定的 CSV（`PBS::saveResults`） | `runtime, #high-level expanded/generated, #low-level expanded/generated, solution cost, root g value, delay, runtime of ... , instance name` | **`search_stats_only`** |
| 仓库自带样例 `vehicle500vphpl_random1.csv` | 仅 1 行统计（`runtime=0.0897202`, `solution cost=81.3`, `delay=80.45`） | 历史样例，非本轮实验 |

### 1.7 上游实现的已知"配置陷阱"（**已验证，仅记录，不修改**）

1. `Driver.cpp` 用 `boost::program_options` 暴露 `-m/--map`，但**忽略它**：
   `graph_file = CONFIG_PATH + "intro_graph_3.json"`、`pairDistance_3.json` 硬编码。
2. `pbs.run("output.txt")` 同样硬编码输出名，`-o/--output` 实际无效。
3. `data/` 是**相对路径**：必须在 `Intersection/PSB-Intersection/` 下运行。


---

## 2. PSL（核心优化类 baseline 之二）

### 2.1 仓库标识（**已验证**）

| 项 | 值 |
|---|---|
| URL | `https://github.com/theanhhoang/AIM.git` |
| 克隆日期 | 2026-11-07 |
| 默认/当前分支 | **`AAAI22_PBS-SIPP`**（非 `main`/`master`；原样记录，**未切换分支**） |
| HEAD commit | `5686e15092fd95a46309a118655a5ab0c23c60fa` |
| HEAD 提交时间 / 说明 | 2022-08-18 07:51:14 −0700 — "Readme" |
| 提交总数 | 92 |
| 体积 | 494 MB（`venv/` 6.7 MB、`PBS-SIPP-ver2/` 104 MB、`MILP-FCFS/` 47 MB，含历史编译产物与 MP4/PDF） |
| 论文 | Li, J., Hoang, T., Lin, E., Vu, H. L., Koenig, S. (2023). *Intersection Coordination with Priority-Based Search for Autonomous Vehicles*. AAAI 2023 |

### 2.2 目录

| 目录 | 内容（实测） | 本轮用途 |
|---|---|---|
| `PBS-SIPP-ver2/` | PSL 主体（`Driver/PBS/PTNode/SIPP/Instance.cpp`）+ **预编译二进制 `AIMPBS`（41.7 MB）** + `intro_graph_3.json`、`pairDistance_3.json`、`vehicleArrival.json`、`output.txt`、`ReservationTable.txt`、`model.lp`、`solution` | **核心复现目标** |
| `PBS-SIPP-ver2-BFS/` | 同一实现的 BFS 变体 | 交叉参考，本轮不跑 |
| `MILP-FCFS/` | MILP 与 FCFS 对照实现（`AIMILP.cpp`，32 处 cplex 调用）+ 预编译 `AIMILP` | 论文另两个 baseline；本轮不跑 |
| `src/` | 与 `MILP-FCFS/` 同构的早期副本 | 不跑 |
| `Controller/` | `controller.py`（**默认 100 次仿真**）、`generate_arrivals_new.py`、历史 `result/` | **禁止直接运行**（见 §2.6） |
| `SUMO/` | `single_intersection.net.xml`（net v1.9，100×100 m，含内部车道，netedit 1.13.0 生成） | 作者自己的 SUMO 尝试遗迹；可作适配参考 |

### 2.3 许可证（**风险项**）

- 仓库内**不存在** `LICENSE` / `COPYING` / `NOTICE`（`find` 实测为空），`README.md` 也未声明许可。
- 结论同 §1.3：**无再分发权**，仅本地复现。

### 2.4 依赖（**已验证**）

| 依赖 | 要求 | 本机状态 |
|---|---|---|
| C++14 / CMake ≥3.10 | 由 `CMakeLists.txt` 指定 | ✅ |
| Boost `program_options/system/filesystem` | 必需 | conda Boost 1.82.0 ✅ |
| **CPLEX + Concert** | **硬编码** `/opt/ibm/ILOG/CPLEX_Studio1210` | **缺失 ❌** |

### 2.5 编译状态（**实测失败，原因唯一**）

```bash
cmake -S third_party/_local/AIM-PSL/PBS-SIPP-ver2 -B third_party/_local/_build/psl-pbs   # Configure done
make -j4    # Instance/PTNode/PBS/Driver 编译通过（仅告警），在 SIPP.cpp:9 失败：
# fatal error: ilcplex/ilocplex.h: No such file or directory
```

CPLEX 用途：`SIPP.cpp:205-223` 构造 `IloCplex` → `solve()` → `getValue()`，求安全区间内的
到达时刻与速度（并 `exportModel("model.lp")`）。与 PSB 同源，**不可绕过**。

**可能存在但未验证的旁路**：仓库自带 `PBS-SIPP-ver2/AIMPBS` 是**静态链接** ELF
（`ldd` 输出中**无** cplex 动态依赖），说明作者当年把 `libcplex.a` 静态链入。
若它能直接在本机运行，则 PSL **单样例复现**或许不需要本地 CPLEX；
但**重新编译**仍必须有 CPLEX。此旁路不改变"本地无法编译 PSL"的事实。
⇒ 该二进制是否可运行属于 **Stage 2** 内容，本轮**未执行**。

### 2.6 Controller 的默认行为（**本轮禁止运行**）

`Controller/controller.py` 实测结构：

- 第 3 行 `for randomness in range(1)`：脚本一执行就跑完一次完整流程；
- 第 227 行 `for randomness in range(99)`：再执行 99 次 ⇒ **总计 100 次**；
- 每次内部 `for step in range(4,30,5)` ⇒ 6 个车辆数档（4/9/14/19/24/29）；
- 每档同时跑 PSL、MILP、FCFS ⇒ 量级 **100 × 6 × 3 = 1800 次求解**。

⇒ **禁止执行 `python controller.py`**。Stage 2 只允许手工调用**单次**二进制。

### 2.7 输出产物

- `output.txt`：列同 PSB，但**无** `Optimal T; Start Time; Control Points`；
  `controller.py` 用它算 delay / travel time（`data[0..8]`）。
- `ReservationTable.txt`：`PBS.cpp:116-126` 用 `fstream::binary` 写 double/int，
  **不可按文本解析**，需按其写出格式读取。
- 仓库自带 `output.txt`（40 行样例）与 `result/` 历史统计只作**格式参照**，不是本轮结果。

### 2.8 与 PSB 的输入格式一致性（**已验证**）

两者使用**同一套实例格式**，这是统一接口设计的基础：

```jsonc
// intro_graph_3.json —— 顶点（冲突点）+ 冲突关系
{"vertices":[{"name":"WSR_0","pos":[-7.3152,-5.4864],"vertex_conflicts":["WER_0"]}, ...]}
// vehicleArrival*.json —— 每车一条
{"0":{"importance":1,"trajectory":["EWL_0","EWL_1",...,"EWL_7"],"lane":3,"id":0,"arrivalTime":0.77}, ...}
```

---

## 3. CPLEX：本轮唯一硬阻塞（**已验证**）

| 检查 | 结果 |
|---|---|
| `ls /opt` | 仅 `bytedance kingsoft nvidia wechat zotero` ⇒ 无 `ibm/ILOG` |
| `ls /opt/ibm/ilog* /opt/cplex* /usr/local/ibm/ilog*` | 均不存在 |
| `command -v cplex` | 空 |
| `python3 -c "import cplex"` | `ModuleNotFoundError: No module named 'cplex'` |
| `env \| grep -i cplex` | 空 |

**为什么不能自动解决**：

1. CPLEX 是 IBM 商业软件，需 IBM 账号 + 许可（学术版也需注册下载），
   属于**作者才能完成的凭据/许可行为**（`AGENTS.md` §0.5、§8）。
2. 两个仓库都把 CPLEX 路径写成 `set(...)`（**非 CACHE**），
   因此 `cmake -DCPLEX_BASE_DIR=...` **不生效**；只能改上游 `CMakeLists`
   或按它约定的绝对路径提供库。
3. 三种处置方式，**均需作者决策**，本轮**一种都未执行**：
   - **A**：作者安装 CPLEX（≥12.10，建议保留老版本归档），
     由**我们的** `baselines/*_sumo/CMakeLists.txt` 指向该路径，上游 checkout 保持 pristine；
   - **B**：按上游约定在本地建立 `/opt/ibm/ILOG/CPLEX_Studio1210`（及 `..._128`）
     （需 sudo、系统级改动，须作者本人执行）；
   - **C**：改用开源 LP/MILP（HiGHS/CBC）⇒ **属于修改算法实现**，
     破坏"原始复现"可信度，须作者明确授权且论文必须披露。

**当前结论**：PSB **不能编译、不能运行**（且无预编译二进制）；PSL **不能重新编译**，
其预编译二进制能否运行待 Stage 2 验证。

---

## 4. 变更与偏离记录

| 编号 | 类型 | 说明 | 日期 |
|---|---|---|---|
| U-01 | 新增 | 克隆 PSB-RAL（pristine，未改） | 2026-11-07 |
| U-02 | 新增 | 克隆 AIM-PSL（pristine，未改） | 2026-11-07 |
| U-03 | 构建 | out-of-source 配置/编译尝试，产物在 `third_party/_local/_build/`（不入库） | 2026-11-07 |
| U-04 | 待定 | CPLEX 落地方式（A/B/C） | 待作者决定 |

**未做且不得视为已完成**：未运行任何 PSB/PSL 样例、未修改任何上游文件、未创建 submodule、
未把上游源码复制进本仓库、未在论文中声称任何复现结果。

---

## 5. MMD（DSIP 的方法学上游 / 本轮重建对象）

- 授权：作者在 2026-11-07 的 DSIP Reconstruction 任务书中明确授权克隆
  `https://github.com/yoraish/mmd.git` 到 `third_party/_local/mmd/`。
- **状态：尚未克隆（Stage 1 执行）**。本表的 commit / 分支 / 许可证 / 依赖必须
  在 Stage 1 克隆后**实测填写**，不得预先臆测。
- 论文：Shaoul, Mishani, Vats, Li, Likhachev, *Multi-Robot Motion Planning with Diffusion Models*,
  ICLR 2025（稿件 refs.bib 中的 `shaoul2025`，即 DSIP 的 [41]）。
- 已确认的上游事实（来自工作区内 `docs/env/mmd-environment-audit.md`，第三方路径部分已作废）：
  - 上游 `mmd/` 与 `scripts/` 中**无** `traci`/`sumolib` 命中 ⇒ **上游不含 SUMO 集成**，
    DSIP 的 SUMO 桥接层属于已丢失的自有代码，必须重写。
  - 作者提示：官方代码在 **2024-11-07** 有过清理/效率修改，可能导致与论文结果略有差异
    ⇒ 必须记录**精确 commit**，不能默认最新等于论文版本。
- 本机已有 `mmd` conda 环境（Python 3.8.20 / PyTorch 2.0.0+cu118 / RTX 4060 可见），
  Stage 1 将验证其是否满足克隆 commit 的 `requirements.txt`（不得修改其他环境）。

### 5.1 实测登记（2026-11-07 填写完成）

| 项 | 值 |
|---|---|
| URL | `https://github.com/yoraish/mmd.git` |
| 克隆日期 | 2026-11-07（经本地代理 `127.0.0.1:7890`） |
| 分支 | `main` |
| HEAD commit | **`5c2597eb3e2def9f0a87d7972811d340343c0738`** |
| 提交时间 / 说明 | 2025-02-12 20:01:51 −0500 — "Update README.md" |
| 提交总数 | 10 |
| 体积 | 16 MB（不含模型） |
| LICENSE | **MIT**（© 2024 Shaoul, Mishani, Vats）⇒ 允许再分发，但本轮仍不复制进本仓库 |
| 依赖 | `environment.yml`（python 3.8 + patchelf + pip: pyyaml/matplotlib/setuptools）+ `requirements.txt`（torch 被注释，需另装）+ `deps/` 三个可编辑安装 + `setup.sh`（装 gdown） |
| 本机环境 | 复用既有 `mmd` conda 环境（Python 3.8.20 / PyTorch 2.0.0+cu118 / RTX 4060 可见）；**未新建环境、未安装任何包** |
| 克隆代码可导入 | ✅ `PYTHONPATH=third_party/_local/mmd` 下 `import mmd` 指向克隆；`CBS` 可导入 |
| checkpoint 归档 | `data_trained_models.tar.xz`（full 版，`gdown 1WO3tpvg-HU0m9RyDvGyfDamo7roBYMud`）→ 472 119 808 B，2026-11-07 下载 |
| 归档落盘 | `third_party/_local/_assets/data_trained_models/`（**Git 忽略**）；含 5 个 env，`EnvEmptyNoWait2D-RobotPlanarDisk` 在列 |
| 训练 commit | `81b20df798805a992f1653b77a9d53fe2a88b64b`（写入 args.yaml）**已不在上游历史中** |

**离线/无授权时的处置**：不把模型或源码提交入库；只登记 URL + commit + SHA256
（见 `docs/dsip_reconstruction/checkpoint_manifest.md`）。

