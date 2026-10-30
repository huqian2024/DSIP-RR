# 工作区资产盘点（DSIP-RR）

- 盘点日期：2026-10-30
- 范围：当前工作区根目录下的全部文件（32 个文件，14 MB）；未移动、未重命名、未覆盖、未修改任何研究资产。
- 路径统一用 `~` 表示家目录。

## 1. 目录结构与体积

```
DSIP-RR/
├── AGENTS.md                     30 KB   （已阅读，含 R&R 约束）
├── .gitignore                    312 B   （初始化前已存在，本阶段扩充，见 git-initialization.md）
├── baselines/                    空
├── evaluation/                   空
├── experiments/                  空
├── results/                      空
├── src/                          空
├── third_party/                  空
├── docs/audits/、docs/env/       空（本阶段新增 4 份报告）
├── paper/
│   ├── revision/                 空（可编辑修订版尚未建立）
│   ├── reviews/                  空（**审稿意见文件缺失**）
│   └── submitted/overleaf/       Overleaf 导出快照（6.5 MB zip + 解压目录）
└── scenarios/original/           14 个文件，188 KB（SUMO 资产）
```

## 2. 论文资产（`paper/submitted/overleaf/`）

解压目录名含投稿标题全称，内部 15 个文件，与 zip 内容一致（zip 完整性校验通过，`testzip()` 返回 None）。

| 文件 | 大小 | MD5 | 说明 |
|---|---|---|---|
| main.tex | 64,581 B | aaf9db96ed36cfb841196463103d5bc2 | 唯一根 tex，`\documentclass[journal]{IEEEtran}` |
| refs.bib | 20,125 B | 1e2eab8540d63608fb9d9445735e79b3 | 54 条 `@` 记录，`\bibliography{refs}` |
| demo.png | 523 KB | 1cf7bd12de162051c8467c82e42ec2f4 | Fig. 1（`fig:demo`） |
| tl2.png / tl3.png / tl4.png | 941/981/880 KB | 956da5b3… / 3d30d52c… / 36e02a33… | Fig. 2–4（平均时间损失，已渲染的历史图件） |
| as2.png / as3.png / as4.png | 87 KB 各 | 39184595… / f3383b30… / e4a5eb65… | Fig. 5–7（平均车速） |
| evolution.png | 269 KB | 8919c4d5… | Fig. 8（演化/冲突区图） |
| 5 位作者肖像 .jpg | 23 KB–1.9 MB | — | IEEEbiography 用图 |

文本结构：8 个 figure 环境、2 个 table 环境（Table I 交通流密度、Table II 绿灯时间分配），章节为 Introduction / Related Works / Simulation / Methodology / Results and Discussion（+ 结论，见 tex 后段）。

### 关键缺失

1. **原始投稿 PDF 不在工作区**。`paper/submitted/` 下只有 Overleaf 源码快照，没有可直接引用的投稿版 PDF，因此"源码快照是否与投稿 PDF 完全一致"目前无法核对（`AGENTS.md` 第 4 节要求的比对前提不成立）。
2. **审稿意见缺失**：`paper/reviews/` 为空 —— EIC 决定信、R1 意见、R2 附件都没有。没有它们就无法建立逐条 reviewer→修改 的追踪矩阵。
3. 无自定义 `.sty` / `.cls`、无 build 脚本、无 subfile；模板依赖 IEEEtran 文档类（本机未安装 LaTeX，无法编译验证）。
4. 参考图件均为 **PNG 位图**（非 PDF/EPS 矢量），这对 R1/R2 提出的"图 8 可读性"与"Fig. 2–4 纵轴单位"修改是硬约束：只能重绘或用原始位图做裁剪/放大，且**不得**改变原图数值（`AGENTS.md` 第 6.0 节）。


## 3. SUMO 资产（`scenarios/original/`）

14 个文件，与 `~/Downloads/sumo_rl_demo/` 中的同名原始文件逐字节一致（已用 md5 抽查确认，见下表）。

### 3.1 配置

| 文件 | MD5 | 内容摘要 |
|---|---|---|
| cross.sumocfg | c08df288e89e936e8a9be8d0eb28dedd | `net-file`/`route-files`/`additional-files` 三个输入均写成**绝对路径** `~/Downloads/sumo_rl_demo/…`；`begin=0`、`end=1000`、`step-length=1`；**无 `seed` 元素** |

配置引用的三个外部文件**全部存在**且与工作区副本 md5 一致：

| 引用目标 | 存在 | md5 与工作区副本一致 |
|---|---|---|
| `cross3.net.xml` | ✔ | ✔ (c6a00f03d6ab67dc1dc373ea172ecbfc) |
| `routes.rou.xml` | ✔ | ✔ (1e3ff29c057103252e206239df7b80db) |
| `types.typ.xml` | ✔ | ✔ (69f278b34abfc9e0476bea438c7810e3) |

可运行性验证：`sumo -c scenarios/original/cross.sumocfg --end 1` 退出码 0；TraCI 连通性测试 3 步正常（见 `docs/env/environment-audit.md`）。**注意**：cfg 里是绝对路径，换机器/换目录即失效 —— 这在 baseline 阶段需要以"新增包装 cfg + 记录原 cfg 未改动"的方式解决，本阶段不动原文件。

### 3.2 路网

| 文件 | MD5 | 每进口车道数 | 干道长度(m) | 是否含 `tlLogic` |
|---|---|---|---|---|
| cross1.net.xml | 7e90d91ced4493b61a30fad52801064c | 2 | 86.40 | 无（信号自由） |
| cross2.net.xml | 2b706259221435d00c7014506e20ffa9 | 2 | 89.60 | 无 |
| cross3.net.xml | c6a00f03d6ab67dc1dc373ea172ecbfc | 3 | 86.40 | 无 |
| cross4.net.xml | 6a876e4c1f0620e47d8ad388785653c0 | 4 | 83.20 | 无 |
| tls2.net.xml | e7d958fc7fc2943f7b33dfc4d514c955 | 2 | 含内部车道 | 有（1 个） |
| tls3.net.xml | bd5f69c9d238a2b38c74596e4d39bcf8 | 3 | 含内部车道 | 有（1 个） |
| tls4.net.xml | 8ccdd8a12b4eb56f022c0f3c893170f7 | 4 | 含内部车道 | 有（1 个） |

生成源文件亦保留：`nodes.nod.xml`(f1107277…)、`2edges.edg.xml`(d07d2c3c…)、`3edges.edg.xml`(436f2dd4…)、`4edges.edg.xml`(b8a30540…)，均为 netconvert 输入。`tls*` 比对应 `cross*` 多了信号控制所需的内部车道（长度 1.44/3.23 m 等），说明二者是同几何的"有/无信号"配对版本。

### 3.3 交通流与车辆类型

| 文件 | MD5 | 内容 |
|---|---|---|
| routes.rou.xml | 1e3ff29c057103252e206239df7b80db | 12 条 `route` + 12 条 `flow`（四进口 × 直/左/右） |
| types.typ.xml | 69f278b34abfc9e0476bea438c7810e3 | 单一 `vType` `car`：IDM、accel 1.0、decel 4.5、sigma 0.5、length 5.0、maxSpeed 13.9 (=50 km/h)、tau 2.0、minGap 3.0 |

`routes.rou.xml` 的实际参数（**不要修改**，仅记录）：

- 直行：`departInterval = normal(10, 1.0)`，`number = 100`
- 左/右转：`departInterval = normal(20, 1.0)`，`number = 50`
- 每条 flow 自带 `seed`：82339–82350（连续 12 个）
- 转向比例 50 : 100 : 50 = **1:2:1** ✔（与论文一致）
- 起点/速度随机（`departPos="random"`、`departSpeed="random"`）

### 3.4 与论文实验设置的不一致（**只记录，不修改**）

| 项目 | 论文描述 | 现有文件 | 影响 |
|---|---|---|---|
| 仿真步长 | 0.1 s（规划更新 0.4 s） | `cross.sumocfg` 中 `step-length = 1` | 若直接按现有 cfg 复现，时间精度与"0.4 s 更新"无法对齐；需作者确认真实历史配置 |
| 交通密度 | 5 个等级（MinD/LowD/MedD/HigD/MaxD，见 Table I） | 只有 **1 组** flow 参数（直行间隔 10 s、转向 20 s） | 5 个密度等级对应的 route 文件**缺失**；按 Table I 与式(1) 反算，现有需求远低于 MinD |
| 车道映射 | 双向 4/6/8 车道 | cross2/3/4 = 每进口 2/3/4 车道 → 双向 4/6/8 车道 | 映射可由车道数推断，但 `cross1`（2 车道、86.40 m）与 `cross2`（2 车道、89.60 m）并存，两者用途需作者确认 |
| 全局种子 | 每配置 30 个不同随机种子 | cfg 无 `seed`；仅 flow 级 seed | "30 个 run" 的全局种子清单未落盘，属**已知但未确认**的关键复现参数 |

## 4. 与 `AGENTS.md` 的差异记录

按任务要求核对"`AGENTS.md` 历史资产描述 vs 最新事实"，未发现研究方向层面的冲突，仅有以下事实性补充/差异（**未因此改动任何研究计划**）：

1. `AGENTS.md` 称原始 SUMO 的 `.net.xml/.rou.xml/.sumocfg/.add.xml` 均保留 → 实际核实：路网、车辆类型、**单一密度**车流、单一 cfg 保留；**5 个密度等级的车流文件未找到**，也没有 `.add.xml` 类附加文件。
2. `AGENTS.md` 目标布局中的 `paper/submitted/`（"immutable submitted PDF / Overleaf snapshot"）→ 实际只有 Overleaf 快照，**无投稿 PDF**。
3. `AGENTS.md` 称"原始随机种子已知" → 现可读取的是 flow 级 seed（82339–82350）与 cfg 中缺省的 `--seed`；30 个 run 的完整种子列表需作者确认后才能写进实验配置。
4. `AGENTS.md` 的第一优先任务（FCFS / CCAM-DI baseline）与本次任务描述一致，无冲突。

## 5. 工作区之外的候选历史资产（仅记录，未导入）

`~/Downloads/sumo_rl_demo/`（现有 cfg 的绝对路径指向处）除上述 XML 外，还包含 `AttentionLight/`、`colight/`、`MPLight/`、`colight_models/`、`model/`、`records/`、`results/`、`logs/`、`mmd/` 等目录，以及若干自动化脚本与截图 PNG。这些疑似是论文中 RL baselines（MP-Light / CoLight / AttentionLight）与历史绘图脚本的残留。

本阶段**未**读取其内部内容、**未**复制进仓库、**未**运行。是否作为历史证据纳入 `third_party/` 或 `experiments/`，需作者判断（涉及"能否证明历史结果来源"的问题）。

## 6. 缺失资产清单（汇总）

| 缺失项 | 状态 | 影响 |
|---|---|---|
| 投稿版 PDF | 缺失 | 无法与源码快照比对、无法核页数/图序 |
| EIC 信 + R1/R2 意见 | 缺失 | 无法建立 reviewer→修改 追踪矩阵 |
| 5 个密度等级 route 文件 | 缺失（仅 1 组） | 无法复现论文的 5 密度 × 3 车道配置网格 |
| 30 个 run 的全局种子清单 | 未确认 | 复现随机性无法对齐 |
| 原始 DSIP 源码 / checkpoint / 逐 seed CSV / 轨迹日志 | 已知丢失 | 历史曲线不可重算（只能用现有 PNG 作为历史图件） |
| 0.1 s 步长的真实 cfg | 未找到 | 复现配置与论文描述不一致 |
| LaTeX 工具链 | 未安装（环境侧） | 无法编译、无法核算页数 |
| 矢量版图件（PDF/EPS） | 缺失（只有 PNG） | Fig. 2–8 的可读性修改受限 |

## 7. 结论

- 研究资产**不齐全**：论文侧缺"投稿 PDF + 审稿意见"，实验侧缺"多密度车流 + 全局种子清单"；DSIP 端代码/数据按已知情况永久缺失。
- 现有资产足以支撑下一步：用 `cross2/3/4.net.xml` + `types.typ.xml` + 论文 Table I/式(1) 重新生成 5 个密度等级的 route 文件（需作者授权并留下生成脚本），在 SUMO 1.12 + TraCI 上跑 FCFS / CCAM-DI baseline。
- 但在开始 baseline 之前必须补齐两件前置事项：LaTeX 编译工具链，以及 EIC 信/审稿意见归档。

