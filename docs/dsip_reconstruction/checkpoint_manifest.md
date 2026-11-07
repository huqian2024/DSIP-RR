# EmptyNoWait checkpoint 清单（Stage 1 实测）

- 建立日期：**2026-11-07**；作者裁决（Q1）：**使用 full 版本归档**。
- 所有下列数值均为**本机实测**，不是从论文或 README 推断。

---

## 1. 归档来源

| 项 | 值 |
|---|---|
| 归档 | `data_trained_models.tar.xz`（**full 版**，非 `_small`） |
| Google Drive id | `1WO3tpvg-HU0m9RyDvGyfDamo7roBYMud`（来自 MMD README / 任务书） |
| 下载日期 | 2026-11-07 |
| 下载工具 | `~/anaconda3/envs/mmd/bin/gdown` 5.2.0（mmd 环境自带），经本地代理 |
| 归档大小 | **472 119 808 B**（472 MB） |
| 归档 mtime | 2024-11-08（服务器侧时间戳） |
| 落盘位置 | `third_party/_local/_assets/data_trained_models.tar.xz`（**Git 忽略**，`.gitignore` 的 `third_party/*/`） |
| 解压位置 | `third_party/_local/_assets/data_trained_models/`（同样忽略） |
| 解压后总大小 | 5 个模型 ≈ 1.2 GB（仓库本身只有 16 MB，模型不入库） |

## 2. 归档内包含的 5 个模型（实测）

```text
data_trained_models/
├── EnvConveyor2D-RobotPlanarDisk/
├── EnvDropRegion2D-RobotPlanarDisk/
├── EnvEmpty2D-RobotPlanarDisk/
├── EnvEmptyNoWait2D-RobotPlanarDisk/   <-- 本轮唯一允许使用
└── EnvHighways2D-RobotPlanarDisk/
```

⇒ **`EnvEmptyNoWait2D-RobotPlanarDisk` 存在**，与作者指定的先验一致；
其余 4 个按任务书 §0.1 **禁止使用**。

## 3. `EnvEmptyNoWait2D-RobotPlanarDisk/` 内容（实测）

```text
args.yaml
logfile                                   (0 B)
train_subset_indices.pt, val_subset_indices.pt
checkpoints/
  model_current.pth                       4 108 109 B
  model_current_state_dict.pth            4 058 051 B
  ema_model_current.pth                   4 108 757 B
  ema_model_current_state_dict.pth        4 058 699 B   <-- 推理实际加载的就是它
  model_epoch_6399_iter_480000[_state_dict].pth
  ema_model_epoch_6399_iter_480000[_state_dict].pth
  model_epoch_6133_iter_460000[_state_dict].pth
  ema_model_epoch_6133_iter_460000[_state_dict].pth
  train_losses.npy, val_losses.npy
```

**哪一份被加载**：`mmd/planners/single_agent/mpd_ensemble.py:176-177`
（与 `mpd.py:168-169` 同）在 `use_ema: true` 时加载
`checkpoints/ema_model_current_state_dict.pth`；本模型 `args.yaml` 中 `use_ema: true`
⇒ **实际权重 = `ema_model_current_state_dict.pth`**。

## 4. SHA256（本机计算）

| 文件 | SHA256 |
|---|---|
| `args.yaml` | `2bb581b18f3a1c5f777c4fe6098c35c9974c3ba707229245ab0f14d6551106c3` |
| `checkpoints/ema_model_current_state_dict.pth` *(实际加载)* | `ed1180b1136d7bfbce1b1c08097d868fbf737df8f2b14bb521cebed1ee0b3444` |
| `checkpoints/ema_model_current.pth` | `822f33945dfd9d34cfff3730f467971ce25e01d47343e742971f7dae17d66573` |
| `checkpoints/model_current_state_dict.pth` | `f4e040161d61022b0aa48f9a8c14087c24b8f990bf0605a0c674288be9ae8e77` |
| `checkpoints/model_current.pth` | `262a607c9dbce2a912343acfe2452301dddb7c51e68b34eccc924e35b39231df` |

> 归档本身的 SHA256 未算（472 MB，可后补）；已记录精确字节数与 mtime，可用于二次校验。

## 5. 模型配置（`args.yaml` 全文关键字段，实测）

| 字段 | 值 | 含义 |
|---|---|---|
| `dataset_subdir` | `EnvEmptyNoWait2D-RobotPlanarDisk` | 与指定先验一致 |
| `diffusion_model_class` | `GaussianDiffusionModel` | |
| `loss_class` | `GaussianDiffusionLoss` | |
| `include_velocity` | **true** | 状态含速度 ⇒ **state_dim = 4 `[x,y,vx,vy]`** |
| `n_diffusion_steps` | **25** | 与任务书/MMD 论文的 25 步一致 |
| `variance_schedule` | `exponential` | |
| `predict_epsilon` | `true` | |
| `use_ema` | `true` | ⇒ 加载 ema 权重 |
| `unet_dim_mults_option` | `0` | |
| `unet_input_dim` | `32` | |
| `num_train_steps` | `500000` | 归档里最新 ckpt 为 iter 480 000 |
| `batch_size` / `lr` / `seed` | 128 / 0.0003 / 0 | |
| `git_url` | `git@github.com:yoraish/mmd.git` | |
| **`git_hash`（训练时）** | **`81b20df798805a992f1653b77a9d53fe2a88b64b`** | 见 §6 |

## 6. ⚠️ 训练 commit 与当前克隆不一致（必须记录）

- 权重里记录的训练时代码版本是 `81b20df…`；
- 本机克隆的 MMD HEAD 是 `5c2597e…`（`main`，10 个 commit）；
- `git cat-file -t 81b20df…` → **`could not get object info`** ⇒ 该 commit **已不在上游历史中**
  （上游只保留 10 个提交，早期历史被重写过）。

**影响与处置**：
1. **不影响**推理：推理只需 `mmd/` 包与 checkpoint；`state_dict` 形状已与当前代码的
   `TemporalUnet` 匹配（实测见 §7），可正常加载。
2. **不可声称**"重建了当年那份训练代码"——我们没有、也拿不到。
3. 所有结果必须同时记录：checkpoint SHA256 + 当前 MMD commit `5c2597eb…`。

## 7. 权重结构自检（实测，仅加载 state_dict，CPU）

| 检查 | 结果 |
|---|---|
| state_dict 张量数 | **160** |
| 扩散缓冲 `betas` 形状 | `torch.Size([25])` ⇒ **n_diffusion_steps = 25** 由权重自身确认 |
| 首个卷积 `model.downs.0.0.blocks.0.block.0.weight` | `(32, 4, 5)` ⇒ **输入通道 = 4** ⇒ `state_dim = 4` |

## 8. 模型/数据尺度参数（来自上游代码，非本模型自述）

| 参数 | 值 | 来源 |
|---|---|---|
| 轨迹 horizon `H` | **64** | `mmd/config/mmd_params.py: horizon` |
| 轨迹时长 | **5.0 s** | `mmd_params.py: trajectory_duration` |
| ⇒ 时间采样间隔 `Δt_MMD` | **5.0 / 64 = 0.078125 s** | 由上面两行推出（**INFERRED**，非作者记忆） |
| 采样数 `n_samples` | **64** | `mmd_params.py` |
| robot disk 半径 | **0.05**（直径 0.10） | `mmd_params.py: robot_planar_disk_radius` |
| xECBS 顶点约束半径 | **0.12** | `mmd_params.py: vertex_constraint_radius = 0.05 × 2.4` |
| 工作空间 | **`[[-1,-1],[1,1]]`（2×2 units）** | `deps/torch_robotics/.../env_empty_2d.py: limits=` |
| 权重项 | collision **0.02** / smoothness **0.08** / constraints **0.20** / soft constraints **0.02** | `mmd_params.py` |
| 局部推理步数 | noising **3** / denoising **3** | `mmd_params.py` |
| 引导步数 | `n_guide_steps=20`、`start_guide_steps_fraction=0.5`、`n_diffusion_steps_without_noise=1` | `mmd_params.py` |
| 低层选路策略 | `least_collisions` | `mmd_params.py` |

> 这些是 **MMD 默认值**，不是 DSIP 的原值；在 `parameter_inventory.md` 中一律标
> `MMD_REFERENCE`，只有作者确认后才可升级为 `RECOVERED`。
