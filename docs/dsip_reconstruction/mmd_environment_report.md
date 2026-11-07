# MMD 环境与上游复现报告（Stage 1）

- 日期：**2026-11-07**；状态：**Stage 1 完成，Stage 2 未开始**
- 上游：`https://github.com/yoraish/mmd.git` → `third_party/_local/mmd/`（pristine，未改一个文件）
- 分级：**【已验证】**（本机实测）/ **【未验证】** / **【计划】**

---

## 1. 上游版本记录 【已验证】

| 项 | 值 |
|---|---|
| 分支 | `main` |
| HEAD commit | **`5c2597eb3e2def9f0a87d7972811d340343c0738`** |
| HEAD 时间 / 说明 | 2025-02-12 20:01:51 −0500 — "Update README.md" |
| 提交总数 | **10**（`b49caa5` 初始 → `5c2597e` HEAD） |
| 体积 | **16 MB**（不含模型） |
| 许可证 | **MIT License**, © 2024 Yorai Shaoul, Itamar Mishani, Shivam Vats（`LICENSE` 46 行） |
| 再分发 | MIT **允许**再分发（需保留版权与许可声明）——与 PSB/PSL 不同；但本轮仍不把上游源码复制进本仓库 |

### 1.1 与"论文版本"的差距（必须记录）

- 作者提示上游在 **2024-11-07** 做过清理/效率修改，可能与论文结果略有不同；
- 当前 HEAD 是 **2025-02-12**，晚于该日期 ⇒ **我们拿到的是"清理后"的代码**；
- 仓库只有 10 个提交，更早历史不可得；checkpoint 里记录的训练 commit
  `81b20df…` **不在**当前历史中（`git cat-file` 报 `could not get object info`，
  详见 `checkpoint_manifest.md` §6）。
- ⇒ **不得声称"复现了论文实验时的那份代码"**；只能说"在上游 `5c2597eb` + 官方完整 checkpoint 上复现"。

## 2. 仓库结构 【已验证】

```text
mmd/
├── mmd/                       # 主包（config/ datasets/ models/ planners/ trainer/ utils/ ...）
├── scripts/
│   ├── inference/             # ← ★ 多车推理入口（作者指定 Q3 的位置）
│   │   ├── inference_multi_agent.py
│   │   ├── launch_multi_agent_experiment.py
│   │   ├── launch_multi_tile_experiment.py
│   │   ├── launch_mapf_comparison_experiment.py
│   │   └── launch_mapf_freespace_experiment.py
│   ├── generate_data/         # 训练数据生成
│   └── train_diffusion/       # 训练脚本（本轮禁止使用）
├── deps/
│   ├── torch_robotics/        # 环境与机器人定义（EnvEmptyNoWait2D 在这里）
│   ├── motion_planning_baselines/
│   └── experiment_launcher/
├── environment.yml, requirements.txt, setup.py, setup.sh, LICENSE, README.md
└── media/                     # README 用 gif（对复现无用）
```

## 3. xECBS 的实际位置与关键细节 【已验证，回答 Q3】

### 3.1 实现文件

- **`mmd/planners/multi_agent/cbs.py`**（508 行）：
  - `class CBSExperienceReuseStrategy(Enum)`：`NONE / XCBS / NOISE_AS_EXPERIENCE`；
  - `class CBS`：第 128 行 **硬编码** `self.experience_reuse_strategy = CBSExperienceReuseStrategy.XCBS`；
  - 第 412-430 行：重规划时把父节点该 agent 的路径包成
    `PathBatchExperience(new_state.path_bl[agent_id])` 交给低层 planner。

### 3.2 ⚠️ 但默认并不是 xECBS —— 必须由调用方打开

```python
# cbs.py:112-117
def __init__(self, low_level_planner_l, start_l, goal_l, start_time_l=None,
             is_xcbs=False,            # <-- 默认 False
             is_ecbs=True, ...):       # <-- 默认 True
```

```python
# scripts/inference/inference_multi_agent.py:112-113
'is_xcbs': True if test_config.multi_agent_planner_class in ["XECBS", "XCBS"] else False,
'is_ecbs': True if test_config.multi_agent_planner_class in ["ECBS", "XECBS"] else False,
```

⇒ **复现 xECBS 的唯一正确做法**：在实验配置里把 `multi_agent_planner_class` 设为
**`"XECBS"`**（同时得到 strong/weak 约束 + experience reuse）。
若沿用默认值，跑出来的是 **ECBS**，且 `experience_reuse_strategy` 虽为 XCBS 也不会被用到
（`cbs.py:422` 在 `if self.is_xcbs:` 分支内）。
**这一条已写入 `implementation_decisions.md` D-03a，Stage 3 必须先验证。**

### 3.3 Experience Reuse 的调用链 【已验证】

1. `cbs.py` 父节点保存 `path_bl`（每 agent 一个 batch 路径）；
2. 子节点重规划 → `PathBatchExperience(...)` 作为 `experience` 参数；
3. `mpd_ensemble.py` → `DiffusionsEnsemble.run_local_inference(seed_trajectory_b,
   n_noising_steps, n_denoising_steps)`（`diffusion_ensemble.py:270-300`）：
   - 对种子轨迹做 **`n_noising_steps` 步前向加噪**（`make_timesteps(B, n_noising_steps)`）；
   - 再以 **`n_denoising_steps` 步**去噪回来（同时施加更新后的约束梯度）。
4. 默认值：**noising 3 / denoising 3**（`mmd_params.py`）。

⇒ 与任务书的一致表述应是："**常规推理 25 个扩散步；experience reuse 走 3 步加噪 + 3 步去噪**"，
**不是**"所有规划都是 3 步"。

## 4. 低层规划器 【已验证结构，未运行】

`mmd/planners/single_agent/` 同时存在 **`mpd.py`（MPD）** 与 **`mpd_ensemble.py`（MPDEnsemble）**。

- `mpd_ensemble.py` 第 176-177 行：`use_ema=True` 时加载
  `checkpoints/ema_model_current_state_dict.pth`（`mpd.py:168-169` 同）。
- 推理脚本默认接的是哪一个：**Stage 2 需实测确认**（`inference_multi_agent.py` 里按
  `model_ids` 构造低层 planner 的分支）。**在确认前不擅自选择**（见 `implementation_decisions.md` D-02a）。

## 5. 环境现状 【已验证】—— 复用既有 `mmd` 环境，未新建、未安装任何包

| 项 | 值 | 判定 |
|---|---|---|
| 环境 | `~/anaconda3/envs/mmd`（conda，Python 3.8.20） | 可用 |
| PyTorch | **2.0.0+cu118**（`torch.version.cuda == 11.8`） | 与官方建议一致 |
| GPU | `torch.cuda.is_available() == True`，RTX 4060 Laptop（8 GB） | 可用 |
| gdown | **5.2.0**（环境内自带） | 用于 checkpoint 下载 |
| 上游 `environment.yml` | 只声明 `python=3.8 + patchelf + pip: pyyaml, matplotlib, setuptools==70.2.0` | 依赖主要由 `requirements.txt` 给 |
| 上游 `requirements.txt` | 含 `torch` 被注释掉（`#torch~=2.0.0+cu118`），torch 需另装 | 已满足 |
| 导入克隆代码 | `PYTHONPATH=third_party/_local/mmd` 下 `import mmd` → **来自克隆目录**；`from mmd.planners.multi_agent.cbs import CBS` 成功 | ✅ |

### 5.1 已知风险（环境层面）

1. 该环境里**已有一个可编辑安装的 `mmd 0.1`**，指向工作区**之外**的旧副本
   （`docs/env/mmd-environment-audit.md` §4 已标记作废、不得引用）。
   ⇒ 本轮一律用 `PYTHONPATH=third_party/_local/mmd` 强制优先克隆
   （已实测确认 `mmd.__file__` 来自克隆）。**不修改**该 editable 安装，也不删除。
2. `traci/sumolib` 为 **1.24.0**，而系统 SUMO 二进制是 **1.12.0** —— 已知偏差，Stage 6 集成时复核。
3. 上游 **不含** `traci`/`sumolib` 任何引用 ⇒ SUMO 桥接层必须由我们在
   `src/dsip_reconstruction/` 新写。

## 6. checkpoint 目录的接法（不修改上游）

上游有三处路径约定：

| 位置 | 内容 |
|---|---|
| `mmd/config/mmd_params.py:63` | `trained_models_dir_global_fpath = '~/mmd/data_trained_models'  # Modify this.` |
| `mmd/planners/single_agent/mpd_ensemble.py:62` | `TRAINED_MODELS_DIR = '../../data_trained_models/'` |
| `scripts/inference/inference_multi_agent.py:75` | `TRAINED_MODELS_DIR = '../../data_trained_models/'` |

我们的做法（**不改上游**）：

- checkpoint 放在 `third_party/_local/_assets/data_trained_models/`（Git 忽略）；
- 适配层构造参数时**显式传入** `trained_models_dir`（`MPDEnsemble.__init__` 已接受该参数）；
- 对硬编码的 `'../../data_trained_models/'`，用 **cwd 或工作区忽略目录内的符号链接**解决，
  并在 `run_manifest.json` 记录实际路径。**不 patch 上游文件。**

## 7. 恢复到的 MMD 默认参数 【已验证】（来源：`mmd/config/mmd_params.py`）

| 参数 | 值 |
|---|---|
| `robot_planar_disk_radius` | **0.05**（直径 0.10） |
| `n_samples` | **64** |
| `horizon` | **64** |
| `trajectory_duration` | **5.0 s** ⇒ `Δt_MMD = 0.078125 s` |
| `n_local_inference_noising_steps` | **3** |
| `n_local_inference_denoising_steps` | **3** |
| `start_guide_steps_fraction` | 0.5 |
| `n_guide_steps` | 20 |
| `n_diffusion_steps_without_noise` | 1 |
| `weight_grad_cost_collision` | **2e-2** |
| `weight_grad_cost_smoothness` | **8e-2** |
| `weight_grad_cost_constraints` | **2e-1**（strong） |
| `weight_grad_cost_soft_constraints` | **2e-2**（weak） |
| `factor_num_interpolated_points_for_collision` | 1.5 |
| `vertex_constraint_radius` | **0.12**（= 0.05 × 2.4） |
| `low_level_choose_path_from_batch_strategy` | `least_collisions` |
| `runtime_limit` | 60 s |

⇒ 与任务书给出的 MMD Appendix A.4 参考值**逐项吻合**（0.08 / 0.02 / 0.20 / 0.02 / disk 0.10 / sphere 0.12）。
但这是 **MMD 默认值**，不是 DSIP 原值 ⇒ 在 `parameter_inventory.md` 中标 `MMD_REFERENCE`。

## 8. 本阶段没做的事（不得视为已完成）

- 未跑任何推理/训练（单车、多车都没有）；
- 未验证 checkpoint 能否被 `load_state_dict` 完整加载（只做了 state_dict 键/形状自检）；
- 未确定低层 planner 用 `MPD` 还是 `MPDEnsemble`；
- 未接入 SUMO。

## 9. 下一步（Stage 2，等作者确认）

在 `mmd` 环境、`PYTHONPATH=third_party/_local/mmd` 下：

1. 用官方入口做**一次**单车 EmptyNoWait 推理（固定 seed），确认模型加载、输入输出维数、
   轨迹坐标/时间范围、去噪步数、GPU 使用；
2. 记录完整命令 + 配置 + 轨迹 + 日志（写入 Stage 2 才创建的结果目录）；
3. **不跑**多车、不跑 SUMO、不跑任何批量。

