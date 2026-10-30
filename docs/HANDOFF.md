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

- 分支：`main`；本轮修改前工作树干净。
- 历史提交（保留不动）：
  - `e41abb1` chore: initialize DSIP-RR local repository
  - `4f1c7ab` docs(audits): record local git initialization and initial commit provenance
  - `7e1c116` docs(env): fix conda-meta path typo in mmd environment audit
  - `554cd0e` docs(audits): phase-2 scenario provenance, AIM baseline feasibility, and next-phase plan（**内容已作废**，仅作历史记录）
- 本轮提交：`docs: enforce workspace boundary and reset research handoff`（hash 见 `git log -1`）。
- 无 remote、未 push、未创建 GitHub 仓库。
- 工作区内有一份**未跟踪**文件 `scenarios/original/routes.txt`（非本轮 Agent 创建，见 §3.1）；是否纳入版本控制需作者决定。

---

## 6. 下一阶段尚未启动的任务

1. FCFS baseline 的最小实现（**未启动**，需作者授权）。
2. CCAM-DI 可行性确认（**未启动**，需作者授权，可能需要新环境）。
3. 论文编译审计与页数核算（**未启动**；本机无 LaTeX，可按作者指示改用 Overleaf）。
4. 补充实验（**未启动**；任何参数未确认前不得开始）。

**明确声明：当前不再进行任何工作区外的数据调查。** 下一阶段是在**作者确认后**，仅使用 `DSIP-RR` 内的资产推进 FCFS baseline 的最小实现。

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
| 9 | 将 `routes.txt` 纳入 Git；或建立 remote / push | 版本控制决策 |

---

## 8. 下一步（唯一建议动作）

请作者就以下两点给出指示，之后再动代码：

1. 是否授权**新建**一个工作区内的 `.sumocfg`（新文件，原文件不动），以便用现有 `cross*.net.xml` + `routes.rou.xml` + `types.typ.xml` 在工作区内跑通一次最小 SUMO 冒烟测试；
2. 论文所述 5 档密度、30 种子、0.1 s 步长：由作者直接给出参数，还是标记为 NOT VERIFIED 并在修订说明中回避。

在得到答复前，本仓库不启动任何实验或代码开发。

