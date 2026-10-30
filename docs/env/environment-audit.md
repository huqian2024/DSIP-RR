# 环境审计报告（DSIP-RR 初始化阶段）

- 采集日期：2026-10-30
- 采集方式：只读命令检查（`uname`、`lscpu`、`free`、`df`、`nvidia-smi`、`nvcc`、`conda`、`sumo`、`pip`、`git`、traci 短连接测试）
- 本阶段未安装、未升级、未卸载任何软件；未修改 `mmd` 环境；未运行训练、推理或大规模仿真。
- 路径统一以 `~` 表示用户家目录，避免在版本库中泄露绝对私人路径。

---

## 1. 主机与硬件

| 项目 | 观测值 |
|---|---|
| 发行版 | Ubuntu 22.04.5 LTS (Jammy Jellyfish) |
| 内核 | 6.8.0-138-generic |
| CPU | 12th Gen Intel Core i7-12650H（10 核 / 16 线程） |
| 内存 | 总计 62 GiB（可用约 55 GiB），Swap 2 GiB |
| 磁盘 | 根分区 916 G，已用 185 G，可用 685 G（使用率 22%） |

结论：磁盘余量充足，足以容纳 SUMO 逐 seed 输出、matplotlib 图件与 LaTeX 中间产物；但逐 step 轨迹（FCD）仍应避免长时段全量落盘。

## 2. GPU、驱动与 CUDA

| 项目 | 观测值 |
|---|---|
| GPU | NVIDIA GeForce RTX 4060 Laptop GPU |
| 显存 | 8188 MiB（审计时占用 15 MiB） |
| 驱动版本 | 575.51.03 |
| 驱动报告的最高 CUDA 版本 | 12.9（这是**驱动**支持的版本，不等于本地 Toolkit） |
| 本地 CUDA Toolkit | 是，`/usr/local/cuda-12.9`（`/usr/local/cuda` → `cuda-12` → `cuda-12.9`），`nvcc` 12.9.41 |
| `nvidia-smi` 状态 | 正常：温度 36 ℃、P0、功耗 12 W / 70 W、GPU 利用率 0%、仅 Xorg 占用 4 MiB，无计算进程 |

注意（风险项，未处理）：

- `LD_LIBRARY_PATH` 中包含 `/usr/local/cuda-12/lib64`（重复出现两次），而 `mmd` 环境内的 PyTorch 自带 cu118 运行时。当前 `torch.cuda.is_available()` 为 True，说明暂未冲突；但若后续出现 `libcudart`/`libcublas` 加载异常，应优先怀疑该环境变量，而不是重装 PyTorch。
- 驱动 575 对新旧 CUDA 运行时向下兼容，CUDA 12.9 Toolkit 与 PyTorch cu118 二进制**共存**是可行的，两者互不替代。

## 3. 基础工具链

| 工具 | 版本 / 状态 |
|---|---|
| Git | 2.34.1（支持 `git init -b main`） |
| Git 身份 | 全局 `user.name` / `user.email` 已配置（非空），本阶段**未修改** |
| Git LFS | git-lfs 3.6.1 已安装（本阶段未启用） |
| Python（conda base） | 3.12.2，位于 `~/anaconda3`；`CONDA_DEFAULT_ENV=base` |
| Python（系统） | /usr/bin/python3 为 3.10.12 |
| pip | 24.2（base 环境） |
| Conda | 24.11.3（无 mamba / micromamba） |
| conda 环境数 | 10（base、ai4s、attentionlight、colight、d2l、highway、metadrive、mmd、mplight、sumorl） |

## 4. SUMO / TraCI

| 项目 | 观测值 |
|---|---|
| SUMO 二进制 | `/usr/bin/sumo`，Eclipse SUMO **1.12.0**（同时存在 `sumo-gui`、`netconvert`、`duarouter`） |
| `SUMO_HOME` | **已设置**为 `/usr/share/sumo` |
| traci / sumolib | conda base 与 `mmd` 环境内均为 **1.24.0**（pip 安装，非 `/usr/share/sumo/tools` 中的 1.12 版本） |

版本偏差：SUMO 二进制 1.12.0 ↔ traci/sumolib Python 包 1.24.0。已在 `/tmp` 下做受限连通性测试（`--end 3`，非研究性仿真）：

```
traci.start(['sumo','-c', scenarios/original/cross.sumocfg, '--end','3', '--no-step-log','true','--seed','1'])
→ 3 步后 sim time = 3.0，在线车辆 10 辆，traci.close() 正常
```

结论：基本 TraCI 通路可用（`scenarios/original/cross.sumocfg` 可被 SUMO 1.12 加载并运行）；但 1.24 客户端与 1.12 服务端并非官方配套组合，做 baseline 时需要为**每个使用的 TraCI 调用**建立可用性验证，或由作者决定是否固定一套配套版本（本阶段不做任何版本变更）。

另外单独用 SUMO 直接运行 `cross.sumocfg --end 1` 退出码为 0，说明配置中引用的路网/车流/类型文件均存在且自洽（详见 `docs/audits/workspace-inventory.md`）。

## 5. LaTeX

| 项目 | 状态 |
|---|---|
| pdflatex / xelatex / lualatex | **未安装** |
| latexmk | **未安装** |
| bibtex / biber | **未安装** |
| kpsewhich / chktex / tectonic | **未安装** |
| TeX Live 目录（/usr/local/texlive、/opt/texlive） | 不存在 |
| dpkg 中 texlive* 包 | 无 |

结论：**当前机器无法编译论文**。这不是代码问题，而是工具链缺失。因为本阶段禁止安装软件，故未处理；编译能力（以及 EIC 关注的页数核算）在安装 TeX Live 或改用 Overleaf 在线编译之前无法验证。

参考：论文使用 `\documentclass[journal]{IEEEtran}`（`main.tex` 第 1 行），因此需要 IEEEtran 文档类（`texlive-publishers` 中的 `ieeetran` 或 IEEE 官方 cls）。若日后安装，应记录确切版本，并**不要**自动升级 IEEE 模板。

## 6. VS Code 解释器

- 工作区内**没有** `.vscode/settings.json`，用户级 settings 中也未检索到 `python.*` 相关配置项。
- 因此当前无法从配置层面确定工作区 Python 解释器；终端处于 conda `base`（Python 3.12.2）。
- 现状含义：工作区默认解释器很可能是 base 的 3.12，而实验依赖（PyTorch 2.0.0 + cu118）只存在于 `mmd`（Python 3.8.20）。后续在 VS Code 中打开 baseline 代码时，需显式选择 `mmd` 解释器，否则会出现"torch 不可用/版本不符"的假故障。本阶段未创建 `.vscode/`，以免把个人 IDE 配置写入仓库。

## 7. 相关环境变量

```
SUMO_HOME=/usr/share/sumo
CONDA_DEFAULT_ENV=base
CONDA_PREFIX=~/anaconda3
LD_LIBRARY_PATH=/usr/local/cuda-12/lib64:/usr/local/cuda-12/lib64:
PATH=…/usr/local/cuda-12/bin:…/anaconda3/bin:…
VSCODE_PYTHON_AUTOACTIVATE_GUARD=1
```

风险：`SUMO_HOME` 指向 1.12 的 tools 目录，而实际被 Python import 的 `traci` 来自 site-packages（1.24）。若将来用 `$SUMO_HOME/tools` 拼路径（常见写法 `sys.path.append(os.path.join(os.environ['SUMO_HOME'],'tools'))`），会同时出现两个 traci 版本，务必在 baseline 代码中显式避免。

---

## 8. 结论

1. GPU 与驱动正常，CUDA Toolkit 12.9 可用；CUDA 版本"驱动报告版本"与"本地 Toolkit 版本"已区分记录。
2. SUMO 1.12 + TraCI 通路可用（存在 1.12/1.24 版本偏差，已记录未修改）。
3. LaTeX 工具链**完全缺失**，为当前唯一硬性环境阻塞项。
4. VS Code 解释器未配置，实验代码应固定使用 conda `mmd`（Python 3.8.20）或后续为 baseline 新建独立环境（需作者决策，本阶段未创建）。
