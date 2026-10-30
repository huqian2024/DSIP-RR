# 本地 Git 初始化记录

- 执行日期：2026-10-30
- 范围：仅在当前工作区根目录建立本地版本管理；**未**创建 GitHub 仓库、**未**添加 remote、**未** push、**未**要求任何登录。
- 未修改 Git 全局配置，未编造提交身份。

## 1. 初始化前状态

| 检查项 | 结果 |
|---|---|
| 当前目录是否已是 Git 仓库 | 否（`fatal: not a git repository`） |
| 是否位于其他仓库内部 | 否（父目录链上无 `.git`） |
| 工作区内嵌套仓库 | 无（`find . -name .git -type d` 仅命中新建的 `./.git`） |
| 已有 `.gitignore` | 有（312 B，内容较简，只覆盖 Python 缓存/少量 LaTeX 中间文件/`results/`/`paper/reviews/`） |
| Git 版本 | 2.34.1（支持 `git init -b main`） |
| Git 身份 | 全局 `user.name` / `user.email` 已存在；本地未设置 → 提交时回落到全局身份 |
| Git LFS | 已安装 3.6.1，**本阶段未启用**（无文件超过阈值，见 §5） |

## 2. 初始化命令

```
git init -b main
```

结果：`Initialized empty Git repository in <workspace>/.git/`，当前分支 = `main`。

## 3. `.gitignore` 策略

原则：**只忽略可再生 / 体积大 / 私人的内容**；论文源、SUMO 输入配置、论文图件一律入库。

| 类别 | 规则（要点） | 理由 |
|---|---|---|
| Python | `__pycache__/`、`*.py[cod]`、`*.so`、`.venv/`、`venv/`、`/env/`、`*.egg-info/`、`build/`、`dist/`、`.pytest_cache/` 等 | 缓存与虚拟环境可重建 |
| LaTeX | `*.aux *.fls *.fdb_latexmk *.synctex.gz *.blg *.toc *.lof *.lot *.out *.log *.bcf *.run.xml *.xdv *.nav *.snm *.vrb *.idx *.ind *.ilg`、`/paper/revision/build/` | 编译中间产物；**生成的 `.pdf` 保留** |
| 模型权重 | `*.pt *.pth *.ckpt *.safetensors *.onnx *.h5 *.pkl *.joblib` | 体积大，应由发布渠道管理 |
| SUMO / 实验输出 | `results/**/tripinfo*.xml`、`summary*`、`queue*`、`vehroute*`、`persons*`、`fcd*`、`emission*`、`stdout*/stderr*`、`experiments/**/runs/`、`**/*.fcd.xml`、`*.netstate*.xml`、`*.sumo.log`、`/tmp_sumo/` | 重跑即可再生；逐 step 轨迹体量大 |
| 上游第三方代码 | `third_party/*/`（保留 `third_party/README.md` 例外） | 以 "URL + 固定 commit" 记录，避免嵌套 `.git` 与仓库膨胀；确需入库时改用 submodule |
| 私人材料 | `paper/reviews/` | 未公开的编辑/审稿通信（AGENTS.md 第 8 节） |
| 编辑器/系统 | `.vscode/`、`.idea/`、`.DS_Store`、`Thumbs.db`、`*.swp`、`*~` | 个人 IDE 配置 |

**修正记录**：初稿中虚拟环境规则写作 `env/`，`git check-ignore` 显示它把 `docs/env/environment-audit.md` 也忽略了（gitignore 的目录规则会匹配任意层级同名目录）。已改为 `/env/`（仅根目录），复检通过。这说明"必须实测 check-ignore，不能只看规则字面"。

### 3.1 忽略规则实测

研究资产（**应不被忽略**，实测无输出）：

```
scenarios/original/cross.sumocfg
scenarios/original/routes.rou.xml
scenarios/original/cross3.net.xml
scenarios/original/types.typ.xml
paper/submitted/overleaf/…/main.tex
paper/submitted/overleaf/…/refs.bib
paper/submitted/overleaf/…/tl2.png
paper/submitted/overleaf/…/Qian_Hu.jpg
paper/submitted/overleaf/… (原始 zip)
AGENTS.md
docs/audits/workspace-inventory.md
docs/env/environment-audit.md
docs/env/mmd-environment-audit.md
```

可再生输出（**应被忽略**，实测命中）：

```
.gitignore:71:results/**/fcd*.xml      results/fcd_dump.xml
.gitignore:66:results/**/tripinfo*.xml results/tripinfo_run1.xml
results/aggregate_delay.csv            → 不忽略（聚合结果应入库）
```


## 4. 暂存与提交前核查

按要求**未**使用 `git add .`，而是逐项显式 `git add`：

```
git add AGENTS.md .gitignore \
        scenarios/original \
        paper/submitted/overleaf \
        docs/audits/workspace-inventory.md docs/env/environment-audit.md docs/env/mmd-environment-audit.md \
        baselines/.gitkeep evaluation/.gitkeep experiments/.gitkeep \
        results/.gitkeep src/.gitkeep third_party/.gitkeep paper/revision/.gitkeep
```

核查结果：

| 核查项 | 结果 |
|---|---|
| 暂存文件数 | 42（42 files changed, 3608 insertions） |
| 是否含 `paper/reviews/` 或 `.vscode/` | 否（`git ls-files \| grep -c` = 0） |
| 是否含仿真输出 / 模型权重 | 否 |
| 最大单文件 | Overleaf 原始 zip ≈ 6.5 MB（其余均 < 2 MB） |
| 仓库总体积（`.git`） | 14 MB |
| 凭证/令牌扫描（`ghp_`、`github_pat_`、`sk-…`、`BEGIN RSA`、`password =`、`overleaf…token`） | 仅命中 `AGENTS.md` 中的**策略说明文字**（"Do not disclose … Overleaf tokens"），非真实凭证 |
| 大文件阈值（>100 MB） | 无 → **不需要 Git LFS** |
| 私有绝对路径 | `scenarios/original/cross.sumocfg` 内含 `~/Downloads/sumo_rl_demo/…` 绝对路径。该文件是历史资产，按约束**不得修改**；因此保留原样入库，并在下方风险项记录 |

## 5. 初始提交

| 项目 | 值 |
|---|---|
| 分支 | `main` |
| commit | `e41abb1` (`e41abb11804fe5b6d7334446930a53abccef7188`) |
| 作者 | 取自**既有全局配置**（未修改、未伪造） |
| 提交时间 | 2026-10-30 16:39 (+08:00) |
| 提交摘要 | `chore: initialize DSIP-RR local repository` |
| 文件变更 | 42 files changed, 3608 insertions(+) |
| 工作区状态 | 干净（除被忽略的 `paper/reviews/`） |
| remote | 无 |

提交内容分组：

1. `AGENTS.md`、`.gitignore`（策略文件）
2. `paper/submitted/overleaf/`（15 个文件 + 原始 zip，逐字节未变）
3. `scenarios/original/`（14 个 SUMO 原始文件，md5 与本地原始文件一致）
4. `docs/env/`、`docs/audits/`（本阶段审计文档）
5. 6 个目标目录的 `.gitkeep`（`paper/revision/` 亦保留）

## 6. 风险与待决策问题

1. **`paper/reviews/` 被忽略**：审稿意见尚未提供，规则已排除该目录。若日后放入 EIC 信/审稿意见，它们不会进入版本库 —— 若希望"私有仓库内可追溯"，需要作者确认后把该目录从忽略列表移除（本阶段未改）。
2. **`cross.sumocfg` 内含私人绝对路径**：未来若把仓库公开，会泄露用户家目录名。建议在公开前用"新增包装 cfg + 记录原文件未改动"的方式处理，或先确认是否可改写该历史文件（本阶段严格遵守"不修改"）。
3. **Overleaf zip 与解压目录重复存储**：约 6.5 MB 冗余。保留理由是 zip 作为"冻结快照"的可校验副本；如需瘦身可后续移除，但应先在文档记录。
4. **无 remote / 无备份**：本地仓库当前是唯一版本库，且工作区本身可能是唯一资产副本。下一阶段建议先确认离线备份（外部磁盘或私有远端），但**本次不创建远端**。
5. **提交身份是全局配置**：若作者希望本仓库使用不同身份，应显式设置仓库级 `user.name/user.email`（本阶段未改，以免越权）。

## 7. 下一步（最小动作）

1. 补齐 `paper/reviews/`（EIC 信 + R1/R2 意见），决定是否纳入版本库。
2. 解决 LaTeX 工具链（安装 TeX Live 含 `IEEEtran`，或改用 Overleaf 编译）后才能做页数与编译审计。
3. 之后再进入 baseline 阶段：固定 SUMO/traci 版本组合、生成 5 个密度等级的 route 文件（需授权）、实现 FCFS 与 CCAM-DI 适配层。
