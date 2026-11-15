# S0 环境与权重复核（2026-11-15）

- **范围**：`reconstruction-plan.md` §4 的 **S0 —— 环境/权重复核**。
- **本阶段不跑仿真**：没有加载模型、没有推理、没有生成任何轨迹或数字。
- **触发**：作者 2026-11-15 指令「启动 DSIP 的还原」；闸门 G1–G4 当日全部关闭
  （`gate-review-2026-11-15.md`）。
- **结束方式**：按 L3 阶段闸门，**在此停下等作者确认**，不进入 S1。

---

## 1. 上游 MMD checkout

| 项 | 值 |
|---|---|
| 路径 | `third_party/_local/mmd/` |
| commit | `5c2597eb3e2def9f0a87d7972811d340343c0738` |
| branch | `main` |
| pristine | ✅ **是**：`git status --porcelain` 输出为空 |

**本阶段做的一件事**：清理了 18 个 untracked 的 `__pycache__/` 目录
（此前运行留下的 Python 字节码，不属于上游内容）。清理前有 18 条 `?? …/__pycache__/`，
清理后 **0 条**，源码与 git 索引未触碰。

> 注意：`__pycache__` 会继续在 S1 加载模型时重新生成。按需在每次 S 阶段结束时清理，
> 或使用 `PYTHONDONTWRITEBYTECODE=1` 运行，避免反复污染 pristine 状态。

## 2. 固定 prior 的权重

要求：**只用** `EnvEmptyNoWait2D-RobotPlanarDisk`（换 prior 或重训 = 违规）。

| 文件 | 实测 SHA256 | 与 `checkpoint_manifest.md` §4 一致 |
|---|---|---|
| `args.yaml` | `2bb581b18f3a1c5f777c4fe6098c35c9974c3ba707229245ab0f14d6551106c3` | ✅ |
| `checkpoints/ema_model_current_state_dict.pth` **（实际加载）** | `ed1180b1136d7bfbce1b1c08097d868fbf737df8f2b14bb521cebed1ee0b3444` | ✅ |
| `checkpoints/ema_model_current.pth` | `822f33945dfd9d34cfff3730f467971ce25e01d47343e742971f7dae17d66573` | ✅ |

- 路径：`third_party/_local/_assets/data_trained_models/EnvEmptyNoWait2D-RobotPlanarDisk/`
- `args.yaml` 中 `dataset_subdir = EnvEmptyNoWait2D-RobotPlanarDisk`、`use_ema: true`
  ⇒ 实际权重是 `ema_model_current_state_dict.pth`（见清单 §3）。
- 目录下另有 `EnvEmpty2D` / `EnvHighways2D` / `EnvConveyor2D` / `EnvDropRegion2D`
  的权重：**存在但按规则不得使用**。

## 3. 运行环境

| 项 | 值 |
|---|---|
| conda 环境 | `~/anaconda3/envs/mmd` |
| Python | 3.8.20 |
| PyTorch | **2.0.0**（`torch.version.cuda == 11.8`） |
| CUDA 可用 | `True` |
| GPU | NVIDIA GeForce RTX 4060 Laptop GPU（8 GB） |
| cuDNN | 8700 |

与 `mmd_environment_report.md` §5 记录一致，**未新建环境、未安装任何包**。

## 4. 与重建契约的对照

| 契约（`AGENTS.md`） | S0 状态 |
|---|---|
| 固定 prior = `EnvEmptyNoWait2D-RobotPlanarDisk` | ✅ 权重在位且哈希可核 |
| 固定协调器 MMD-xECBS + Experience Reuse | ✅ 上游 `mmd/planners/multi_agent/cbs.py` 在位，待 S2 读调用顺序 |
| 上游 pristine | ✅ 已恢复（清理 `__pycache__`） |
| 适配代码只在 `src/dsip_reconstruction/` | ✅ 该目录仍为空（尚未创建文件） |
| 不重训 / 不改架构 | ✅ 无任何改动 |
| 运行需记录 commit + 权重哈希 + 环境 | ✅ 本节即为记录基线 |

## 5. S0 结论

> **环境与权重全部就位、可核验、无偏离。**
> 未发现任何需要作者裁决的资产问题。
>
> **下一步是 S1**（单次单车 `EnvEmptyNoWait2D-RobotPlanarDisk` 推理：
> 加载/维度/去噪步数/GPU 记录）。按阶段闸门，**S1 需作者确认后才开始**。
