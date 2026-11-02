# 审稿意见追溯矩阵（EIC + R1 + R2）

- 建立日期：**2026-11-02**
- 状态：**AUDIT ONLY（只登记，不改正文、不改实验）**
- 材料来源：`paper/reviews/`（原文由 `.gitignore` 排除，不入库；纯文本抽取件放在
  `paper/reviews/_extracted/`，同样不入库）
- **本文件不修改 `AGENTS.md` §2 / §7.8 与 `docs/HANDOFF.md` 的优先级顺序。**
  它只做两件事：(1) 建立"评审要求 → 工作项 → 证据状态"的可追溯映射；
  (2) 登记评审内容与既有计划之间的**差异（delta）**，供作者裁决。

---

## 0. 结论摘要（先看这 8 条）

| # | 结论 | 依据 |
|---|---|---|
| 1 | **两位审稿人都没有要求消融实验。** 现有"默认不做消融"的边界**无需改动**，可继续拒绝任何消融扩项。 | R1 全部意见、R2 全部 10 条均无 ablation 字样 |
| 2 | R1 给 **Reject**，三大主因：(a) 未比较 AIM 同类方法；(b) 相对 [41] 的贡献不清；(c) 转向比固定 1:2:1。R2 给 **Major Revision**，10 条。两条主线**高度重叠**在 (a)(b)。 | `paper/reviews/EIC and review 1.docx`、`review 2.pdf` |
| 3 | 论文里有一句**直接触发 R1-M1 与 R2#2 的原话**：把 AIM 对比说成 "orthogonal … prioritized in our future work"（`main.tex` L510），结论段又把 AIM 对比列为 future work。这句话必须删除/重写，成本极低、收益最大。 | `main.tex` L510、L614 |
| 4 | 我们计划的 FCFS **正好对应** R2#2 点名的 "reservation-based scheme"；但 **CCAM-DI 不属于**该条点名的 "optimization-based trajectory coordination"（MPC / 优先级-序列优化）。**第二个基线是否够用，需作者裁决。** | R2#2；`AGENTS.md` §2 |
| 5 | R2 有 **4 条只能靠"可运行的 DSIP"回答**：#3 运动学可行性、#4 CBS 计算时间/回落机制、#5 通信时延/抖动，以及 R1-M3 的变转向比（同样需要 DSIP）。当前 DSIP 源码/权重缺失 → **这 4 条是全局关键路径**。 | `HANDOFF.md` §3.1 |
| 6 | **作者确认（2026-11-02）：当前 Overleaf 快照即投稿版源**。因此 R2#8/#9/#10 **在投稿源中不成立**——全文只有 3 处 `\mathcal{H}_{b}`（L321/L325/L330），`\mathcal{H}_{k}` **一次也没有**；Eq. (23) 结构完整、括号配对；`\bar v` 已给出定义。R2 附件 PDF 的 Producer 是 **Aspose.PDF**（二次处理），其文本层把下标与逗号拉散成 `𝑏𝑖𝑗,ℎ𝑐 𝑐𝑖𝑗,ℎ𝑐 ,𝜌𝑖𝑗 ,[ℎ𝑐 ― Δℎ,ℎ𝑐 + Δℎ]` → **高度可能是审稿端渲染/抽取假象**。答复应为"冷静、事实性"说明，**不要为此改公式**。 | 作者口述；`main.tex` L321/325/330、L359-368、L405-411；`pdfinfo 'review 2.pdf'` |
| 7 | R1 的右转质疑**无法靠文案解释解决**：Table II 写 "Right Turn = Always Green"，而工作区 `tls{2,3,4}.net.xml` 的真实 `tlLogic` 只有 **2 个 42 s 相位、无"右转常绿"**。两者不一致，必须先向作者确认历史实验用的是哪套配时。 | `scenarios/original/tls*.net.xml`；`main.tex` L495-506 |
| 8 | 期限：EIC 给出 **90 天**。R2 附件 PDF 生成时间 2026-10-25，据此粗估截止 ≈ **2027-01-23**（**须以投稿系统决定日期为准，本文件不认定**）。 | EIC 信正文；`pdfinfo 'review 2.pdf'` |

---

## 1. 决定与期限

| 项 | 内容 | 证据 |
|---|---|---|
| EIC | Simona Sacone；**Revise & Resubmit**，90 天内提交，否则按新稿处理 | EIC 信 |
| AE/Editor | "There are many comments provided by the two reviewers. Please try to address them before resubmitting." —— 无独立技术意见 | EIC 信末 |
| 篇幅 | EIC 建议 **REGULAR PAPER ≈ 10 Transactions pages（含 biographies）**；由 AE 最终判定 Regular/Short | EIC 信 |
| R1 | Recommendation **Reject**；Summary **Poor**；Organization 4 / Clarity 4 / Length **2** / References **1** / Correctness 3 / Significance 2 / Originality 3 / Contribution 2 | R1 |
| R2 | Recommendation **Major Revision for a New Review**；Summary **Good**；Organization 3 / Clarity 3 / Length 4 / References 3 / Correctness 3 / Significance 4 / Originality 4 / Contribution 4 | R2 |
| 新增指定文献 | Klimke, Mertens, Völz, Buchholz, "A Real-World Evaluation of Two Cooperative Intersection Management Approaches," IEEE ITS Magazine, DOI 10.1109/MITS.2025.3643199 | R1 参考文献栏 |

> 注意幅度差异：R1 是"拒稿级"，R2 是"可救的"。**R1 的 3 条 major 应全部当作必答项。**

---

## 2. R1 意见矩阵

### 2.1 Major issues

| ID | 审稿人原话要点 | 论文位置 | 我们能做什么 | 需要什么证据 | 状态 |
|---|---|---|---|---|---|
| **R1-M1** | 作者似乎不了解 SOTA：无信号交叉口有经典优化与 RL 两条线，甚至在混合交通中做过评估；**只和信号灯比不公平**，必须与这些方法及其结果比较 | 引言 L34-41；Related Work L73-87；**L510 那句 "orthogonal … future work"** | ①重写 L510（删除推后/贬低措辞）；②Related Work 补 AIM 两条线 + Klimke 等；③实验补 AIM 基线（与 R2#2 合并处理） | 新增文献的准确书目与 DOI；基线实验结果 | **写作可立即启动**；实验受阻（见 §5） |
| **R1-M2** | 相对文献（尤其 **[41]**）的贡献不清；建议**先把已有单智能体扩散方法讲成 fundamentals**，再**明确列出多智能体版本扩展/改动了什么** | §Methodology L170-435；L194 "not trained from scratch"；L85-87 | 纯写作：Methodology 重构为 "Fundamentals（单智能体扩散 + CBS，来自 [41]）→ 我们的扩展（路网投影/车道软约束/边界裁剪/多车 CBS 约束生成/SUMO 执行接口）"。不改算法、不改公式含义 | 无（仅需作者确认"哪些是我们做的"） | **可立即启动** |
| **R1-M3** | 固定 Left:Straight:Right = 1:2:1 不够，应有**更多变的转向比**，才能真正证明适应性，也更贴近现实 | L122 明确写 "fixed ratio of 1:2:1" | 生成变转向比需求（同一总需求下不同 S 占比）；用 DSIP 跑敏感性 | **可运行的 DSIP** + 作者批准的比值集合 | **受阻（关键路径）** |

### 2.2 Further issues

| ID | 审稿人原话要点 | 论文位置 | 处理方式 | 状态 |
|---|---|---|---|---|
| **R1-F1** | 方法章节把通用方法与 SUMO 实现细节混在一起；应拆成"理论方法"+"实现子节" | §Methodology 全章，尤其 L176、L192、L388-392、L404-411 | 纯结构重排（`AGENTS.md` §5 第 2 条已列为允许动作）。**不改变任何公式或行为** | 可立即启动 |
| **R1-F2** | **CBS 缩写从未定义** | L41 现为 `CBS(confilct-based-search)`（**含拼写错误 confilct**） | 首次出现处规范定义为 "conflict-based search (CBS)" 并修拼写；同时说明 CBS 来自 [41]。**当前快照已有定义 → 投稿版可能没有**（见 §6.3） | 可立即修（低成本） |
| **R1-F3** | 为什么右转"常绿"？直行绿灯时右转也放行不会撞车吗？ | Table II `tabgreentimeallocation` L493-506 | **不能只靠解释**：需说明①中国大陆"右转在不妨碍被放行车辆/行人时可通行"的规则口径；②SUMO 中右转的实际让行/信号实现。**工作区 tls 网络的 tlLogic 与 Table II 不符（§6.2）** | **需作者裁决/授权** |
| **R1-F4** | Fig. 8 中车辆太小 | `evolution.png`（L597，`figure*`，`\linewidth`） | 放大/裁剪/加关键区插图。**属 HISTORICAL_FIGURE：只允许改呈现，不得改动图中内容**（`AGENTS.md` §6.0） | 可立即做（限呈现层） |

### 2.3 R1 评分的连带影响

- **Length = 2**（嫌长）：但同一份意见又要求补 Related Work、补 AIM 基线、拆方法章节
  → 篇幅**净增**。"压到 10 页"与"回答 R1"存在**结构性冲突**，只能把长表/大图/附加实验
  移入 **supplementary material**，正文留结论性图表。**该取舍需作者批准。**
- **References = 1**（嫌少）：Related Work 与 AIM 文献须**显著扩充**，不只是加 Klimke 一条。

---

## 3. R2 意见矩阵（10 条）

| ID | 审稿人要求 | 论文位置 | 我们的对应工作项 | 可行性 | 状态 |
|---|---|---|---|---|---|
| **R2-1** | 明确**独立算法贡献**：相对 [41]（多机器人扩散 + CBS）究竟创新在哪？是否针对交通特性做了 guidance 梯度 / 冲突解耦 / 规则建模的定制？ | L194；L85-87；§Methodology | 与 **R1-M2 合并**：一份 "Fundamentals vs. Our extensions" 的重构 | 纯写作 | **可立即启动** |
| **R2-2** | 只与信号灯比不足够；**至少 1–2 个经典 AIM / 优化类轨迹协调基线**（预留式 / MPC / 分布式-集中式优先级-序列优化） | L491（5 种方法全是信号灯类）；L510 | 现有计划 (a)：**FCFS**（= 预留式，✅ 对应）；**CCAM-DI**（≠ 优化类，⚠️ 不对应本条措辞） | FCFS 真实控制未完成（仅 Shadow）；CCAM-DI 未开始 | **进行中（关键路径）** + **需裁决** |
| **R2-3** | 质点圆盘模型 + TraCI 直接改位置 + 位移差分速度 → 无自行车模型/转向速率/加速度-加加速度约束；**"零碰撞"缺乏物理可行性支撑**。要求：讨论动力学限制对跟踪的影响，**或**给出运动学可行性统计（极端加速度/急转出现频次） | L192、L388-392、L405-411；L583 "no collision warnings" | **全新工作项（原计划无）**：从轨迹日志计算 a=max\|Δv/Δt\|、heading rate、曲率、jerk 分布；并改写安全声明 | **需要 DSIP 轨迹日志（已丢失）→ 需要可运行 DSIP** | **受阻** |
| **R2-4** | CBS 在高密度下指数爆炸；**400 ms 预算内无解时的回落/降级机制是什么？**是否出现死锁/查询超时？**建议给出 CBS 计算时间或搜索树深度的统计分布** | L388 "every four simulation steps"；L607 400 ms；**全文无 fallback 描述** | 现有计划 (c)：CBS 时延/超时统计 → **范围需扩大**为 (c1) 统计 + (c2) 回落机制说明 | 统计需 DSIP；回落机制说明可先写（但必须有真实机制，不能编） | **受阻（部分可写）** |
| **R2-5** | 假设零时延/零丢包/100% CAV 集中式；建议做 **50–100 ms 时延或抖动敏感性**，**或**彻底论述通信中断时的安全失效机制 | 摘要 "idealized"；L95；L614 | 现有计划 (d) 的**低成本替代**：写完整 failsafe 小节 +（若可跑）延迟注入实验 | 实验需 DSIP；论述可先写 | **半可行** |
| **R2-6** | Figs. 2–4 的 sqrt 轴会掩盖真实物理量级；要求在**图例或正文显著位置**给出**明确的物理单位换算**或更清晰标注 | L529；`tl2/3/4.png` | 改 caption + 正文说明 sqrt 轴与秒的换算；**不得改动图中数值**（HISTORICAL_FIGURE） | 无需数据 | **可立即做** |
| **R2-7** | Fig. 8 对比度低，难以分辨交互与排队；建议加**配色背景**或**关键冲突区放大插图** | L597 `evolution.png` | 与 **R1-F4 合并** | 需原始分辨率图件；不得伪造轨迹 | **可立即做（限呈现层）** |
| **R2-8** | Eq. (20) 的 `ℋ_k` 与 Eq. (19) 的 `ℋ_b` 下标不一致 | Eq. (19) L315-324 / Eq. (20) L326-337 | **投稿源即当前快照；`\mathcal{H}_{k}` 全文 0 次，3 处均为 `\mathcal{H}_{b}`** → 不成立 | 无需数据 | **NOT REPRODUCED（源侧已证）** |
| **R2-9** | Eq. (23) 存在排版/语法错误，缺少标点或运算符 | Eq. (23) L359-368 | **投稿源即当前快照；`\left(\mathbf{c}_{ij,h_c},\rho_{ij},[h_c-\Delta h,h_c+\Delta h]\right)` 结构完整** → 疑为审稿端 PDF 渲染假象 | 无需数据（如仍不放心，云端编译后目视一页即可） | **NOT REPRODUCED（源侧已证）** |
| **R2-10** | Eq. (24) 附近 `v` 的文字定义不完整（"where denotes the average speed" 缺符号） | Eq. (24) L405-411 | 投稿源已写 `\bar{v}` 并给出定义（"where `\bar{v}` denotes the average speed within one simulation step"）→ **原抱怨不成立**；但 `\bar v` 同时被 Eq. (5)（交叉口整体平均车速）与 Eq. (24)（单步位移导出速度）使用 → **真实存在符号重载**，可顺手改为 `v^{\mathrm{step}}_i` | 无需数据 | **原项不成立；符号重载可修（可选）** |

---

## 4. 覆盖度对照：现有计划 vs 评审要求

| 评审要求 | 现有计划中的对应项 | 覆盖度 | 说明 |
|---|---|---|---|
| R1-M1 / R2-2 与 AIM 同类比较 | §7.8(a) FCFS + CCAM-DI | **部分** | FCFS ✅ 命中"预留式"；CCAM-DI ⚠️ 不属"优化类"；R2 要 **1–2 个** |
| R1-M3 变转向比 | §7.8(b) | **形式覆盖、实质未决** | 原文措辞是"仅当重建验证通过后"；评审已把它变成 **major 必答项** → 实质优先级上升 |
| R2-4 CBS 时延 | §7.8(c) | **部分** | 原计划只有"时延/超时统计"，缺 **回落/降级机制** 与 **树深度分布** |
| R2-5 V2X 时延 | §7.8(d)（标注 optional） | **部分** | 评审给了"论述 failsafe"这条低成本路径 → 可不必真跑实验 |
| R2-3 运动学可行性 | **无** | **缺** | 全新条目 |
| R1-M2 / R2-1 贡献澄清 | §5 第 3 条（clarify relation to MMD）已有 | **覆盖** | 需按"fundamentals → extensions"结构重写，比原计划更彻底 |
| R1-F1 方法/实现拆分 | §5 第 2 条已有 | **覆盖** | — |
| R1-F3 右转常绿 | §4.2 已列为审计项（要求"验证 SUMO 信号/让行规则支持该解释"） | **覆盖但已证伪** | 工作区 tls 网络与 Table II 不符（§6.2） |
| R1-F4 / R2-7 Fig. 8 | §6.2 第 1 条已有 | **覆盖** | 只允许呈现层改动 |
| R2-6 sqrt 轴 | §6.4 第 4 条已有 | **覆盖** | — |
| R2-8/9/10 公式 | §4.2 已列为审计项 | **覆盖** | 结论与预期相反：**投稿源里本就正确**，属审稿端渲染/抽取假象 |
| R1 参考文献不足（score 1） | 未单列 | **缺** | 需专门的文献扩充任务，不只是加 Klimke |

---

## 5. 差异（delta）清单 —— "目标需要调整"的地方

> 再次声明：以下**不修改** `AGENTS.md` §2/§7.8 与 `HANDOFF.md` 的优先级文字；
> 这里只把"评审实际要求"与"计划里的措辞"之间的落差摊开。

| Δ | 差异 | 影响 |
|---|---|---|
| **Δ1** | 变转向比（§7.8(b)）在计划里是"重建验证通过**之后**才做"，但在评审里是 **R1 的 major**。二者都指向"必须能跑 DSIP"。 | **DSIP 可运行性从"次要"实质上升为全局关键路径**，但明面上的优先级顺序不变 |
| **Δ2** | (c) 只写了"时延/超时统计"；R2-4 还要 **回落/降级机制** 与 **搜索树深度分布** | 该项工作量增加，且"回落机制"在没有源码时**不可编造** |
| **Δ3** | **运动学可行性统计（R2-3）完全不在计划里** | 需新增工作项；且它同时要求**改写"零碰撞"措辞**（属 `AGENTS.md` §8 允许的口径修正） |
| **Δ4** | R2-2 要 "1–2" 个；FCFS 只满足"预留式"，CCAM-DI 不在其列举类别内 | **第二个基线选型需作者裁决**（见 §8 Q2） |
| **Δ5** | (d) 标了 optional；R2-5 允许"论述 failsafe"替代实验 | (d) 可降级为**纯写作**，风险可控 |
| **Δ6** | 论文 L510 与结论段主动把 AIM 对比推给 future work | **这是给审稿人的"口供"**，必须删；删完还要有实验顶上，否则更被动 |
| **Δ7** | R2-8/9/10 在投稿源中**不成立**（作者已确认快照=投稿版；`\mathcal{H}_{k}` 0 命中） | **这三条的"答复"比"修改"更重要**：改成冷静的事实性说明；只顺手修 `\bar v` 的符号重载 |
| **Δ8** | Table II 的 "Always Green" 与工作区 `tlLogic` 冲突 | R1-F3 从"文案问题"升级为"**证据缺口**"，需作者裁决 |

---

## 6. 工作区内证据核验（只写可证的）

### 6.1 论文侧（`paper/submitted/overleaf/…/main.tex`，657 行）

| 事实 | 位置 | 与评审的关系 |
|---|---|---|
| 实验只有 **5 种方法**：DSIP + fixed-time + MP-Light + CoLight + AttentionLight，**全部是信号灯类** | L491 | R2-2 / R1-M1 成立 |
| 明确写 "many pioneering AIM methods lack publicly available code …orthogonal to this paradigm-level evaluation and are **prioritized in our future work**" | L510 | **这是最需要删改的一句** |
| 结论段同样把 AIM 对比列为 future work | L614 | 同上 |
| 转向比明写 "fixed ratio of 1:2:1" | L122 | R1-M3 成立 |
| 车辆被表示为"planar position with a safety radius"，并且"moved to target position through TraCI" | L314、L392 | R2-3 成立 |
| 全文**没有** CBS 超时/回落/降级描述；只有 "400-ms planning refresh interval" | L388、L607 | R2-4 成立 |
| 安全声明："no collision warnings were observed under the idealized SUMO execution setting" + "over 2 million planned vehicle passages" | L583 | R2-3 的靶子；措辞已部分对冲（"idealized"），但仍需强化 |
| Eq. (19)/(20) 均为 `\mathcal{H}_{b}` | L315-337 | R2-8 **在快照中不成立** |
| Eq. (23) 结构完整、括号配对 | L359-368 | R2-9 **在快照中不成立** |
| Eq. (24) 已定义 `\bar v = sqrt(Δx²+Δy²)/Δt`；但 `\bar v` 在 Eq. (5) 已用于"交叉口平均车速" | L158-160 vs L405-411 | R2-10 **部分成立**（符号冲突） |
| 正文写 "minimum inter-vehicle gap of **1.5 meters**"；并称其余动力学参数"governed by SUMO's default" | L135 | 与工作区 `types.typ.xml`（`minGap=3.0`、IDM `accel=1.0/decel=4.5/sigma=0.5/tau=2.0`，**非默认值**）**不一致** → 与 R2-3 同源，必须修 |
| 正文写仿真步长 **0.1 s**；工作区 `cross.sumocfg` 写 `step-length=1` | L404 vs `scenarios/original/cross.sumocfg` | 与 R2-3/R2-4 相关；属"投稿口径 vs 现存资产"不一致，需作者确认 |

### 6.2 信号配时侧

| 事实 | 证据 |
|---|---|
| Table II：4 相 / Left 20 s / Straight 40 s / **Right "Always Green"** | `main.tex` L495-506 |
| 正文称"four-phase signal scheme"、green 由 Webster/HCM 计算 | L493 |
| 工作区 `tls2/tls3/tls4.net.xml` 的 `tlLogic` **各自只有 2 个相位、每相位 42 s**，状态串为 `GGGggrrrrr…` 型，**不存在"右转常绿"相位** | `scenarios/original/tls{2,3,4}.net.xml` |
| ⇒ **Table II 的配时在工作区内无对应物** | 结论：R1-F3 不能靠文案解释，需作者说明历史实验真正使用的信号程序（或承认 Table II 是"具有代表性的定时方案"而非实际运行配置） |

### 6.3 快照 vs 投稿版的一致性（**已由作者澄清**）

- **作者确认（2026-11-02）：当前 Overleaf 快照就是投稿版源。** 因此不存在"快照晚于投稿版"的问题，
  先前基于 R1/R2 描述做的反向推断**作废**。
- 由此得到三条硬结论（**都是"审稿人所述与投稿源不符"**）：
  1. **R1-F2**：`CBS` 在 L41 **是有定义的** `CBS(confilct-based-search)`；问题在于
     **拼写错（confilct）且格式像注记**，所以审稿人认为"从未定义"。→ 修拼写 + 写成规范定义即可。
  2. **R2-8**：`\mathcal{H}_{k}` **全文不存在**（grep 0 命中），3 处全为 `\mathcal{H}_{b}`。→ 不成立。
  3. **R2-9 / R2-10**：Eq. (23) 结构完整；Eq. (24) 的 `\bar v` 有明确定义。
- **假象来源高度可疑**：R2 附件 `review 2.pdf` 的 Producer 是 **Aspose.PDF for Java 25.8**
  （二次转换产物），其文本层把下标与逗号拉散：
  `𝑏𝑖𝑗,ℎ𝑐 𝑐𝑖𝑗,ℎ𝑐 ,𝜌𝑖𝑗 ,[ℎ𝑐 ― Δℎ,ℎ𝑐 + Δℎ]`。这正是"看起来缺标点/缺符号"的典型 PDF 抽取现象。
- **答复策略**（`AGENTS.md` §4.2 的"冷静、事实性"路线）：
  不辩解、不为此改公式；说明"经核对投稿源与编译版本，Eq. (20)/(23)/(24) 的记号与结构是完整的，
  疑为渲染/转换差异"；并**顺手做两处无害加固**（`\mathcal{H}` 记号在全文中统一说明一次；
  `\bar v` 的符号重载改掉）——这样即使审稿人再查，也只会更清楚。
- **仍需一次云端编译确认**：投稿源在实际 LaTeX 下的页数与这三条公式的最终渲染。作者自行在云端编译。

### 6.4 环境侧

- 本机**无 LaTeX 工具链**（`pdflatex / xelatex / latexmk / bibtex / biber / tectonic` 全部不存在）。
- **作者决定：在云端（Overleaf）编译。** → 本地不安装 texlive，页数与渲染由作者侧确认；
  本仓库只负责提供可编译的源与改动清单。
- SUMO/TraCI 通路已验证（见 `HANDOFF.md` §10）；FCFS 仅 Shadow Mode。

### 6.5 工作区漂移（"与投稿时不一样"的部分）—— 已核验

`git log -- scenarios/original paper/submitted` 只有 `e41abb1`（初始化）一条；
`git diff e41abb1 -- scenarios/original paper/submitted` **为空**
⇒ **投稿版资产（7 个 net、1 个 sumocfg、1 个 rou、1 个 typ、nod/edg、`main.tex`、`refs.bib`、全部图件）
自导入后一个字都没被改过。**

因此"与投稿时不一样"的只是**本轮新增的工作资产**，可安全地按来源分层：

| 层 | 路径 | Git 状态 | 说明 |
|---|---|---|---|
| **投稿版原始资产** | `scenarios/original/`（除 `routes.txt`）、`paper/submitted/` | 已跟踪、**零改动** | 引用/复现的唯一基线，不可改 |
| **本轮新增（已跟踪）** | `baselines/fcfs_sumo/`（11 文件）、`scenarios/smoke/`（3 文件）、`docs/HANDOFF.md`、`docs/env/`、`third_party/README.md`、`AGENTS.md`、`.gitignore` | 已提交 | 本轮产物 |
| **本轮新增（未跟踪）** | `scenarios/flows/`（15 个 `lanes*_density*.rou.xml` + `generate_flows.py` + `validate_flows.py` + `README.md`）、`scenarios/original/routes.txt`、`docs/audits/reviewer-issue-matrix.md` | 未入库 | `flows/` 是否入库需作者决定；`routes.txt` 按作者要求保持未跟踪 |
| **作废报告** | `docs/audits/{scenario-provenance,aim-baseline-feasibility,next-phase-minimal-plan}.md`、`workspace-inventory.md` §8、`third_party/README.md` 外部部分、`docs/env/mmd-environment-audit.md` §4 | 已提交但**已声明失效** | 保留作历史记录，不得引用 |

> "整理"的最小动作（不涉及任何研究判断）：把上表做成 `docs/audits/asset-layers.md`，
> 或直接在 `HANDOFF.md` 的资产表里加"层"列。**本文件不代替 `HANDOFF.md`，也不改动其内容。**

---

## 7. 调整后的目标（分层，不改动既有优先级文字）

> 排序原则：**先用"零算力"的写作/呈现工作把确定能答的 6 条答掉**，
> 同时把"必须能跑 DSIP"的 4 条单独隔离成一条关键路径，**尽早暴露风险**。

### P0 —— 现在就能做，不依赖任何实验（建议本阶段唯一重点）

| 项 | 覆盖评审条目 | 说明 |
|---|---|---|
| 删除并重写 `main.tex` L510 + 结论段的 AIM 措辞 | R1-M1（触发点）、R2-2（触发点） | 不新增任何数据，先止血 |
| Methodology 重构：Fundamentals（[41] 的单智能体扩散 + CBS）→ Our extensions | **R1-M2、R2-1** | 一次改动同时满足两条 major |
| 方法与实现拆分（理论章节 / "SUMO 实现"子节） | R1-F1 | 纯结构 |
| CBS 首次出现处规范定义 + 修 `confilct` 拼写 | R1-F2 | 一行 |
| Eq. (24) 记号去冲突（`\bar v` → 步骤速度专用符号） | R2-10 | 一行级 |
| Figs. 2–4 caption/正文补 sqrt 轴与秒的换算说明 | R2-6 | 不动图 |
| Fig. 8 放大/加冲突区插图（仅呈现层） | R1-F4、R2-7 | 不动内容 |
| Related Work 扩充（AIM 优化线 + RL 线 + Klimke DOI） | R1-M1、References=1 | 需作者确认可引用范围 |
| 统一"1.5 m vs 3.0 m minGap"、"0.1 s vs cfg 1 s"的表述 | R2-3 的连带项 | **需作者确认哪个是真值** |

### P1 —— 决定"能不能救"的实验（关键路径）

1. **FCFS 真实控制**（把 Shadow 升级为真正的预留式控制）→ 直接支撑 R2-2 的"预留式基线"。
2. **DSIP 可运行性**（重建）：**这是 4 条评审意见的唯一共同前提**。
   建议设一个**硬时间盒**（例如 4–6 周）；到期若达不到可运行+可验证状态，
   就明确转为"受限答复 + limitation"，并**立即告知作者**，而不是继续硬推。

### P2 —— 依赖 P1 的评审条目（按"性价比"排序）

| 顺序 | 项 | 覆盖 | 理由 |
|---|---|---|---|
| 1 | CBS 计算时间分布 + 超时/死锁计数 | R2-4 的一半 | 只需在既有 planner 里加计时与日志 |
| 2 | 变转向比敏感性 | **R1-M3** | major；但对 DSIP 要求最高（要重跑全矩阵子集） |
| 3 | 运动学可行性统计（a / 曲率 / heading rate / jerk） | **R2-3** | 需要逐 step 轨迹日志 |
| 4 | 时延/抖动注入（或降级为 failsafe 论述） | R2-5 | 可用论述替代，优先级最低 |

### P3 —— 篇幅与结构（等 P0 完成后）

- 先修正确性，再压页（`AGENTS.md` §5 顺序）。
- R1 嫌长、却要求加内容 → **必须与作者约定"正文 10 页 + supplementary"的分配**。
- 压缩收益点（待实测）：L521-525 与 L590-596 有明显重复论述；L34 引言偏长；
  750 词级的 Discussion 可精简；算法伪代码可移 supplementary。

---

## 8. 需要作者裁决 / 授权的问题（按阻断程度）

| # | 问题 | 为什么阻断 |
|---|---|---|
| ~~Q1~~ | ~~投稿版 PDF 在哪里？~~ | **已解决（2026-11-02）**：作者确认当前 Overleaf 快照即投稿版源。页数由作者云端编译后提供 |
| **Q2** | **第二个 AIM 基线选谁？** R2-2 点名"预留式 / MPC / 优先级-序列优化"。FCFS 命中第一条；CCAM-DI 不属其列举类别。 | 决定 §7.8(a) 是否需要调整（本文件无权调整） |
| **Q3** | **Table II 的信号配时是实际运行配置还是"代表性"方案？** 投稿版 `tls*.net.xml` 已核为**零改动**，其 `tlLogic` 与 Table II 明显不符。 | R1-F3 的答复只能二选一：解释规则 / 承认代表性并改措辞 |
| ~~Q4~~ | ~~R2-8/9/10 怎么答？~~ | **已定性**：源侧不成立 → 走"事实性说明 + 展示核对"路线，不辩解、不改公式 |
| **Q5** | 变转向比的**比值集合与总需求口径**（S 占比取哪几档？总需求固定 MedD 还是也扫密度？） | 决定实验矩阵规模与时间盒 |
| **Q6** | **1.5 m 还是 3.0 m 最小间距？0.1 s 还是 1 s 步长？** 论文写 1.5 m / 0.1 s；投稿版 `types.typ.xml` 是 `minGap=3.0`，`cross.sumocfg` 是 `step-length=1`。**两者都是投稿原样、未改动** → 属于论文与投稿资产之间的内部不一致，须作者定口径 | 直接影响 R2-3 的运动学统计口径与可信度 |
| **Q7** | 是否接受 **supplementary material** 承载附加实验与大图（换取正文 10 页）？ | 决定压缩策略是否可行 |
| ~~Q8~~ | ~~本机装 texlive？~~ | **已解决**：作者在云端编译，本地不装 |

---

## 9. 下一步（单一最小动作）

**（2026-11-02 更新）** Q1 已解决，因此 §9 从"要 PDF"改为**对投稿源本身做一轮零风险的事实性核对**，
为三条"不成立"意见准备好可展示的证据：

1. 作者在 Overleaf 编译**不改动的投稿源**，导出一份"当前编译版"PDF；
2. 在编译版里逐条目视 **Eq. (19)/(20)/(23)/(24)** 与 `CBS` 首次出现处；
3. 若渲染正常 → 在 response letter 里给出**页码 + 截图**，冷静说明"经核对，记号与结构完整"；
   若渲染确实异常 → 那就不是审稿人的问题，按 `AGENTS.md` §5 第 1 条修 LaTeX。

**在此之前不改正文。**（正文修改需作者授权。）

---

## 附录 A：材料与抽取方式（可复现）

```bash
# 1) docx → txt（本机无 python-docx，用 LibreOffice）
soffice --headless --convert-to txt:Text --outdir _extracted "EIC  and review 1.docx"

# 2) pdf → txt
pdftotext -layout "review 2.pdf" _extracted/review2.txt
pdfinfo "review 2.pdf"   # Pages: 2 / A4 / CreationDate: 2026-10-25
```

- 抽取件路径：`paper/reviews/_extracted/`（**不入库**，`paper/reviews/` 在 `.gitignore` 中被排除）
- 评审原文**未被修改**；本文件只做引用与映射。

