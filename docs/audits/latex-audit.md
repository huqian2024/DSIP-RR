# LaTeX 审计与小错修复记录（2026-11-14）

- 状态：**静态检查已完成；2 处确凿小错已修（仅在 `paper/revision/`）；其余项目故意不改，理由见 §4**
- 不可变基线：`paper/submitted/overleaf/DSIP_ A Dynamic Coordination Planner…/`（**本次未改动一个字节**）
- 可编辑副本：`paper/revision/`（由投稿快照 `cp -a` 生成，`main.tex` 原 sha256 = `06f7be44…`）
- 上位约束：`AGENTS.md` §1.1（保护投稿记录）、§4.2（审稿项逐条核验）、§5（小步、可复审的补丁）

---

## 1. 【已验证】环境限制

本机**无任何 LaTeX 工具链**（`pdflatex / xelatex / latexmk / bibtex / biber / tectonic` 均不存在）。
作者决定在 Overleaf 云端编译（`docs/audits/reviewer-issue-matrix.md` §6.4）。

⇒ 本轮**不能**给出页数、渲染截图、overfull box 清单。
本轮只做**不依赖编译器即可确证**的检查（交叉引用、文献键、图件存在性、明显的排版占位符），
并明确标注哪些结论必须由云端编译确认。

## 2. 【已验证】静态检查结果（可复跑）

| 检查 | 方法 | 结果 |
|---|---|---|
| `\label` 重复 | 正则计数 | **0 处重复**（33 个 label 全唯一） |
| `\ref`/`\eqref` 悬空 | 引用集合 − 定义集合 | **0 处悬空** |
| 未被引用的 label | 定义集合 − 引用集合 | 21 项，全部是**公式 label** 与 `fig:tl3`/`fig:as3`（通过 `\ref{fig:tl2}--\ref{fig:tl4}` 区间引用）⇒ **不是错误** |
| `\cite` 键缺失 | 引用键 − `refs.bib` 键 | **0 处缺失**（47 个引用键全部存在） |
| `refs.bib` 中未被引用的条目 | 差集 | 7 条（`erdmann1987, ericson2004, moradi2003, ross2011, shabestary2022, stentz1994, vannoy2008`）。BibTeX 会静默丢弃，**不会产生可见错误**；但也**不能**靠它们凑参考文献数量（R1 的 References=1） |
| `\includegraphics` 文件存在性 | 逐文件 `Path.exists()` | **0 处缺失**（8 个 png、5 个 jpg 全在） |
| 拼写/占位符扫描 | `confilct`/`TODO`/`FIXME`/`XXX`/`??`/`\ref{}` | **命中 1 处**：L41 `confilct` |

复跑脚本见 §6。

## 3. 【已修】2 处确凿小错（仅 `paper/revision/main.tex`）

### 3.1 R1-F2：`CBS` 缩写拼写错误 + 定义格式不规范（L41）

```diff
- ... combines learned single-agent trajectory priors with a
-     CBS(confilct-based-search)-based coordination layer ...
+ ... combines learned single-agent trajectory priors with a
+     conflict-based search (CBS) coordination layer ...
```

**依据**：R1 原话是"CBS 缩写从未定义"。核验结论：投稿源**有**定义，但
①拼写错（`confilct`），②写成 `CBS(...)` 注记式而非"全称 (缩写)"的首次定义格式，
所以审稿人读起来像没定义。修法即 R1 隐含要求的最小改动。**不改任何技术含义。**

**刻意未做**：在本句追加 `\cite{shaoul2025}`（CBS 来自 MMD [41]）。
理由：那属于 **R1-M2 / R2-1 的贡献边界**问题（P1 写作任务），
且会与"是否扩充 Related Work"一起决定，现在单独加 citing 会让编号与叙述先动一半。

### 3.2 IEEEtran 模板占位符残留在 `\markboth`（L20–21）

```diff
-\markboth{Journal of \LaTeX\ Class Files,~Vol.~14, No.~8, August~2021}%
-{Shell \MakeLowercase{\textit{et al.}}: Bare Demo of IEEEtran.cls for IEEE Journals}
+\markboth{Submitted to the IEEE Transactions on Intelligent Transportation Systems}%
+{Hu \MakeLowercase{\textit{et al.}}: DSIP: A Dynamic Coordination Planner for Signal-Free Intersections}
```

**这是模板 demo 的页眉，不是本文的页眉。** 投稿正文若保留它，页眉会印出
"Journal of LaTeX Class Files … Bare Demo of IEEEtran.cls"，属于明显的投稿事故。
改为"Submitted to …"是 IEEE 对投稿件的常规写法，**不虚构卷期号/年份**。

### 3.3 改动范围核验

`diff` 显示 `main.tex` **只有这 2 行**不同；`refs.bib` 与 8 个图件、5 位作者照片
`cmp` 全部 **byte-identical**。投稿快照 `paper/submitted/` **零改动**。

## 4. 【故意不改】审稿人提到、但本轮不动的地方

| 审稿项 | 现象 | 为什么本轮不改 |
|---|---|---|
| **R1-M1 / R2-2** | L510 把 AIM 对比说成 "orthogonal … prioritized in our future work"；L614 又把 AIM 对比列为 future work | **这是评价性/定位性陈述，不是小错。** 改成什么完全取决于 PSL 实验能否进正文：若进了，应写成"我们与一个优先级-序列优化基线对比"；若没进，删掉这句反而留下无法回答的空白。**必须等 PSL 结果确定后再改（P1 任务）** |
| **R2-8** Eq. (20) `\mathcal{H}_k` vs `\mathcal{H}_b` | 全文 `\mathcal{H}_{k}` **0 次**，3 处均为 `\mathcal{H}_{b}` | **不成立**（源侧已证）。按 §6.3 既定策略：回复"冷静、事实性",**不为此改公式** |
| **R2-9** Eq. (23) 缺标点 | `\left(\mathbf{c}_{ij,h_c},\rho_{ij},[h_c-\Delta h,h_c+\Delta h]\right)` 括号配对、逗号齐全 | **不成立**，疑为审稿端 Aspose.PDF 抽取假象。**不改** |
| **R2-10** Eq. (24) 缺符号 | L411 已写 "where $\bar{v}$ denotes the average speed within one simulation step" | **原抱怨不成立**。存在的真实问题是 `\bar v` 在 Eq. (4)/Eq. (5)/Eq. (24) 三处**语义不同**；改符号会让"审稿人指出的公式"被改动，观感更差 → **只登记，不修**（可选加固见 §5） |
| **R1-F3** Table II 右转 "Always Green" | 工作区 `tls{2,3,4}.net.xml` 的 `tlLogic` 只有 2 个 42 s 相位，**没有右转常绿相位** | **需作者裁决**：Table II 到底是"代表性定时方案"还是历史实跑配置。**不能靠改文案解释掉** |
| **论文 vs 工作区不一致** | L135 写 "minimum inter-vehicle gap of 1.5 m" + "其余动力学由 SUMO 默认值决定"；而工作区 `types.typ.xml` 是 `minGap=3.0`、IDM `accel=1.0/decel=4.5/sigma=0.5/tau=2.0`（**非默认**） | 这是**对历史实验参数的事实陈述**。按 `AGENTS.md` §1.1/§8，不得据新推测改写历史实验描述；**必须先问作者当时用的是什么** |
| **R1-F4 / R2-7** Fig. 8 车辆太小 / 对比度低 | `evolution.png` | 需原始高分辨率/矢量资产才能放大而不伪造内容。**本轮不动图件**（`AGENTS.md` §6.0） |
| **R2-6** Figs. 2–4 的 sqrt 轴 | L529 已用一句话解释 "square-root transformed to compress the vertical axis" | 可加强（caption 里给出 sqrt→秒 的读法），但涉及图注改写与图件核对，**留待 P1** |

## 5. 【可选】留给作者的加固建议（本轮未执行）

1. **`\bar v` 符号消歧**：Eq. (24) 改用 `v_i^{\mathrm{step}}` 之类，同时在 Eq. (4)
   下方注明 `\bar v` 是"整个交叉口所有在途车辆的平均瞬时速度"。
   好处：即使 R2 再查，记号也更清楚。风险：动了审稿人指名的公式。
2. **sqrt 轴的 caption**：在 Figs. 2–4 的 caption 里加一句
   "纵轴为 $\sqrt{\text{time loss}\,(\mathrm{s})}$，即图上刻度 $t$ 对应 $t^2$ 秒"。
   纯表述，不改图。
3. **7 条未被引用的 bib 条目**：要么在扩充 Related Work 时用上，要么删除，避免"参考文献虚胖"的观感。

## 6. 复跑静态检查

```bash
cd 'paper/revision'
python3 - <<'PY'
import re, pathlib
src = pathlib.Path('main.tex').read_text(encoding='utf-8')
bib = pathlib.Path('refs.bib').read_text(encoding='utf-8')
labels = re.findall(r'\\label\{([^}]+)\}', src)
refs   = re.findall(r'\\(?:eq)?ref\{([^}]+)\}', src)
print('labels', len(labels), 'unique', len(set(labels)))
print('dup', [l for l in set(labels) if labels.count(l) > 1])
print('dangling refs', sorted(set(refs) - set(labels)))
cites = {k.strip() for m in re.findall(r'\\cite\{([^}]+)\}', src) for k in m.split(',')}
keys  = set(re.findall(r'@\w+\{([^,]+),', bib))
print('missing bib keys', sorted(cites - keys))
print('uncited bib keys', sorted(keys - cites))
for f in re.findall(r'\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}', src):
    if not pathlib.Path(f).exists(): print('MISSING GRAPHIC', f)
PY
```

## 7. 仍需作者完成

1. **Overleaf 云端编译一次**，确认：页数、这两处改动后的页眉、Eq. (20)/(23)/(24) 的实际渲染。
2. 裁决 **Table II 右转"常绿"** 与 `tls{2,3,4}.net.xml`（2 相位 × 42 s）的矛盾。
3. 确认 L135 的 **1.5 m 车距 / "SUMO 默认动力学"** 与历史实验实际参数的关系。
4. 决定 L510 / L614 关于 AIM 对比的措辞 —— **等 PSL 结果确定后一起改**。

