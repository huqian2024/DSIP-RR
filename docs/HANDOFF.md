# HANDOFF — DSIP-RR 当前状态交接

- 更新日期：**2026-11-02**（Task 06 checkpoint：审稿意见、口径对齐、FCFS 真实控制；Task 01–05 的记录见 §10）
- 本文档是**当前唯一权威的资产与边界说明**。与它冲突的旧报告一律作废（见 §4）。

> ## 🚩 当前状态（2026-11-02）
>
> | 事项 | 状态 |
> |---|---|
> | SUMO 环境（工作区内相对路径场景） | **已验证可运行**（Task 02/03/04 三次运行一致） |
> | 0.1 s 步长运行 | **已验证**（命令行 `--step-length 0.1` 覆盖，**不新建 cfg**；`departInterval` 在 SUMO 1.12.0 下被接受） |
> | TraCI 通路（traci 1.24.0 ↔ SUMO 1.12.0，协议 v20） | **已验证（含写入）**：`setStop` / `resume` 在 0.1 s 下生效 |
> | FCFS **Shadow Mode**（只算决策、不控制车辆） | **已完成**（`baselines/fcfs_sumo/`） |
> | FCFS **真实控制（单 run 验证）** | **✅ 已跑通**：`baselines/fcfs_sumo/control.py`；seed 81890、100 s 下 **无控制 2 次碰撞 → 控制 0 次** |
> | FCFS **完整基线复现（30 seeds × 5 密度 × 3 车道）** | **❌ 未开始**（仅单 run 验证，无性能矩阵） |
> | CCAM-DI / DSIP 复现 | **❌ 未开始**（无源码、无权重） |
> | 审稿意见 | **✅ 已获取并归档**（EIC + R1 Reject + R2 Major Revision；见 §11） |
> | 论文 LaTeX 审计（AGENTS §4） | **部分完成**：审稿矩阵 + 口径一致性表已建；本机无 LaTeX，**由作者云端编译** |
>
> **三条红线（必须随结果一起引用）**
> 1. **FCFS 只完成"单 run 验证"，不是"基线复现"。** 目前只证明"控制机制能消掉已观测到的出口汇流碰撞"，**没有任何性能矩阵、没有 30 seeds、没有多密度**。
> 2. **冲突矩阵是 provisional**（几何推导 + 无 `<request>/foes` 的网络）。当前控制用的是**车道级资源**（内部 via 车道 ∪ 出口车道），这一点是结构性的；但"资源不相交即安全"仍只在已实测的运行上成立，未被证明为一般结论。
> 3. **FCFS 的保守度是人为设定的**（D1 `Δt_safe=2.0 s`、D2 `L_ACZ=28 m`、D3 整组 movement 车道全预约）。单 run 中 80 辆车只完成约 21 辆，**延误偏高**——这是保守上界，不能当作 FCFS 的最好表现。

---

## 1. 当前项目目标

IEEE T-ITS 论文 **T-ITS-26-05-2776**（DSIP: A Dynamic Coordination Planner for Signal-Free Intersections Using Diffusion-Model-Based Multi-Agent Motion Planning）的 **Revise & Resubmit** 修订工作。目标是在可追溯、不可造假的前提下完成：

1. 审阅并修订 Overleaf 论文源（先审计、后修改；需作者授权才动正文）；
2. 复现/实现两种 AIM baseline：**FCFS（Dresner–Stone 预留式）** 与 **CCAM-DI**；
3. 在有明确授权与真实数据的前提下，完成范围受限的补充实验。

边界内原则（与 `AGENTS.md` 一致）：不覆盖原始论文与 SUMO 文件；不修改 `mmd` 环境；DSIP 重建仅在必要时、并经授权后进行；**不做消融、不开发新算法**；实验结论必须真实可追溯。

---

## 2. 永久工作区边界（硬性）

唯一允许访问的研究文件范围：**本工作区 `DSIP-RR` 根目录及其内部**。

- 不搜索、不遍历、不读取、不复制、不修改任何工作区外的研究文件（`~/Downloads`、`~/Documents`、旧实验目录、其他仓库等）。
- 不使用 `find ..`、全盘搜索、跨目录 `grep`、指向工作区外的绝对路径、符号链接或脚本绕过边界。
- 工作区内配置若引用外部文件（如 `scenarios/original/cross.sumocfg`），**只报告依赖，不访问目标**。
- 不下载、不克隆、不访问远程代码仓库（除非作者在具体任务中明确授权）。
- 需要工作区外资源时：**停止并向作者说明**，等待明确授权。

以上规则已写入 `AGENTS.md` §0，对所有后续 Agent 与任务长期有效。

---

## 3. 本轮确认的可用文件与缺失信息（仅依据工作区内文件）

### 3.1 资产状态表

| 资产 | 状态 | 依据 / 说明 |
|---|---|---|
| `scenarios/original/cross.sumocfg` | **AVAILABLE** | 存在；`begin=0`、`end=1000`、`step-length=1`；**三个输入均为工作区外的绝对路径**（见 §3.2） |
| `scenarios/original/cross1/2/3/4.net.xml` | **AVAILABLE** | 每进口车道数 2/2/3/4；`center` 为 `unregulated`；无 `tlLogic`；进口边 speed=13.90；进口边长 86.4 / 89.6 / 86.4 / 83.2 m |
| `scenarios/original/tls2/3/4.net.xml` | **AVAILABLE** | 每进口车道数 2/3/4；`center` 为 `traffic_light`；各含 1 个 `tlLogic`（4 个 phase）；进口边 speed=13.90 |
| `scenarios/original/routes.rou.xml` | **AVAILABLE（单套）** | 12 条 `route` + 12 条 `flow`，无 `vehicle` 元素；`begin=0`、`end=1000`；直行 `number=100`/`normal(10, 1.0)`，转向 `number=50`/`normal(20, 1.0)`；flow 级 `seed` = 82339–82350；`type="car"`；`departPos/departSpeed="random"` |
| `scenarios/original/types.typ.xml` | **AVAILABLE** | 单一 `vType car`：IDM、accel 1.0、decel 4.5、sigma 0.5、length 5.0、minGap 3.0、maxSpeed 13.9、tau 2.0、vClass passenger |
| `scenarios/original/nodes.nod.xml`、`2edges/3edges/4edges.edg.xml` | **AVAILABLE** | netconvert 输入文件 |
| `scenarios/original/routes.txt` | **AVAILABLE（未纳入 Git）** | 248 B / 4 行，内容为 5 组「直行/转向数量 + 间隔」备忘（26/13、40/20、52/26 … 100/50、132/66）。**含义与权威性 NOT VERIFIED**，需作者确认后才可引用 |
| 其他 `.sumocfg` / `.add.xml` | **MISSING** | 工作区内只有上述 1 个 cfg；无附加文件，无其他密度/车道配置的 cfg |
| 其他 `.rou.xml`（其他密度档、其他车道组合） | **MISSING** | 工作区内只有 1 套 flow 参数 |
| 历史逐 run 结果（CSV/轨迹/日志） | **MISSING** | 工作区内不存在；`results/` 仅有 `.gitkeep` |
| DSIP 源码 / checkpoint | **MISSING** | 工作区内不存在（与作者陈述一致） |
| 论文 LaTeX 源 `main.tex` | **AVAILABLE** | `paper/submitted/overleaf/…/main.tex`；`\documentclass[journal]{IEEEtran}`；8 个 figure 环境、2 个 table |
| 参考文献 `refs.bib` | **AVAILABLE** | 同目录，54 条条目 |
| 论文图件（含作者照片） | **AVAILABLE** | `main.tex` 引用的 13 个图件在工作区内**全部存在**：demo/tl2/tl3/tl4/as2/as3/as4/evolution (png) + 5 张 author jpg |
| Overleaf 导出 zip | **AVAILABLE** | 同目录下，15 个成员，完整性校验通过 |
| 投稿版 PDF | **MISSING** | `paper/submitted/` 下无 PDF → 无法与源码快照比对、无法核页数 |
| EIC 决定信 / R1 / R2 意见 | **MISSING** | `paper/reviews/` 为空目录，且被 `.gitignore` 排除 |
| 自定义 `.sty` / `.cls`、build 脚本 | **MISSING** | 依赖 IEEEtran 文档类；工作区内无构建脚本 |
| LaTeX 工具链（本机） | **MISSING（机器级）** | 见 `docs/env/environment-audit.md`：无 pdflatex/xelatex/latexmk/bibtex |
| 论文所述 5 档密度、30 个种子、0.1 s 步长 | **NOT VERIFIED** | 工作区内**无文件可证明**：只有 1 套 flow 参数、只有 flow 级 seed、cfg 写 `step-length=1` |
| 4/6/8 车道与 `cross*`/`tls*` 的对应关系 | **NOT VERIFIED** | 只能确认每个 net 的每进口车道数与交叉口类型；与论文「双向 4/6/8 车道」的对应需作者确认 |
| `scenarios/` 能否直接跑通 | **NOT VERIFIED（有阻断）** | 原 cfg 引用工作区外绝对路径；在工作区内运行需**新建**一个指向工作区内文件的新 cfg（新建属修改，需授权），且不得改动原 cfg |

### 3.2 已知的外部依赖（只报告，不访问）

`scenarios/original/cross.sumocfg` 的三个输入全部为工作区外绝对路径：

```
net-file         = /…/sumo_rl_demo/cross3.net.xml
route-files      = /…/sumo_rl_demo/routes.rou.xml
additional-files = /…/sumo_rl_demo/types.typ.xml
```

工作区内存在同名文件（`cross3.net.xml`、`routes.rou.xml`、`types.typ.xml`），但**是否与外部目标一致 NOT VERIFIED**（按边界规则不读取外部目标，故不做比对）。

### 3.3 现有文件可直接支撑的测试范围

- 7 个路网（4 个信号自由 + 3 个带信号灯）× 1 套车辆类型。
- 1 套交通流（12 条 OD，直行 100 / 转向 50，0–1000 s），**仅此一套**。
- 无任何可直接证明的「密度梯度」「多种子集合」「0.1 s 时间步」。因此目前**不能**声明可以复现论文的实验矩阵。

---

## 4. 已作废的上一轮报告（SUPERSEDED / NOT AUTHORITATIVE）

| 文件 | 失效范围 | 失效原因 |
|---|---|---|
| `docs/audits/scenario-provenance.md` | 全文 | 依据工作区外旧脚本与 CSV 推导密度、种子、步长、数据来源 |
| `docs/audits/aim-baseline-feasibility.md` | 全文 | 上游仓库信息来自网络；场景判断依赖工作区外资产 |
| `docs/audits/next-phase-minimal-plan.md` | 全文 | 输入全部来自上述两份文件 |
| `docs/audits/workspace-inventory.md` | 仅 §8 | §8 引用工作区外发现；§1–§7 仍为工作区内盘点，继续有效 |
| `third_party/README.md` | 外部路径与 commit | 同上 |
| `docs/env/mmd-environment-audit.md` | 仅 §4 | 上游源码路径与 commit 来自工作区外 |

处理方式：各文件顶部已加失效说明；**原文保留，未删除**；Git 历史未改写（未 reset / rebase / drop commit）。上述内容**不得引用**，也不得用于修改论文、实验设置、密度、种子、步长、指标或研究判断。

---

## 5. 当前 Git 状态

- 分支：`main`；远端 `origin` = `https://github.com/huqian2024/DSIP-RR.git`，`main` 已跟踪 `origin/main`，本地与远端均指向 `df62540`（详见 §9.6）。
- 提交历史（全部保留，未 reset / rebase / drop）：
  - `e41abb1` chore: initialize DSIP-RR local repository
  - `4f1c7ab` docs(audits): record local git initialization and initial commit provenance
  - `7e1c116` docs(env): fix conda-meta path typo in mmd environment audit
  - `554cd0e` docs(audits): phase-2 scenario provenance, AIM baseline feasibility, and next-phase plan（**内容已作废**，仅作历史记录）
  - `81340cf` docs: enforce workspace boundary and reset research handoff
  - 本轮：`docs: finalize session handoff`（hash 见 `git log -1`）
- 跟踪文件数：48（+ 本轮更新后 HANDOFF）。历史最大单文件：Overleaf 原始 zip ≈ 6.7 MB；无权重、无仿真输出。
- 工作区内有一份**未跟踪**文件 `scenarios/original/routes.txt`（非 Agent 创建，按作者要求**保持原样、不提交**）。
- 推送前安全检查结论（本轮执行）：全历史 diff 中未发现密码/token/私钥/API key 字符串（唯一命中是本仓库审计文档里对该风险的中文描述文字）；唯一含工作区外绝对路径的文件是 `scenarios/original/cross.sumocfg`（3 行 `/home/<user>/...`，属历史资产原样保留）。

---

## 6. 任务状态（2026-11-01 更新，详见 §10）

| # | 任务 | 状态 |
|---|---|---|
| 1 | 工作区内相对路径 SUMO 配置 + 冒烟测试 | ✅ **已完成**（Task 02）：`scenarios/smoke/cross3_smoke.sumocfg`，退出码 0、80 车出发、72 抵达、0 碰撞告警、0 传送 |
| 2 | TraCI 兼容性验证 | ✅ **已完成**（Task 03）：`traci 1.24.0 ↔ SUMO 1.12.0`，协议 v20，读取接口全通 |
| 3 | FCFS **Shadow Mode**（只算决策、不控制） | ✅ **已完成**（Task 04）：`baselines/fcfs_sumo/`，25 项自检全 PASS |
| 4 | FCFS **真实控制器**（`setSpeed`/`slowDown`/`setStop`） | ❌ **未开始**（下一步；需先定 §10.7 的参数） |
| 5 | FCFS Baseline **复现/性能实验** | ❌ **未完成** — 目前只有 Shadow，无控制、无指标、无 30 seeds |
| 6 | CCAM-DI 可行性确认 | ❌ 未开始（需网络获取 + 新环境，须逐次授权） |
| 7 | 论文 LaTeX 审计与页数核算 | ❌ 未开始（无投稿 PDF、无 R1/R2 意见、本机无 LaTeX） |
| 8 | 补充实验（密度/转向比） | ❌ 未开始（密度与车流口径仍挂起，见 §10.6） |

**明确声明：当前不再进行任何工作区外的数据调查。**

---

## 7. 需要作者授权才能开展的操作

| # | 操作 | 为什么需要授权 |
|---|---|---|
| 1 | 在 `scenarios/` 下**新建**一个指向工作区内文件的新 `.sumocfg`（原 cfg 不动） | 属于新增研究配置 |
| 2 | 采用现有文件之外的密度、种子、步长设置 | 工作区内无法证实，须作者给定 |
| 3 | 新建/生成交通流文件（任一密度档） | 属于生成实验输入 |
| 4 | 启动 FCFS baseline 开发与运行 | 新阶段工作，作者尚未启动 |
| 5 | CCAM-DI：新建 conda 环境 / 安装依赖 / 获取或训练权重 | 涉及环境变更与外部资源 |
| 6 | 任何工作区外的文件访问（含以前用过的旧脚本、CSV、MMD 源码目录） | 永久边界禁止，需逐次明确授权 |
| 7 | 安装 LaTeX 工具链或改用 Overleaf 编译流程 | 环境变更 |
| 8 | 修改论文正文、图表、参考文献 | 目前仅允许审计 |
| 9 | 将 `routes.txt` 纳入 Git | 版本控制决策（当前保持未跟踪） |
| 10 | 安装新工具（如 `gh` CLI）或变更系统软件 | 环境变更，未获授权 |
| 11 | 任何 push / 建立 remote（除作者本次已授权的一次私有仓库同步外） | 版本控制与对外发布决策 |

> 例外（作者本次已明确授权，仅限一次）：访问 GitHub 完成身份验证、创建 **Private** 仓库 `DSIP-RR` 并 push。该授权的执行状态见 §9。

---

## 8. 下一步（唯一动作）

> **2026-11-01 更新**：本节原有的"新建相对路径 cfg + 冒烟测试"**已完成**（Task 02），
> 见 §6 与 §10.2。当前下一唯一动作是：

**下一唯一任务**：在作者确认 §10.7 的**第 1–3 项参数**（安全间隔、控制区定义、资源粒度）之后，
把 `baselines/fcfs_sumo/` 从 **Shadow** 推进到**单一冲突对的最小控制原型**（例如 m05 × m10），
只做 100 s 单次验证，目标是不出现"冲突 movement 同时占用"；在此之前**不得**开展任何性能实验。

未完成的既有约束：

- 论文所述 5 档密度 / 30 种子 / 0.1 s 步长仍为 **NOT VERIFIED**，在作者给出参数前不作为任何实验输入。
- 15 组车流的生成按作者指示**挂起**（口径见 §10.6）。


---

## 9. 今日会话小结与 GitHub 同步状态

### 9.1 今日已完成（均有工作区内文档记录）

| 事项 | 产物 |
|---|---|
| 机器环境审计（OS/内核/CPU/内存/磁盘、GPU 驱动与 CUDA Toolkit 版本区分、SUMO、Python/conda、LaTeX 缺失、VS Code 解释器未配置、环境变量） | `docs/env/environment-audit.md` |
| `mmd` 环境审计（Conda 环境、Python 3.8.20、torch 2.0.0/cu118、`cuda.is_available()=True`；**未做任何修改**） | `docs/env/mmd-environment-audit.md` |
| 工作区资产盘点（工作区内文件清单、md5、引用关系、缺失项） | `docs/audits/workspace-inventory.md`（§1–§7 有效） |
| 本地 Git 初始化、`.gitignore` 策略与提交前核查 | `docs/audits/git-initialization.md`；提交 `e41abb1`、`4f1c7ab`、`7e1c116` |
| 工作区边界固化 + 越界调查结果作废 | `AGENTS.md` §0 与 §2 Provenance caveat；提交 `81340cf` |

### 9.2 已作废

见 §4（3 份报告全文、1 份报告 §8、1 份 §4、`third_party/README.md` 外部信息）。原文保留、未删除，Git 历史未改写。

### 9.3 尚未开始

**FCFS 与 CCAM-DI 均未开始实现**：无相关代码、无运行、无环境变更、无生成的车流文件。

### 9.4 GitHub 私有仓库同步状态：**BLOCKED（未完成）**

> 更新：该阻塞已于同日解除，最终状态见 **§9.6**（作者决定使用 Public 仓库并已完成推送）。本节保留为过程记录。


- 目标命令：`gh repo create DSIP-RR --private --source=. --remote=origin --push`
- 实际检查结果：

| 检查项 | 结果 |
|---|---|
| `gh --version` | **command not found**（`/snap/bin` 中亦无 `gh`） |
| `gh auth status` | 无法执行（同上） |
| `git remote -v` | 空 —— 无任何 remote |
| `git config --get credential.helper` | 未配置（本地与全局均无）→ 无可用于非交互 HTTPS push 的既有凭据 |
| VS Code CLI | 存在（`/snap/bin/code`）；`--list-extensions` 过滤 GitHub 后无输出 |

- 结论：**未创建仓库、未添加 remote、未 push**。原因是 GitHub CLI 不可用，而"安装新工具/变更系统软件"不在本次授权范围内（`AGENTS.md` 与本次任务均要求不得自行安装）；同时本地没有既有 Git 凭据，无法在非交互环境下完成认证。
- 明确未做的事：未安装 `gh`、未执行任何登录、未创建任何远程仓库、未添加 remote、未 push、未将任何内容公开、未改写 Git 历史。
- 解除阻塞的三条可选路径（需作者选择其一并完成凭据交互）：

| 选项 | 作者需要做的 | 之后 Agent 可做的 |
|---|---|---|
| A | 授权安装 GitHub CLI（如 `sudo snap install gh`）并本人完成 `gh auth login` | 执行 `gh repo create DSIP-RR --private --source=. --remote=origin --push` 并验证 |
| B | 在 VS Code 中使用「Publish to GitHub」创建 **Private** 仓库 `DSIP-RR`（勾选 private） | 添加/校正 `origin`，建立 `main` 跟踪，push 并验证可见性 |
| C | 在 github.com 手动创建 **Private** 仓库 `DSIP-RR` 并提供 URL | `git remote add origin <URL>`、`git push -u origin main` 并验证 |

- Agent 不会索取、读取或输出任何访问令牌；认证必须由作者本人完成。
- 当前状态对科研资产无影响：所有内容仍在本地 `main` 分支，历史完整（6 个提交）。


### 9.5 重试记录（同日，作者要求 retry Git）

重试结果：**仍然 BLOCKED**，比上次多确认了一条网络诊断信息。

| 检查 | 本次结果 |
|---|---|
| `command -v gh` / `gh --version` | 仍 **NOT FOUND**（未安装） |
| `gh auth status` | 无法执行（同上） |
| `git remote -v` | 仍为空 |
| `git config --get credential.helper` | 仍未配置（本地与全局均无） |
| 直连 `https://github.com`（curl，25 s 超时） | **超时失败** —— 本 shell 无直连 |
| 经本地代理 `http://127.0.0.1:7890` 访问 github.com | **HTTP 200（0.49 s）成功** |
| `git ls-remote`（直连、非交互） | 挂起至超时被杀（exit 143） |

结论：

1. **网络不是根因**：本机有本地代理 `127.0.0.1:7890`，设置 `https_proxy=http://127.0.0.1:7890` 即可访问 GitHub。
2. **真正的阻塞是认证与仓库创建工具缺失**：没有 `gh`，也没有任何 git 凭据（无 credential helper、无可用 token）。在既无仓库创建手段、又无凭据的情况下，`git push` 无法完成；而安装 `gh` 或配置凭据都属于未授权的系统/凭据变更，Agent 不得自行执行。
3. 本轮**未做任何状态变更**：未安装工具、未登录、未添加 remote、未 push、未创建仓库；工作树仍只有那份未跟踪的 `scenarios/original/routes.txt`。

最小解除路径（作者执行任一条，之后 Agent 可完成剩余步骤）：

- **A**：作者本人执行（含代理）
  ```
  sudo snap install gh
  https_proxy=http://127.0.0.1:7890 gh auth login      # 浏览器/设备码方式，由作者完成
  ```
  之后 Agent 执行：
  ```
  https_proxy=http://127.0.0.1:7890 gh repo create DSIP-RR --private --source=. --remote=origin --push
  ```
- **B**：作者在 VS Code「Publish to GitHub」创建 **Private** 仓库 `DSIP-RR`；
- **C**：作者在 github.com 创建 **Private** 仓库并提供 URL；随后需作者完成一次凭据配置（PAT 或 SSH key），Agent 再执行：
  ```
  git remote add origin <URL>
  https_proxy=http://127.0.0.1:7890 git push -u origin main
  ```

无论哪条路径，**认证必须由作者本人完成**；Agent 不索取、不读取、不输出任何 token 或密钥。


### 9.6 远端建立与推送 —— 最终状态（已同步）

时间线（同一天）：

1. 作者提供地址 `https://github.com/huqian2024/DSIP-RR.git`；
2. 推送前核实：该仓库当时 `private == false`、`size = 0 KB`、`GET /commits → HTTP 409`（空仓库），因此 Agent **先中止了 push** 并报告（见 §9.5 之后的记录与提交 `df62540`）；
3. **作者随后明确指示：仓库就是要 Public，并授权推送。** 该可见性由此成为**作者的显式决定**，不再是配置错误；
4. 执行推送并完成云端复核。

最终验证（经本地代理 `127.0.0.1:7890`）：

| 检查项 | 结果 |
|---|---|
| `git remote -v` | `origin  https://github.com/huqian2024/DSIP-RR.git`（fetch/push 均正确） |
| `git status -sb` | `## main...origin/main`（已建立跟踪） |
| 本地 `HEAD` | `df62540828f90f2562d0ae7a0c6056568c8f7d11` |
| 远端 `refs/heads/main` | `df62540828f90f2562d0ae7a0c6056568c8f7d11` — **与本地一致** |
| 云端提交数 | **8**（`e41abb1`、`4f1c7ab`、`7e1c116`、`554cd0e`、`81340cf`、`a20e708`、`324ba7e`、`df62540`） |
| `private` / `visibility` | **false / public**（作者指定） |
| `default_branch` | `main` |
| 仓库 URL | https://github.com/huqian2024/DSIP-RR |

**公开可见内容清单（作者已知悉并接受）**：未发表论文 LaTeX 源（`main.tex`、`refs.bib`）、8 张图件、5 张作者肖像、Overleaf 导出 zip、稿件编号与审稿相关记录、机器环境审计（硬件/驱动/CUDA 版本等）、`cross.sumocfg` 中的本地绝对路径（含用户名）、以及全部审计与交接文档（含已作废报告的原文）。

若将来需要回转：GitHub → Settings → General → Danger Zone → Change repository visibility → Make private。注意公开期间可能已被 clone/fork/缓存，回转只能阻止后续访问。**未跟踪文件 `scenarios/original/routes.txt` 未推送**（仍只存在于本地）。

在上述两点完成前，仓库保持"本地有版本、远端为空"的状态。

---

## 10. Task 01–05 检查点记录（2026-11-01）

### 10.1 已完成内容

| Task | 内容 | 产物 |
|---|---|---|
| 01 | 工作区只读审计（规范、Git、资产、实验就绪度） | 会话报告；`docs/HANDOFF.md` §3 资产表复核 |
| 02 | 工作区内相对路径 SUMO 配置 + 一次 100 s 冒烟 | `scenarios/smoke/cross3_smoke.sumocfg`；`results/smoke/` |
| 03 | TraCI 兼容性 + 12 流冲突结构分析 | `scenarios/smoke/traci_smoke_test.py`、`scenarios/smoke/net_analysis.py` |
| 04 | FCFS **Shadow Mode**（决策计算 + 事件记录，零控制） | `baselines/fcfs_sumo/`（9 文件 / 1273 行）；`results/fcfs_shadow/` |
| 05 | 审计 + HANDOFF 更新 + `.gitignore` 收紧 + 本地 checkpoint | 本次 commit |

### 10.2 SUMO / TraCI 实际验证结果

| 项目 | 实测值 |
|---|---|
| SUMO 二进制 | `/usr/bin/sumo` **1.12.0**，`SUMO_HOME=/usr/share/sumo`，另有 `sumo-gui`/`netconvert`/`duarouter` |
| Python | 3.12.2（conda `base`） |
| TraCI 客户端 | pip `traci==1.24.0`、`sumolib==1.24.0` |
| TraCI 协议 | `getVersion()` → **`(20, 'SUMO 1.12.0')`**，握手成功 |
| Task 02（CLI，`--end 100`，步长 1 s） | 退出码 **0**；loaded/inserted **80**、arrived **72**、running 8；collisions **0**、teleports **0**；1 条紧急制动警告（`flow_we.6` @ t=64）；平均速度 9.44 m/s、timeLoss 4.32 s |
| Task 03（TraCI，31 步） | 38 项检查，仅 `vehicle.setLane` 不存在（**TraCI 本身无此方法**，非版本不兼容） |
| Task 04（TraCI，100 步） | 80 辆车、80 次请求、进入 80 / 离开 78 / 结束时在内 2、0 非法状态转换 |
| 可复现性 | Task 02（CLI）与 Task 04（TraCI）的车辆数/到达数/警告完全一致；Task 04 两次运行统计逐项相同 → **种子固定、结果确定** |
| 未验证 | TraCI **写接口**语义（`setSpeed`/`slowDown`/`setStop`/`resume`）、订阅式读取、`getNextLinks`、多连接复用 |

### 10.3 Shadow Controller：数据与运行方式

```bash
python3 -m baselines.fcfs_sumo.test_logic      # 纯逻辑自检（不需 SUMO），25/25 PASS
python3 -m baselines.fcfs_sumo.runner          # 一次 100 s Shadow 运行（只读 getter）
python3 -m baselines.fcfs_sumo.analyze_shadow  # 对产出的 CSV 做二次分析
```
输出目录 `results/fcfs_shadow/`（`vehicle_events.csv`、`requests.csv`、`decisions.csv`、
`shadow_summary.json`、`shadow_run.log`、`shadow_analysis.txt`）。**这些产物全部可再生，未纳入 Git。**

关键数字（**SHADOW_MODE，无控制，不得当作性能结果**）：

| 指标 | 值 |
|---|---|
| 车辆 / 请求 / 重复请求 | 80 / 80 / **0** |
| 优先级重排次数 | **0** |
| 12 条 movement 是否全部识别 | ✅（直行 40、左转 20、右转 20，符合 1:2:1） |
| 进入 / 离开 / 结束时仍在交叉口内 | 80 / 78 / 2（配对 80 = 78 + 2 ✅） |
| 决策行 | 4561（BLOCKED 331、ELIGIBLE 92、UNDETERMINED 131、ENTERED 186、CLEARED 3821） |
| 进入前最后一次决策 | ELIGIBLE **9** / BLOCKED **46** / UNDETERMINED **25** |
| 实际进入时上一步为 BLOCKED | 46 辆（其中 **35** 辆当刻确有冲突 movement 在内） |
| 冲突 movement 同时占用 | 21 组冲突对、71 个步对（上界口径，见 §10.4） |
| 代理请求 → 进入交叉口 | 均值 6.92 s，中位数 7.00 s，范围 1–15 s |

**解释**：Shadow 无执行机构，因此"应被阻止却实际驶入"是**必然诊断**，**不是碰撞，也不是 FCFS 失效**。
它的价值是把"不控制会怎样"量化成可对照的基线。另需注意：在安全间隔未定义前，
80 辆中只有 **9 辆**能被确定性判定为准入——这是**必须先由作者给参数**才能推进的硬约束。

### 10.4 已知缺陷与限制

1. **冲突矩阵是 provisional**：`center` junction 为 `unregulated` 且 `<request>`/`foes` 元素数 = **0**，
   网络不提供任何权威让行模型；矩阵由内部车道中心线几何推导（24 对交叉）+ 8 对共享出口汇流，
   不含车宽、安全间距、清空时间。**车道中心线不相交 ≠ 可同时通行。**
2. **"冲突同时占用"只是 movement 级上界**：两辆分属冲突 movement 的车可能位于不同平行内部车道。
   `collision.check-junctions` **未启用**，因此本仓库目前**没有任何碰撞证据**，不得把 §10.3 的
   46 辆/71 步对解读为碰撞。
3. **步长 1 s**（论文为 0.1 s）；1 s 下速度控制粒度极粗，真实控制阶段必须重新确定。
4. **车流只有一套** `routes.rou.xml`，其密度约为 MaxD 的 1/10、比 MinD 还稀（见 §10.6），
   因此本阶段所有绝对数值都**不代表**论文条件。
5. **代理请求时间不是 Dresner–Stone 的请求时间**（无 ACZ/控制区定义）。
6. **ELIGIBLE 的语义偏严格**：只要冲突集合在请求之后被占用过就必须 `UNDETERMINED`。
   这在没有安全间隔参数时是正确的保守选择，但意味着**控制阶段无法对多数车辆给出"批准"判定**，
   必须先由作者裁决阈值口径。
7. `conflicts.py` 的**交叉校验**依赖 `results/smoke/net_analysis.log`（该文件可再生、未入库）；
   缺失时校验降级为 `SKIP`/`found=False`，冲突模型本身仍正常构建（已实测）。
8. TraCI **写接口未验证**：`setSpeed`/`slowDown`/`setStop`/`resume` 的真实生效窗口与安全校核尚未实测。
9. **车道数 ↔ 4/6/8 映射**未确认（`cross1` 与 `cross2` 都是每进口 2 车道）；U-turn 连接存在但未建模。
10. **出口车道汇流会产生真实碰撞**（2026-11-01 新发现）：用 `scenarios/flows/` 的 15 组车流在**无控制**
    条件下运行，全部文件在 100 s 内都出现 SUMO 碰撞（默认 teleport），且 **100% 发生在出口车道**
    （`center2north/south/east/west`），交叉口内部（`:center_*`）为 0；1 s 与 0.1 s 步长下都出现。
    碰撞对与 Task 04 的 8 对"共享出口车道"完全对应。后果：这些"无控制"运行**不能**当作零碰撞基线；
    FCFS 的资源必须覆盖**出口汇流**，而非仅交叉口内部通过。详见 `scenarios/flows/README.md`。

### 10.5 未验证假设（不得据以修改论文或实验）

| 假设 | 状态 |
|---|---|
| 论文"4/6/8 车道"= `cross2/3/4` 还是 `cross1/3/4` | **NOT VERIFIED** |
| 论文 5 档密度 / 30 seeds / 0.1 s 步长在工作区内可证 | **NOT VERIFIED**（只有 1 套 flow、只有 flow 级 seed、原 cfg 写 `step-length=1`） |
| 历史 DSIP 结果可复现 | **否**：无源码、无 checkpoint、无逐 run CSV |

### 10.6 车流口径现状（作者口述 + 工作区内核验，尚未用于任何实验）

- `scenarios/original/routes.txt`：15 格（5 档 × 3 种车道数）全部满足 **直行 : 单个转向方向 = 2 : 1**
  （换言之为 L:S:R = 1:2:1）；括号内为 **1000 s 视界内直行的平均发车间隔**。
- 作者说明 SUMO 步长为 **0.1 s** → 实际秒间隔 = 括号值 ÷ 10；一次 1000 s 运行的每进口每方向车辆数 = 表内数字 × 10。
- 按该 ×10 口径，**3 车道列与论文 Table I 逐档精确吻合**：直行 480/600/768/960/1200、
  左(右)转 240/300/384/480/600（2/4 车道列仅整数取整差 ±12）。
- 现有 `routes.rou.xml`（直 100 / 转 50、间隔 10 s/20 s、`end=1000`）用的是第 5 档的数字但摊在 1000 s 上，
  实际密度约为 MaxD 的 1/10（直行约 120 veh/(h·lane)，MinD 为 480）。
- **15 组车流已于 2026-11-01 生成**（作者当日指示，此前为挂起状态）：
  `scenarios/flows/lanes{2,3,4}_density{1..5}.rou.xml` + 生成脚本 `generate_flows.py` + `README.md`。
  生成后 15 个文件均通过 SUMO 1.12.0 加载校验（rc=0），并用独立校验脚本
  `scenarios/flows/validate_flows.py` 复核数量/间隔/比例（15/15 OK）。`routes.txt` 仍为未跟踪状态（按作者要求不提交）。
- `lanes3_*` 一列与 Table I 的 S 值（480/600/768/960/1200）精确吻合；2/4 车道列相差 ±12（整数取整）。
- 尚未决定：步长（1 s vs 0.1 s）、σ 是否保持 1 s、`departLane` 是否改 `best`、车道数 ↔ 网络文件映射。

### 10.7 进入真实 FCFS 控制前必须解决的技术问题（按阻断程度排序）

| # | 问题 | 为什么阻断 |
|---|---|---|
| 1 | **所需安全间隔 Δt_safe 未定** | 25/80 辆在"无法判定"状态下驶入；无此参数就无法给出批准/拒绝 |
| 2 | **控制区 / ACZ 定义与长度** | 决定请求时刻语义与开始限速的位置 |
| 3 | **资源粒度**（整个 movement / 内部车道集合 / 网格单元） | 直行 flow 占 3 条 via 车道，直接决定吞吐与保守度 |
| 4 | **清空判定** | 有 11 辆在"占据方同一步清空"时驶入；需下游客量/清空距离定义 |
| 5 | **控制手段与其副作用** | `setSpeed` 绕过跟驰安全校核（可能造成车体重叠）；`setStop` 会污染 `stopTime` 指标；须先做单冲突对验证 |
| 6 | **步长**（1 s vs 论文 0.1 s） | 1 s 下每步只能改一次速度，控制精度受限 |
| 7 | **到达时间模型** | 请求→进入跨度 1–15 s；`departLane=first` 导致进口内变道，加剧 ETA 噪声 |
| 8 | **死锁 / 平局规则** | Shadow 阶段天然不出现，加控制后必然出现 |
| 9 | **指标与安全口径** | `tripinfo.timeLoss` vs 自定义等待；是否启用 `collision.check-junctions`（AGENTS §7.7） |
| 10 | **车流/密度口径落地** | §10.6 的 ×10 口径需作者最终批准后才能生成 15 组流 |

### 10.8 Git 状态（本次 checkpoint）

- 提交信息：`checkpoint: validate SUMO environment and FCFS shadow controller`
- 提交 hash：见 `git log -1`（本文档随该提交入库，无法自指其 hash）
- 分支 `main`，tracking `origin/main`；**本次未 push / 未 pull / 未 fetch**，未改写任何历史
- **纳入版本控制**：
  - `baselines/fcfs_sumo/`（9 个文件：`__init__.py`、`conflicts.py`、`tracker.py`、`queue.py`、`shadow.py`、`runner.py`、`analyze_shadow.py`、`test_logic.py`、`README.md`）
  - `scenarios/smoke/`（`cross3_smoke.sumocfg`、`traci_smoke_test.py`、`net_analysis.py`）
  - `docs/HANDOFF.md`（本次更新）
  - `.gitignore`（新增 `results/**` 生成物忽略规则）
- **明确未提交**：
  - `results/**`（CSV/JSON/TXT/LOG/XML）—— 全部可由 §10.3 的命令再生，已由 `.gitignore` 覆盖
  - `scenarios/original/routes.txt` —— 按作者要求保持未跟踪
  - `scenarios/original/*` —— 原始资产，未修改、未新增
  - `paper/reviews/` —— 审稿材料，`.gitignore` 已排除
  - 本机环境信息、绝对路径产物、模型权重 —— 从未生成或已忽略


---

## 11. Task 06（2026-11-02）：审稿意见、口径对齐、FCFS 真实控制

### 11.1 审稿意见已到位

- 材料：`paper/reviews/EIC and review 1.docx`、`paper/reviews/review 2.pdf`（**`.gitignore` 排除，不入库**）
- 纯文本抽取件：`paper/reviews/_extracted/`（同样不入库）。方法：
  `soffice --headless --convert-to txt:Text "EIC  and review 1.docx"` + `pdftotext -layout "review 2.pdf"`
- 结论：EIC = Revise & Resubmit（**90 天**）；**R1 = Reject**（3 major + 4 minor）；**R2 = Major Revision**（10 条）
- **两位审稿人都没有要求消融实验** → "默认不做消融"的边界继续有效
- 逐条追溯：`docs/audits/reviewer-issue-matrix.md`

### 11.2 论文口径 ↔ 工作区 一致性（作者口径：以工作区为唯一可证来源）

- `docs/audits/paper-workspace-consistency.md`：25 条判定（10 MATCH / 5 待闭合 / 8 NOT VERIFIABLE / 2 随步长而定）
- **作者更正（2026-11-02）**：论文表述与 `scenarios/original/` 的文件**是吻合的**；
  原判的 5 条"冲突"应理解为"**文件是基座配置，实跑由命令行/脚本覆盖**"，已降级为"待运行侧闭合"
- 已核：`git log -- scenarios/original paper/submitted` 只有 `e41abb1` 一条；
  `git diff e41abb1 -- …` 为空 ⇒ **投稿版资产自导入后零改动**

### 11.3 作者确认的口径

| 项 | 值 | 出处 |
|---|---|---|
| 仿真步长 | **0.1 s**（命令行覆盖，不新建 cfg） | 作者口述 2026-11-02 |
| 信号配时 | **Table II 那一套**（4 相 20/40 + 右转按规则放行）；net 里的 2×42 s 是 netconvert 默认程序 | 同上 |
| 30 个 seed | **81890 … 81919**（连续 30 个） | 作者口述；已落 `experiments/seeds_30.txt` |
| FCFS 参数 D1–D10 | **全部按推荐值** | `docs/decisions/fcfs-parameters.md` §0.0 |
| 改动原则 | **改动最小**：不动 `scenarios/original/`、不新建场景文件、新增代码只加"执行模式" | 作者口述 |

### 11.4 FCFS 真实控制（新增 `baselines/fcfs_sumo/control.py`）

- **纯增量**：不修改 `conflicts.py` / `tracker.py` / `queue.py` / `shadow.py` 的任何语义
- 实现 D1–D8：`Δt_safe=2.0 s`、`L_ACZ=28 m`、资源 = 内部 via 车道 ∪ 出口车道、
  清空 = 观测无车 ∧ `now ≥ release+Δt_safe`、`setStop` 到停止线−2 m / 批准后 `resume`、
  排队键 `(request_time, vehicle_id)`、不 hold-and-wait
- 运行：`python3 -m baselines.fcfs_sumo.control [--baseline] [--end 100] [--seed 81890]`
- 产物：`results/fcfs_control/run_{control,baseline}_seed*.json` + `events_*.csv`（可再生产物，不入库）

**A/B 结果（同 seed 81890、同 0.1 s、同未改动资产、100 s）**

| 指标 | 无控制 | FCFS 控制 |
|---|---|---|
| 碰撞事件（去重后） | **2**（14 条逐步记录） | **0** |
| 碰撞位置 | `center2south_0`（出口汇流；`flow_ws.0` vs `flow_ns.0`、`flow_ns.6` vs `flow_ws.3`） | — |
| 请求 / 批准 | — | 58 / 29 |
| 被拦在停止线 | — | 40 |
| 无法拦停（forced） | — | 2 |
| 100 s 内完成行程 | 74 | 约 21 |

### 11.5 已发现但**未处理**的问题（下阶段必须先解决）

1. **预约粒度是当前唯一影响 FCFS 结果的大变量（已实测，2026-11-02）**

   一个直行 movement 有 3 条平行 via 车道，一辆车只走其中 1 条。默认实现把**整个
   movement 的 6 条车道**全部预约，于是"3 条平行直行车道同时只能放 1 辆车"。

   | 变体 | 预约粒度 | 碰撞 | 100 s 内完成行程 | 请求/批准 | 被拦停 |
   |---|---|---|---|---|---|
   | 无控制 | — | **2** | **74** | — | — |
   | FCFS `movement`（**当前默认**） | movement 全部车道（1 车占 6 条） | **0** | **约 21** | 58 / 29 | 40 |
   | FCFS `lane` | 按 `connection` 只预约该车实际走的 via + 出口车道 | **0** | **68** | 80 / 78 | 32 |

   开关：`python3 -m baselines.fcfs_sumo.control [--granularity {movement,lane}]`
   （**默认仍为 `movement`**，即作者 2026-11-02 决定保留的保守口径；`lane` 仅用于对照测量）

   **关键事实：两种粒度的碰撞数都是 0。** 也就是说，多预约那 4 条车根本不走的车道
   **不带来任何安全收益**，只损失约 3 倍吞吐。因此
   > "movement 级全车道预约" 属于**实现层面的过保守**，不是 FCFS 方法本身的缺点。
   > 论文里若要保留它，必须**显式说明粒度**，否则会被审稿人指出"人为削弱基线"。

2. **论文密度下 FCFS 尚不可用（2026-11-02 实测，未通过验收）**

   `cross3` + `lanes3_density3`（MedD）+ 1000 s + seed 81890 的实测：

   | | 无控制 | FCFS `lane`（默认参数） | FCFS `lane` + `--queue-guard` |
   |---|---|---|---|
   | 插入 / 加载 | **2700 / 5120** | **356 / 5120** | 1304 / 5120 |
   | 碰撞事件 | **107** | 1 | 6 |
   | 平均速度 | 7.59 m/s | 3.05 m/s | 2.49 m/s |
   | TimeLoss | 10.15 s | 65.27 s | 63.41 s |
   | 单 run 墙钟 | ~3 s | **138 s** | **115 s** |

   **三条必须先解决的问题（因此本轮没有启动 30 seeds × 5 密度 × 3 车道 的扫描）：**

   a. **饥饿**：FCFS 只插入 356/5120，无控制能插入 2700。这不是"保守"，是**承载不了需求**，
      不能作为可辩护的 AIM 基线。
   b. **残留碰撞来自 `forced`**：已定位到 `flow_se.1` 在 t=4.8 因"离停止线太近无法拦停"被放行，
      t=6.9 在 `center2east_0`（出口汇流）撞上 `flow_we.0`。**根因是 `departPos="random"`**：
      车辆可能随机出现在距停止线 1 m 内，任何控制器都无法拦住它。
   c. **吞吐瓶颈是出口车道**：D3 要求出口车道在 `MERGE_CLEAR=27.8 m` 内无车且再过 `Δt_safe=2 s`
      才复用，单条出口车道节奏约 4 s，密度一高就饱和。

   **已尝试并回退**：加"队列守卫"（看前车 + 授予超时撤销）把插入数提到 1304，
   但让已验证的 100 s 用例从 **0 碰撞变成 1 碰撞**（`forced` 2 → 5）。
   因此守卫**默认关闭**，仅作 `--queue-guard` 实验开关保留；默认路径回到已验证状态。

   **结论：控制器需要一次正式的设计/实现迭代，不能靠补丁。** 在它通过"MedD 插入数接近无控制
   且碰撞为 0"之前，**不启动全矩阵扫描**（否则 450 次 × ~2 min ≈ 17 机时/粒度，全部作废）。

### 11.5b 设计迭代第 1 轮（2026-11-02 晚）

**修掉的两个真实设计缺陷**

1. **出口车道复用时序被双重计费**：`MERGE_CLEAR = v_max·Δt_safe = 27.8 m` 的无车窗口本身
   已等价于 `Δt_safe`，释放时又再加 `+Δt_safe`，直接砍掉一半容量。现改为：安全缓冲只加在
   "占用是瞬时量"的车道上（via 车道），出口车道靠合流窗口表达。
2. **出口车道预约被提前释放**：车辆一进交叉口，`roadID` 变成 `:center_*`，与出口 lane 不等，
   于是被判"已离开"而释放预约 —— 这正是两个汇流伙伴同时上同一条出口车道的成因。
   现改为：必须**真正观测到车辆在该车道上并越过合流点**才释放。
3. 顺带：**只有车道队首**参与准入/拦停，队列交给 IDM 跟驰（此前对每辆车都 `setStop`，
   制造了大量 `too_close/forced` 与 hold-and-wait）。

**迭代后实测**

| 场景 | 插入 / 加载 | 碰撞 | 墙钟 |
|---|---|---|---|
| 100 s 轻载（`routes.rou.xml`） | 80 / 80 | **0** | ~2 s |
| MedD 1000 s（`lanes3_density3`） | **692 / 5120**（无控制 2700） | **1**（6 forced） | 135 s |

**仍未通过验收（插入数 692 ≪ 2000）。根因已定位，是设计层面的：**

> **`control.py` 根本没有使用几何交叉冲突矩阵。**
> `grep -n 'geometric\|model.matrix\|conflicts(' baselines/fcfs_sumo/control.py` → **无命中**。
> 资源集只由 `vias ∪ 出口车道` 构成，因此**只表达"同车道"与"合流"冲突，
> 不表达"交叉"冲突**（例如南北直行 vs 东西直行在交叉口中心相交，走的是不同 via 车道，
> 会被同时批准）。

后果有两条，都必须按红线处理：

a. **"0 碰撞"不是结构性保证，只是经验观测。** 现在能过 100 s 用例，靠的是密度低、IDM 与
   路口动力学没让它撞上，**不是**控制器保证了它不撞。HANDOFF 早先"资源不相交即安全"的
   表述因此**过强**，已在本节更正。
b. **互斥式（mutual exclusion）预约本身太粗**：把整条车道/整段时间互斥，
   吞吐上限被压到约 0.7–1.3 veh/s，而无控制是 2.7 veh/s。真正的预留式 AIM
   （Dresner–Stone / AIM4）用的是**时间窗（区间）预约**：只要两车通过同一冲突点的
   时间段相差 ≥ 安全间隔，就允许同时在交叉口内。

**因此下一轮不是调参，而是把资源预约从"互斥"改成"冲突点 + 时间窗"**：
`conflicts.py` 已经算好了 24 对交叉点与 8 对汇流关系，可直接作为冲突点集合；
需要新增的是"到达每个冲突点的 ETA"与"区间不重叠 ≥ Δt_safe"两项判定。
这是唯一能同时做到 (i) 结构上不撞、(ii) 吞吐接近无控制 的路径。

### 11.5c 设计迭代第 2 轮：冲突点 + 时间窗预约（2026-11-02 晚）

**新增 `baselines/fcfs_sumo/booking.py`**（纯增量；`control.py` 通过 `--booking {window,mutual}` 选择，
**默认 `window`**）：

- `ConflictPoints`：从 net 的内部车道几何算出 **28 条 via 车道、96 对交叉关系**
  （交叉点用四舍五入后的全局坐标作 key，两个 movement 会得到同一个 key），
  并把中心线重叠的 via 车道并成同一"空间组"。
- `WindowBooker`：资源三类 —— `("space", via)`（整段穿越）、
  `("cross", x, y)`（交叉点，Δt_safe）、`("merge", 出口车道)`（合流点，Δt_safe）。
- **窗口按区间而非点估计**：`[t_early, t_late + Δt_safe]`，
  其中 `t_early` 用 `v_max`、`t_late` 用 `V_SLOW=5 m/s` 下界。
  只用当前速度做点估计时，MedD 出现 **4 次交叉碰撞**；改成区间后降到 1。

**实测（三版对比，seed 81890）**

| 预约机制 | 100 s 碰撞 | MedD 插入 / 加载 | MedD 碰撞 | MedD 速度 |
|---|---|---|---|---|
| 车道互斥（`mutual`） | 0 | 692 / 5120 | 1 | 2.33 m/s |
| 时间窗·点估计 | 0 | 878 / 5120 | **4** | 2.47 m/s |
| **时间窗·区间（现行默认）** | **0** | **626 / 5120** | 1 | 2.25 m/s |
| 无控制参照 | 2 | **2700 / 5120** | **107** | 7.59 m/s |

**仍未通过验收（插入 626 ≪ 2000），且已定位到真正的主因：**

> **`scenarios/original/types.typ.xml` 的 `accel="1.0"` 让"停车等许可"极其昂贵。**
> 任何在停止线被拦下的车都要从 0 重新起步，而 1.0 m/s² 下 20 m 内部车道就要 6 s 以上；
> 现行准入逻辑是"资源忙 → 在停止线拦下 → 空出来再放行"，于是几乎每辆车都变成停走一次。
> 这不是预约机制的问题，而是**准入时机**的问题：预留式 AIM 的标准做法是在
> **车辆还保有车速时就授予**，让它不停车通过。

**下一轮的三件事（按收益排序）**

1. **提前授予**：在 ACZ 入口（28 m）就用预测窗口决策，使获准车辆不减速；
   只有在预测窗口冲突时才拦停。这是把插入数从 ~600 拉向 2000 的关键。
2. **闭环复核**：车辆真正进入 via 车道前复核自己的窗口，避免"开环 ETA 偏晚"造成越界占用。
3. **`forced` 归类**：`departPos="random"` 可能让车随机出现在距停止线 1 m 内，
   任何准入策略都拦不住；这类必须单独计数并说明，不能混进"控制器碰撞"。

> **顺带一条对论文有利的事实**：`accel=1.0 m/s²` 下，凡是"停走一次"的方法都会被重罚，
> 而 DSIP 那种让车连续运动的轨迹级规划天然占优。这比"削弱基线"要强得多，
> 而且完全可辩护——数值可以直接从 `types.typ.xml` 推出来。
### 11.5d 设计迭代第 3 轮：提前授予 + 运动学 ETA（2026-11-02 晚）

**两处改动**

1. **授予不再看"此刻物理是否空着"**。原来的 `_try_book` 调用 `_own_clear`，要求 via/出口车道
   **当下**就没有车 —— 一辆还在 28 m 外的车永远满足不了这个条件，于是几乎所有车都被拦停。
   现在准入完全由预测时间窗决定，这才是"提前授予"。
2. **ETA 改用 `types.typ.xml` 的运动学剖面**（新增 `travel_time()`）。
   原来用固定 `V_SLOW = 5 m/s` 估算，方向错了：从静止走 20 m 实际要 **6.32 s**，
   按 5 m/s 只算 4.0 s，窗口结束**过早**（不安全）。新区间用
   `[a=1.0 最好情况, a=0.5 最坏情况 + Δt_safe]`。

**数值自检（可直接复算）**

| 条件 | 时间 |
|---|---|
| 静止起步，20 m（内部车道），a=1.0 | **6.32 s** |
| 13.9 m/s 巡游，20 m | 1.44 s |
| 静止起步，88 m（进口边全长） | 13.27 s |

**实测**

| 版本 | 100 s 碰撞 | MedD 插入 | MedD 碰撞 | MedD TimeLoss | MedD 速度 |
|---|---|---|---|---|---|
| 时间窗·V_SLOW 估算（11.5c） | 0 | 626 | 1 | 89.4 s | 2.25 m/s |
| 时间窗 + 物理即时校验 | 0 | 763 | 2 | 65.5 s | 3.16 m/s |
| **时间窗 + 运动学 ETA（现行）** | **0** | **713** | 2 | **59.3 s** | 3.01 m/s |
| 无控制参照 | 2 | 2700 | 107 | 10.2 s | 7.59 m/s |

**2 次碰撞已定位（不是 forced 造成的）**

```
t=554.1  center2east_2   flow_we.65 vs flow_ne.39
t=611.6  center2east_2   flow_we.77 vs flow_ne.46
forced 车辆为 flow_ne.24 / flow_we.58 / flow_nw.40 / flow_ns.92 —— 与碰撞车无关
```

两次都是 **`center2east_2` 的汇流**（西→东直行 与 北→东右转共用该出口车道）。
机制：放行后出口车道下游拥堵，车速跌破最坏情形 `a=0.5`，实际到达合流点晚于预约窗口。
⇒ **不是漏了合流预约，而是"车在交叉口内被迫停车"没有被建模。**

**验收线的量纲分析（重要）**

2000 辆 / 1000 s = 2 veh/s；12 条进口车道 ⇒ 每车道 1 辆 / 6 s；
而静止起步走完 20 m 内部车道本身就要 **6.32 s**。
⇒ **"≥2000" 恰好就是"停车等待式"控制的物理上限**，预约算法再好也很难超过。
当前 713 ≈ 上限的 37%；缺口来自冲突点窗口串行（`grants=450 / rejections=37438`）。

**下一步（两条，按收益）**

1. **出口车道余量检查**：放行前确认目标出口车道头部有 ≥ 车长+minGap 的空位，
   杜绝"进交叉口后被迫停车"——这是消掉当前 2 次碰撞的直接手段。
2. **车队/成组放行**：同一 via 车道连续放行（前车在途即预约后车窗口），
   压缩每车道 6.3 s 的节拍——这是唯一能逼近上限的做法。



3. **单 run 不足以当基线**：仍需 30 seeds × 5 密度 × 3 车道；车道数↔net 映射（`cross1` vs `cross2`）仍未确认。
   已实现 `--net` / `--flows`，可按 `lanes2→cross2`、`lanes3→cross3`、`lanes4→cross4` 扫描
   （**该映射为按 net 命名单调序列的推断，仍待作者确认**；`cross1` 亦是 2 车道，二义未消）。
3. `--collision.check-junctions` 仍未启用；当前"0 碰撞"仅指 SUMO 的车辆碰撞检测。
4. 本机无 LaTeX；页数与公式渲染由作者在云端编译确认。

### 11.6 Git（Task 06 checkpoint）

- 纳入版本控制：`docs/HANDOFF.md`（本次）、`docs/audits/reviewer-issue-matrix.md`、
  `docs/audits/paper-workspace-consistency.md`、`docs/decisions/fcfs-parameters.md`、
  `baselines/fcfs_sumo/control.py`、`experiments/seeds_30.txt`
- 明确未提交：`results/**`（可再生）、`paper/reviews/**`（私人材料，`.gitignore` 排除）、
  `scenarios/original/routes.txt`（按作者要求未跟踪）
- 未改写任何历史；未 push

