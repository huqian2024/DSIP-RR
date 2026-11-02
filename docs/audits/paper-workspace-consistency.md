# 论文口径 ↔ 工作区资产 一致性表

- 建立日期：**2026-11-02**
- 状态：**AUDIT ONLY**（只判定，不改论文、不改任何 SUMO 文件、不改 `AGENTS.md` / `HANDOFF.md`）
- **作者口径（2026-11-02 指令）：论文的每一处修改，都必须以"现在的工作区"为唯一可证来源。**
  因此本表的作用是：**先判定哪些论文陈述与工作区一致、哪些不一致，再决定改哪一边。**
- 论文基准：`paper/submitted/overleaf/…/main.tex`（**作者已确认 = 投稿版源**，657 行）
- 工作区资产基准：`scenarios/original/`（**已核：自 `e41abb1` 起零改动**）

> **判定符号**
> `MATCH` = 论文与工作区一致，可原样保留 ·
> `MISMATCH` = 两者冲突，**必须动** ·
> `NOT VERIFIABLE` = 工作区里没有能证伪/证明的东西，**不能写死**

> **本文档不自行选择解决方案**：每个 `MISMATCH` 只给出"按工作区口径应改成什么"的方向，
> 具体改哪一边由作者定（见 §10）。

---

## 0.1 作者更正（2026-11-02）——**本节优先，覆盖下文判定**

作者确认：**论文表述与 `scenarios/original/` 里的文件是吻合的。"有可能是你的问题"成立。**
原先 5 条 `MISMATCH` 的正确解释是：**文件是基座配置，实际实验由运行时的命令行/脚本覆盖**，
而不是"论文写错"或"文件错"。据此把 5 条**降级为"待运行侧证据闭合"**：

| 原判 MISMATCH | 重新解释（假设） | 闭合所需证据 | 现在的状态 |
|---|---|---|---|
| **C1** 步长 0.1 s vs `step-length=1` | `cross.sumocfg` 是**基座模板**（其三个输入还指向 `~/Downloads/sumo_rl_demo/`，明显是遗留样版），实跑用 `--step-length 0.1` 覆盖 | **原始运行命令**，或一个显式 0.1 s 的运行配置 | 待闭合 |
| **D2** Table II（4 相 20/40/常绿）vs net 里 2×42 s | net 里的 `tlLogic` 是 **netconvert 生成的默认程序**；实跑配时由控制脚本经 TraCI 下发 | **信号控制脚本**，或 `tls*.add.xml` | 待闭合 |
| **B1** 1.5 m vs `minGap=3.0` | 1.5 m 很可能是**自采的安全间隔判据 / 规划器安全半径（disk 模型 ρ）**，不是 SUMO 的 `minGap` | **分析脚本里的阈值定义** | 待闭合 |
| **B2** "SUMO 默认" vs 显式 IDM 参数 | "default" 指"用 SUMO **内建**跟驰模型（IDM），未自写动力学"，而非"参数取默认值" | 措辞层面即可闭合（建议把参数列出来） | 待闭合（可写作解决） |
| **A4** `routes.rou.xml` 轻载 vs Table I | 它是**未乘 ×10 的遗留样例**：100×10 = 1000 veh/1000 s = 3600 veh/h ÷ 3 lane = **1200 = MaxD** ✓；**×10 口径下与 Table I 完全吻合** | 说明性文字即可 | 可写作解决 |

> **结论修正：目前没有任何一条"论文与文件真正冲突"的证据。**
> 缺的是**运行侧的可追溯记录**。这正是"复现原来的实验环境"要产出东西。


---

## 1. 判定汇总

| 组 | 条目数 | MATCH | MISMATCH | NOT VERIFIABLE | 随 C1 而定 |
|---|---|---|---|---|---|
| A 交通需求与转向比 | 6 | 4 | 1 | 1 | 0 |
| B 车辆与动力学 | 4 | 2 | **2** | 0 | 0 |
| C 时间与执行 | 4 | 1 | **1** | 0 | 2 |
| D 路网与信号 | 3 | 1 | **1** | 1 | 0 |
| E 指标定义 | 3 | 1 | 0 | 2 | 0 |
| F 实验矩阵与种子 | 3 | 1 | 0 | 2 | 0 |
| G 安全声明 | 2 | 0 | 0 | 2 | 0 |
| **合计** | **25** | **10** | **5** | **8** | **2** |

**5 条 MISMATCH 就是论文必须落笔的地方**：A4、B1、B2、C1、D2。
另有 C2、C4 两条**跟随 C1 的决定而变**（0.4 s 刷新与 10000 步/2500 次查询都只在 0.1 s 下自洽）。

---

## 2. A 组 · 交通需求与转向比

| ID | 论文陈述（行号） | 工作区证据 | 判定 | 按工作区口径应改为 |
|---|---|---|---|---|
| **A1** | "three isolated four-leg intersections … two-way roads with **4, 6, and 8 lanes**"（L99） | `cross1=2`、`cross2=2`、`cross3=3`、`cross4=4` 车道/进口；`tls2/3/4 = 2/3/4` | **NOT VERIFIABLE** | 若"4/6/8"指**双向总数**，则"每进口 2/3/4"，网络应为 `cross1`(或`cross2`)/`cross3`/`cross4`。**`cross1` 与 `cross2` 都是 2 车道 → 二义，须作者指定** |
| **A2** | Table I：L&R = 240/300/384/480/600，S = 480/600/768/960/1200，单位 `veh/(h·lane)`（L107-119） | `scenarios/original/routes.txt` 5 行×3 列；**按 ×10 口径可算术复现**：3 车道列与 Table I 逐档精确吻合（HANDOFF §10.6） | **MATCH**（经作者口述的 ×10 口径 + 工作区内算术复核） | 保留数值；**但必须写清"×10"这层**（`routes.txt` 的数字是 1000 s 内数量的 1/10），否则读者复现不出 480 |
| **A3** | ΔT ~ N(3600/(n·d), 1)（Eq. (1)，L127） | 代入 Table I 自洽：n=3,d=480 → **2.5 s**；n=3,d=1200 → **1.0 s** | **MATCH** | 保留（论文内部自洽） |
| **A4** | 论文实验车流（隐含由 Eq.(1) 生成） | **唯一存在的 `routes.rou.xml` 是 `departInterval="normal(10, 1.0)"`、直行 `number=100`、转向 `number=50`** → 与 Eq.(1) 任何一档都不符，实际密度 ≈ MaxD 的 1/10 | **MISMATCH** | 必须明确：`routes.rou.xml` 是**遗留的轻载样例**，**不是**论文实验车流。论文实验车流由 `scenarios/flows/` 的 15 组承担（HANDOFF §10.6） |
| **A5** | Left : Straight : Right = **1 : 2 : 1**（L122） | `routes.txt` 15 格全部满足"直行 : 单个转向 = 2 : 1"；`routes.rou.xml` 也满足 | **MATCH** | 保留 |
| **A6** | 高斯发车、`departPos/departSpeed` 随机（L124） | `departPos="random" departSpeed="random"` ✓ | **MATCH** | 保留；仅需注意属性名为 `departInterval`（SUMO 1.12 是否仍接受**待实测**，可能需写 `period`） |

---

## 3. B 组 · 车辆与动力学

| ID | 论文陈述（行号） | 工作区证据 | 判定 | 按工作区口径应改为 |
|---|---|---|---|---|
| **B1** | "a **minimum inter-vehicle gap of 1.5 meters** was enforced; violations of this threshold were recorded as potential collisions"（L135） | `types.typ.xml`: `minGap="3.0"` | **MISMATCH** | **改为 3.0 m**。"以 1.5 m 阈值判定潜在碰撞"在工作区**没有任何对应实现** → 该句须删或改为"使用 SUMO 自带碰撞检测"（见 G1） |
| **B2** | "All remaining vehicle dynamics parameters … were governed by **SUMO's default** microscopic traffic models"（L135） | `types.typ.xml` **显式**设定：`carFollowingModel=IDM`、`accel=1.0`、`decel=4.5`、`sigma=0.5`、`tau=2.0`、`length=5.0`、`maxSpeed=13.9` | **MISMATCH** | 不能说"默认"，应**列出这组显式参数**。这条同时强化 R2-3（运动学可行性）的可信度 |
| **B3** | 限速 50 km/h（13.9 m/s）（L135） | 全部进口 lane `speed=13.9`；`types` `maxSpeed=13.9` | **MATCH** | 保留 |
| **B4** | 乘用车 | `vClass=passenger`、`length=5.0`、`IDM` | **MATCH** | 可把 `length=5.0`、`IDM` 写进正文 |

---

## 4. C 组 · 时间与执行

| ID | 论文陈述（行号） | 工作区证据 | 判定 | 按工作区口径应改为 |
|---|---|---|---|---|
| **C1** | 仿真步长 **0.1 s**（L404、L411、L442） | `cross.sumocfg` `step-length="1"` | **MISMATCH（最硬）** | **两条路，必须选一条**：<br>①论文改成 1 s → 但"每 4 步刷新"就变成 4 s，与 400 ms 冲突，**等于改方法**；<br>②**新增一个可追溯的 0.1 s 运行配置**（`scenarios/` 下新建，**不动原 `cross.sumocfg`**），使论文的 0.1 s 在工作区内自证。<br>**建议 ②**（不改结论、不改方法），但新建文件需授权 |
| **C2** | 每 4 个仿真步做一次规划 = **0.4 s** 刷新（L388、L607） | 仅在 0.1 s 下自洽（4×0.1=0.4） | **随 C1 而定** | 同 C1 |
| **C3** | 仿真时长 **1000 s**（L491） | `cross.sumocfg` `end=1000` ✓；`routes.rou.xml` `end=1000` ✓ | **MATCH** | 保留 |
| **C4** | "10,000-step simulation … 2500 planning queries"（L607） | 10000×0.1 = 1000 s ✓；2500×4 = 10000 ✓ | **内部自洽（依赖 0.1 s）** | 同 C1 |

---

## 5. D 组 · 路网与信号

| ID | 论文陈述（行号） | 工作区证据 | 判定 | 按工作区口径应改为 |
|---|---|---|---|---|
| **D1** | 无信号交叉口；中心为无管制（L516） | `cross*/` 的 `center` 类型 = `unregulated`，`tlLogic` 计数 = **0** | **MATCH** | 保留 |
| **D2** | Table II：**4 相**，Left **20 s** / Straight **40 s** / Right **"Always Green"**（L495-506）；正文称 four-phase（L493） | `tls2/3/4.net.xml` 各有 **1 个 `tlLogic`、只有 2 个相位、每相位 42 s**，状态串 `GGGggrrrrr…` / `GGGGggrrrrrr…`，**不存在"右转常绿"** | **MISMATCH** | 二选一：<br>①Table II 是**实跑配时** → 工作区里没有对应物，需重建信号程序（新建，不改原 net）；<br>②Table II 是**代表性定时方案** → 措辞必须改（"a representative fixed-time plan"），并把 "Always Green" 改为按规则说明（右转在不妨碍被放行车流时通行），不能写成信号相位 |
| **D3** | 右转为何"常绿"不撞车（R1 追问，见 `reviewer-issue-matrix` R1-F3） | 工作区 tls 网络无任何右转让行/常绿实现 | **NOT VERIFIABLE** | 需作者裁决（与 D2 同一决策） |

---

## 6. E 组 · 指标定义

| ID | 论文陈述（行号） | 工作区证据 | 判定 | 按工作区口径应改为 |
|---|---|---|---|---|
| **E1** | `TimeLoss_i = T_actual,i − d_i / v_max,i`（Eq. (2)，L148） | 工作区**无任何指标计算脚本**；该式与 SUMO `tripinfo` 的 `timeLoss` **不是同一算法** | **NOT VERIFIABLE** | 必须写清是"SUMO 原生 `timeLoss`"还是"自定义公式"；两者数值不可混用 |
| **E2** | 每个 logging step 对**当前活跃车辆**求平均（Eq. (3)，L152） | 这是**瞬时截面平均**，不是逐车 trip 平均；SUMO 不直接输出该量 | **NOT VERIFIABLE（语义需澄清）** | **必须写死口径**：截面平均 vs 逐车平均。这直接决定 R2-6（sqrt 轴/物理量级）怎么答 |
| **E3** | 平均速度 = 当前活跃车辆瞬时速度均值（Eq. (5)，L159） | 可由 TraCI 逐步读取，语义自洽 | **MATCH（可实现）** | 保留 |

---

## 7. F 组 · 实验矩阵与种子

| ID | 论文陈述（行号） | 工作区证据 | 判定 | 按工作区口径应改为 |
|---|---|---|---|---|
| **F1** | 3 交叉口 × 5 密度 × 5 方法 = **75** configs（L491） | 算术自洽 | **MATCH（算术）** | 保留 |
| **F2** | 每个配置 **30 个独立随机种子**；DSIP 共 **450** runs（L491、L583） | **作者已提供（2026-11-02）：第一个 seed = 81890，连续向上数 30 个 → `81890 … 81919`**；450 = 3×5×30 算术自洽。注：`routes.rou.xml` 的 12 个 flow 级 seed（82339–82350）只用于车流生成，与本组实验 seed 是两套 | **MATCH（seed 列表已确认）** | 把 `81890–81919` 写进论文与实验配置；并说明"同号 seed 不保证不同实现间同随机流"（`AGENTS.md` §7.5） |
| **F3** | "over **2 million** planned vehicle passages"（L583） | 工作区无任何计数记录；15 组 flows 的车数可算，但与 450 runs 的对应关系**无从建立** | **NOT VERIFIABLE** | 要么用工作区 flows 重算并给出算式，要么删掉这个量级声明 |

---

## 8. G 组 · 安全声明

| ID | 论文陈述（行号） | 工作区证据 | 判定 | 按工作区口径应改为 |
|---|---|---|---|---|
| **G1** | "Across all **450 DSIP runs** … **no collision warnings** were observed"（L583） | 工作区**没有任何安全监控实现**；`collision.check-junctions` 未启用；且已实测：**无控制**条件下 15 组 flows 全部在 100 s 内出现 SUMO 碰撞，**100% 发生在出口车道汇流**（HANDOFF §10.4 #10） | **NOT VERIFIABLE（且有反证风险）** | 必须写死检测手段与实际配置（`--collision.action`、`--collision.check-junctions`、是否含出口汇流）。**在补齐检测前，"零碰撞"不能作为结论** |
| **G2** | "Only **three** instances of abrupt deceleration events"（L583） | 无实现、无日志 | **NOT VERIFIABLE** | 同上；且这正是 R2-3 要求补的统计，将来应与运动学统计合并交付 |

---

## 9. 结论：论文必须动笔的 5 处（按风险排序）

| 序 | 条目 | 论文现在写的 | 工作区实际 | 风险 |
|---|---|---|---|---|
| 1 | **C1** 步长 | 0.1 s | `step-length=1` | **最高**：牵动 400 ms 刷新、10000 步、2500 次查询、0.4 s 规划周期 **四处** |
| 2 | **D2** Table II 配时 | 4 相 20/40/Always Green | 2 相 ×42 s，无右转常绿 | **高**：同时是 R1 的追问点 |
| 3 | **B1** 最小车距 | 1.5 m | 3.0 m | 中：一行，但牵连"潜在碰撞"的定义 |
| 4 | **B2** 动力学参数 | "SUMO 默认" | 显式 IDM 一组参数 | 中：改写后可反过来支撑 R2-3 |
| 5 | **A4** 车流文件定位 | 隐含由 Eq.(1) 生成 | 现存 `routes.rou.xml` 是**轻载遗留样例** | 中：不写清会导致"复现不出 Table I" |

> 另外 8 条 `NOT VERIFIABLE` 里，**E1/E2（指标口径）** 必须尽快定，
> 因为它们同时决定 R2-6（sqrt 轴/物理量级）的答复方式；
> **F2（30 seeds）** 与 **G1（零碰撞）** 则必须在写作前拿到真实依据，否则只能降级表述。

---

## 10. 今天能落地的事

| 序 | 事项 | 依赖 | 产出 |
|---|---|---|---|
| 1 | **本一致性表**（已完成） | 无 | `docs/audits/paper-workspace-consistency.md` |
| 2 | 资产分层表独立成文（内容已在 `reviewer-issue-matrix` §6.5） | 无 | `docs/audits/asset-layers.md` |
| 3 | **FCFS 参数决策单**：把 `HANDOFF.md` §10.7 的 10 个阻断项做成"候选方案 + 勾选" | 无（只写方案，不跑实验） | `docs/decisions/fcfs-parameters.md` |
| 4 | 0.1 s 运行配置（`scenarios/` 下新建，**不动原 cfg**） | **需授权（C1 选②）** | 新 `.sumocfg` + 一条可复现命令 |

**需要你一句话的（按阻断程度）**

| # | 问题 | 为什么现在就要 |
|---|---|---|
| C1 | 0.1 s 走"①改论文"还是"②新增一个 0.1 s 的可追溯运行配置"？ | 牵动论文 4 处数字；也是后续所有实验的底座 |
| D2 | Table II 是**实跑配时**还是**代表性方案**？ | 直接决定 R1 右转那条怎么答 |
| A1 | 论文的 4 车道对应 `cross1` 还是 `cross2`？（两者都是每进口 2 车道） | 决定实验矩阵用哪个 net |
| F2 | 30 个 seeds 从哪来，能否给一份清单？ | 决定"30 seeds"能不能继续写 |
| B1/B2 | 确认按工作区口径改（**3.0 m**、列出显式 IDM 参数）？ | 一行改动，但影响 R2-3 的可信度 |

