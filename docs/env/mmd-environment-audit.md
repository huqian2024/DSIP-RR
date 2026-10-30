# `mmd` 环境审计（只读）

- 审计日期：2026-10-30
- 约束：**未**安装/升级/卸载任何包，**未**修改环境，**未**运行训练或推理。仅做 import 与版本查询，以及在 `/tmp` 内做一次 3 步 TraCI 连通性测试。
- 路径统一用 `~` 表示家目录。

## 1. 环境形态判定

不是"名字叫 mmd 的某个环境"的假设，而是逐项验证：

| 判据 | 观测结果 |
|---|---|
| 目录 | `~/anaconda3/envs/mmd` |
| `conda-meta/history` 首行 | `# cmd: <conda>/conda create -n mmd python=3.8 -y`（2025-07-27） |
| `pyvenv.cfg`（venv 标志） | 不存在 |
| 目录结构 | `bin/ comdat-meta/ lib/python3.8/ …` 与 conda 环境一致 |

**结论：`mmd` 是一个 Conda 环境（Python 3.8）**，不是 venv，也不是 Docker/其他形式。可通过 `conda activate mmd` 或直接调用 `~/anaconda3/envs/mmd/bin/python` 使用。

## 2. Python 与深度学习栈

| 组件 | 版本 |
|---|---|
| Python | 3.8.20 |
| PyTorch | 2.0.0（编译时 CUDA 11.8，`torch.version.cuda == 11.8`） |
| torchvision | 0.15.0 |
| torchaudio | 2.0.0 |
| cuDNN | 8.7.0（`torch.backends.cudnn.version() == 8700`） |
| triton | 2.0.0 |
| 已安装包总数 | 134 |

### GPU 可用性（实际调用验证）

```
torch.cuda.is_available()      -> True
torch.cuda.device_count()      -> 1
torch.cuda.get_device_name(0)  -> NVIDIA GeForce RTX 4060 Laptop GPU
```

结论：PyTorch 能正确识别并使用本机 RTX 4060；不需重装或重建环境。

## 3. MMD 相关依赖完整性（对照上游 `requirements.txt`）

上游 `~/<mmd 源码>/requirements.txt` 声明的依赖基本齐备，抽查结果：

| 依赖 | 状态 |
|---|---|
| numpy / scipy | 1.24.3 / 1.10.1 |
| matplotlib / seaborn / plotly | 3.7.5 / 0.13.2 / 6.2.0 |
| pandas / pillow / PyYAML | 2.0.3 / 10.4.0 / 6.0.2 |
| torchdiffeq / torch-summary | 0.2.5 / 1.4.5 |
| trimesh / mesh-to-sdf / urdfpy | 4.7.1 / 0.0.15 / 0.0.22 |
| Hydra | 2.5 |
| wandb / tensorboard | 0.21.0 / 2.14.0 |
| sentence-transformers / transformers | 3.2.1 / 4.46.3 |
| opencv-python / moviepy / scikit-video / pygame | 4.10.0.84 / 1.0.3 / 1.1.11 / 2.6.1 |
| cholespy / einops / networkx | 2.0.0 / 0.6.1 / 2.2 |
| 本地可编辑安装 | `mmd 0.1`、`torch_robotics 0.0.0`、`mp_baselines 0.0.0`、`experiment-launcher 2.3` |
| sumolib / traci | 1.24.0（pip，**非** SUMO 1.12 自带版本） |

说明：以上为"依赖是否存在"的静态核对；按任务约束**未**执行任何 MMD 推理/训练，因此"能否端到端跑通"仍属未验证状态，不能据此宣称 MMD 已可运行。

## 4. 本机 MMD 源码定位

仅检查合理已知位置，未做全盘递归搜索。结果：

| 项目 | 观测值 |
|---|---|
| 路径 | `~/Downloads/mmd` |
| 形态 | Git 仓库，remote `https://github.com/yoraish/mmd.git` |
| HEAD | `5c2597e` "Update README.md"（2025-02-12） |
| 工作区状态 | 1 个已修改文件 `scripts/inference/inference_multi_agent.py`（+15/−12）；未跟踪：`data_trained_models/`、`data_trajectories/`、对应 `.tar.xz` 及若干 `__pycache__`/`egg-info` |
| 目录内容 | `mmd/`、`scripts/`、`deps/`（motion_planning_baselines、torch_robotics、experiment_launcher）、`data_trained_models/`、`data_trajectories/`、`environment.yml`、`requirements.txt` |

说明：该仓库是**上游 MMD**，不是 DSIP 的历史实现。本地存在未提交改动（去年实验期间形成），本阶段未回滚、未提交、未复制，仅记录。若后续要做可复现实验，需要把这套上游代码以"固定 commit + 记录本地 diff"的方式纳入 `third_party/`（新阶段工作，本阶段不做）。

## 5. MMD 与 SUMO / TraCI 的关系

- 在上游 `mmd/` 包与 `scripts/` 中检索 `traci` / `sumolib`：**无命中**。
- 即：上游 MMD 本身**不含** SUMO 集成；DSIP 论文中"SUMO + TraCI + 周期性重规划 + 分步执行"的那一层桥接代码属于 DSIP 自有部分，而这部分源码已丢失。
- 这与 `AGENTS.md` 的描述一致，也意味着：重建 DSIP 需要**新写** SUMO 桥接层，而不是"找回旧代码"。补充实验应以 FCFS / CCAM-DI baseline 优先。

## 6. 结论与风险

1. `mmd` 环境健康：Python 3.8.20 + PyTorch 2.0.0(cu118)，GPU 识别正常，`torch.cuda.is_available() == True`。
2. 依赖齐全，但"端到端可运行"未验证（本阶段禁止运行）。
3. traci/sumolib 为 1.24.0，而系统 SUMO 二进制为 1.12.0：**版本不一致**，属复现风险；`mmd` 环境内的 traci 能连接 1.12 服务端（已测 3 步），但完整 API 兼容性未验证。
4. 禁止事项已遵守：无任何 pip/conda 安装、升级、卸载操作；无 PyTorch/CUDA/驱动变更。
