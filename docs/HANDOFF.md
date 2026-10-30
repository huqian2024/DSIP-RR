# HANDOFF — DSIP-RR 当前状态交接

- 更新日期：2026-10-30
- 本文档是**当前唯一权威的资产与边界说明**。与它冲突的旧报告一律作废（见 §4）。

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

- 分支：`main`；本地仓库，**无 remote**（`git remote -v` 为空）。
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

## 6. 下一阶段尚未启动的任务

1. **下一唯一任务（已由作者指明，尚未执行）**：仅使用工作区内现有 XML，**新建一个相对路径的 SUMO 配置**（原 `cross.sumocfg` 不动），并完成**一次短时冒烟测试**，确认工作区内资产可被 SUMO 加载运行。
2. FCFS baseline 实现（**未开始**，需在冒烟测试之后、由作者另行授权）。
3. CCAM-DI 可行性确认（**未开始**，需作者授权，可能需要新环境）。
4. 论文编译审计与页数核算（**未开始**；本机无 LaTeX，可按作者指示改用 Overleaf）。
5. 补充实验（**未开始**；任何参数未确认前不得开始）。

**明确声明：当前不再进行任何工作区外的数据调查。** 上述第 1 项也只在工作区内、且不修改任何原始文件的前提下进行。

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

**下一唯一任务**：仅使用工作区内现有 XML（`cross*.net.xml` / `tls*.net.xml` / `routes.rou.xml` / `types.typ.xml`），**新建**一个使用**相对路径**的 `.sumocfg`（原 `cross.sumocfg` 保持不动，因为它引用工作区外绝对路径且不得修改），并执行**一次短时冒烟测试**（例如 `sumo -c <新cfg> --end 1`），确认工作区内资产可被 SUMO 正确加载。

该动作**尚未执行**，等作者下一条指令后开始；不涉及论文修改、不生成新交通流、不启动 baseline。

论文所述 5 档密度 / 30 种子 / 0.1 s 步长仍为 **NOT VERIFIED**，在作者给出参数前不作为任何实验输入。


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


### 9.6 仓库地址已提供，但可见性为 **PUBLIC** —— push 已中止（安全阻断）

作者于 2026-10-30 提供目标地址 `https://github.com/huqian2024/DSIP-RR.git`。推送前按流程核实可见性，结果如下（经本地代理 `127.0.0.1:7890` 调用 GitHub API，未使用任何凭据）：

| 字段 | 值 |
|---|---|
| `full_name` | `huqian2024/DSIP-RR` |
| `private` | **false** |
| `visibility` | **public** ← 与任务要求的 Private 不符 |
| `size` | 0 KB |
| `default_branch` | `main` |
| `created_at` / `pushed_at` | 2026-10-30T09:58:14Z / 09:58:15Z |
| forks / watchers | 0 / 0 |
| `GET /commits` | HTTP 409（"Git Repository is empty"） |

判定与处置：

1. 仓库为**空仓库**，尚未推送任何内容，因此**目前没有发生泄露**。
2. 按任务约束「必须 Private、不得创建 Public 仓库」与「发现冲突即停止并报告」，**本轮中止 push**：未添加 `origin`、未 push、未改动远端、未改写本地历史。
3. 若此时推送，将公开暴露：未发表论文 LaTeX 源（`main.tex`、`refs.bib`）、8 张图件与 5 张作者肖像、Overleaf 导出 zip、稿件编号与审稿相关记录、机器环境审计（含硬件/驱动版本）、以及 `cross.sumocfg` 中的本地绝对路径（含用户名）。

解除该阻断（需作者操作）：

1. GitHub → 该仓库 → **Settings → General → Danger Zone → Change repository visibility → Make private**（按提示确认，可能需要 2FA）；
2. 完成后告知 Agent 重试。Agent 将先用 API 复核 `private == true`，再执行：
   ```
   git remote add origin https://github.com/huqian2024/DSIP-RR.git
   https_proxy=http://127.0.0.1:7890 git push -u origin main
   ```
3. 另需注意：本地仍**没有任何 Git 凭据**（`credential.helper` 未配置）。即使仓库转为私有，`git push` 仍需作者本人完成一次认证（`gh auth login`、PAT 存入 credential store，或配置 SSH key）。Agent 不会索取或输出 token。

在上述两点完成前，仓库保持"本地有版本、远端为空"的状态。

