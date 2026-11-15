# DSIP 重建 S1–S3 运行记录（2026-11-15）

- **性质**：`DSIP-Reconstructed`，**非**历史 DSIP 实现；只做**定性**分析（作者 2026-11-15 指令）。
- **不追求**与历史数字的绝对一致（checkpoint 之外的训练数据缺失，参数标定成本过高）。
- 闸门：G1–G4 已于当日关闭（`gate-review-2026-11-15.md`）；S0 见 `stage0-report.md`。

---

## 0. 上游改动与"照原文"的界定

| 项 | 做法 |
|---|---|
| prior | `EnvEmptyNoWait2D-RobotPlanarDisk`，`ema_model_current_state_dict.pth`，**未重训** |
| 低层规划器 | 上游 `mmd.planners.single_agent.MPD`，**一行未改**（通过 `prior.py` 注入 dataset shim） |
| 协调器 | 上游 `mmd.planners.multi_agent.CBS`，`is_xcbs=True, is_ecbs=True`，`PointConflict→MultiPointConstraint`，**一行未改** |
| 参数 | 全部取自 `mmd.config.MMDParams` 与模型 `args.yaml` |
| 上游 checkout | `third_party/_local/mmd` @ `5c2597eb…`，**pristine** |

**唯一的适配**（全部在 `src/dsip_reconstruction/`，属于"道路适配层"，不是方法改写）：

1. `upstream_env.py`：把工作区内 checkout 置于 `sys.path` 首位，并**断言** `mmd`/`torch_robotics`/`mp_baselines` 解析结果都在工作区内（conda 环境里的 editable install 指向工作区外，§0 禁止）。
2. `prior.py`：上游 `TrajectoryDataset` 需要 `data_trajectories/`（1 万条训练轨迹），**工作区内没有**。用一个只提供 `MPD` 所读属性的 shim 替代；归一化限位按"磁盘半径 0.05 在 `[-1,1]^2` 盒内"取 `±0.95`，速度取对称 `±1.5`（硬条件把速度钉为 0，对称区间归一化后恰为 0，故只影响不用于控制的输出速度通道）。
3. `sumo_runner.py`：SUMO ↔ 规划框的几何映射、滚动重规划、理想位置控制、超时兜底。
4. `planning frame`：1 单位 = `0.5 × v_road × 5 s` = **34.75 m**，使先验固定的 5 s 时域对应车辆以路段限速穿越规划框。

> 这些适配都记录在 `s1_report.json` / `s3_report.json` 的 `dataset_source`、`mode`、`frame` 字段里。

## 1. S1 —— 单车间推理（通过）

| 项 | 值 |
|---|---|
| 加载时间 | **1.68 s**（权重 + 任务构建） |
| 单次推理 | **0.852 s**（25 步去噪 + 引导，含 `t_model_sampling 0.822 s`） |
| 采样数 | 64 条，**64/64 无碰撞** |
| 端点误差 | 起点 0.011、终点 0.011（帧单位） |
| 盒内比例 | 1.00 |
| 去噪配置 | `n_diffusion_steps=25`，`t_start_guide=13`（后 12 步引导），`n_guide_steps=20` |

产物：`results/dsip_s1/{s1_report.json, s1_trajs.pt, s1_samples.png}`。
形状核验：采样为起点→终点的近直线，端点精确，符合"空盒 + 直线偏好"的先验（`compute_traj_data_adherence` 奖励直线）。

## 2. S2 —— 多车 xECBS + Experience Reuse（通过）

| 场景 | 智能体 | CT 展开 | 结果 | 规划耗时 | 最小间距 |
|---|---|---|---|---|---|
| `s2_cross4.json` | 4 | **0** | SUCCESS | 2.94 s | 0.118 (> 2r=0.10) |
| `s2_cross8.json` | 8 | **3** | SUCCESS | 8.28 s | 0.107 (> 0.10) |

8 车场景**真正走到了经验复用分支**，日志为 `Using warm start path in p_sample_loop. Steps [3, -1]`：

| 调用类型 | 去噪步数 | 单次模型前向 |
|---|---|---|
| 全新规划（根节点） | 25 | **0.72–0.73 s** |
| 经验复用（CT 展开） | **3** | **0.235–0.238 s** |

⇒ **复用把单次推理压到约 1/3**，这是"推理时间兜底"的第一条证据。

产物：`results/dsip_s2/{s2_report.json,s2_paths.pt}`、`results/dsip_s2_8/…`。

## 3. S3 —— SUMO 端到端（通过）

配置：cross3，`epoch=2 s`，`max_agents=3–4`，`paper_faithful` 位置控制，
`--collision.mingap-factor 0.5`（= 1.5 m 阈值），1000 s 上限但本轮跑 60–200 s。

60 s 冒烟运行（density3）：

| 项 | 值 |
|---|---|
| CBS 调用 | 30 |
| 求解成功 | **29/30** |
| 被规划车辆 | 68 |
| 释放回 SUMO（兜底） | 3 |
| 单次规划 p50 / max | **2.12 s / 3.37 s** |
| 实时比（规划墙钟 / 仿真时长） | **1.05** |

## 4. S3 定性对比：转向比敏感性（核心结果）

6 个 run：3 个 flow × {无控制, DSIP}，cross3，seed 81890，**200 s**，
`epoch=2 s`，`max_agents=4`，`paper_faithful`。
三个 flow 的总需求都锁在 4608 veh/h（`lanes3_density3` = 1:2:1，`_r111` = 1:1:1，`_r122` = 1:2:2）。

| flow | arm | 逐车 timeLoss (s) | 近距事件 <1.5 m | 完成行程 | 规划 p50 (s) |
|---|---|---|---|---|---|
| **1:2:1** | 无控制 | **9.30** | 13 | 498 | – |
| **1:2:1** | **DSIP-Reconstructed** | 18.67 | 449 | 478 | 1.82 |
| **1:1:1** | 无控制 | **10.13** | 12 | 499 | – |
| **1:1:1** | **DSIP-Reconstructed** | 20.12 | 471 | 476 | 2.16 |
| **1:2:2** | 无控制 | **8.96** | 17 | 427 | – |
| **1:2:2** | **DSIP-Reconstructed** | 15.74 | 390 | 450 | 2.15 |

### 4.1 相对效应（作者关心的那个问题）

以 1:2:1 为基准，看**同一条臂内**换成别的转向比时的相对变化：

| 转向比 | 无控制 ΔTL | DSIP ΔTL | 无控制 Δtrip | DSIP Δtrip |
|---|---|---|---|---|
| 1:1:1 | +8.9 % | **+7.7 %** | +0.2 % | −0.4 % |
| 1:2:2 | −3.7 % | **−15.7 %** | −14.3 % | **−5.9 %** |

**定性结论**：`DSIP-Reconstructed` 对转向比变化的**相对响应方向与无控制一致**
（1:1:1 使时耗上升、1:2:2 使时耗下降），量级同阶；在 1:2:2 下
完成行程的下降幅度**明显小于**无控制臂（−5.9 % vs −14.3 %）。
**没有观察到"改转向比后 DSIP 的相对效果变差"。**

> 但只有 **1 个 seed**、200 s，只能作定性陈述，不能作统计推断。

### 4.2 必须同时披露的保真度缺口

**近距事件从 13 升到 449（约 35 倍）**——这是重建与历史 DSIP 的**实质差距**，原因已知且可解释：

1. 先验的碰撞模型是**半径 0.05（帧单位）的圆盘**；本适配的 1 单位 = 34.75 m，
   故圆盘半径 ≈ **1.74 m**（直径 3.5 m），而 SUMO 车长 **5 m**。
   计划保证的是"圆心距 ≥ 3.5 m"，执行成 5 m 的车必然贴到 1.5 m 以内。
2. `paper_faithful` 模式按 `AGENTS.md` 的约定**不做**矩形碰撞/运动学校验；
   该缺口正是 `dynamics_aware` 模式（规划中新增的一项统计量 A）要补的。
3. 位置控制用 `moveToXY(keepRoute=2)`，帧内横向偏移被压到中心线上。

⇒ 因此本轮的 DSIP 数字**不能**用于"DSIP 优于/劣于 X"，只能用于
**同一条臂内的相对响应**（§4.1），这与作者的定性要求一致。

### 4.3 推理时延与兜底（第二条定性结论）

| 项 | 值 |
|---|---|
| 单次 CBS 组规划（≤4 车）p50 | **1.82 / 2.16 / 2.15 s** |
| 超过 400 ms 预算的比例 | **100 %**（100/100 calls，三个场景一致） |
| 兜底：无解/异常 → 交回 SUMO | 有效，逐车计数（`n_released_vehicles`、`s3_fallbacks.json`） |
| 经验复用单次前向（S2 实测） | **0.235 s** vs 全新 25 步 **0.73 s** |

结论：**兜底存在且生效**（没有任何车被冻住），但 **400 ms 的实时预算在重建实现上无法满足**，
瓶颈是"每车一次完整去噪"（25 步）+ 每次规划重建 planner。
经验复用把单次前向压到 1/3，是唯一已经被实测证实的加速手段。

> 历史稿的 "7.75 ms/query" 不能由本实现支持，也不应被引用（`AGENTS.md` 的 timing honesty 条款）。

## 5. 复现

```bash
# S1
/home/qian/anaconda3/envs/mmd/bin/python src/dsip_reconstruction/s1_single_agent.py \
  --out results/dsip_s1 --no-compile

# S2
/home/qian/anaconda3/envs/mmd/bin/python src/dsip_reconstruction/s2_multi_agent.py \
  --scenario scenarios/dsip/s2_cross8.json --out results/dsip_s2_8 --no-compile

# S3 + 转向比对比
/home/qian/anaconda3/envs/mmd/bin/python src/dsip_reconstruction/run_compare.py \
  --rous lanes3_density3.rou.xml,lanes3_density3_r111.rou.xml,lanes3_density3_r122.rou.xml \
  --end 200 --epoch 2 --max-agents 4 --seed 81890 --no-compile \
  --out results/dsip_compare
```

`results/` 全部 git-ignored、可重算；汇总表在 `results/dsip_compare/compare.csv`。

## 6. 已知偏离清单（供作者裁决）

| # | 偏离 | 影响 | 是否阻塞 |
|---|---|---|---|
| D-1 | 训练集 `data_trajectories` 缺失，用 shim + 假定归一化限位 | 端点精度、先验分布可能有小偏差 | 否（定性可用） |
| D-2 | 规划框尺度 34.75 m/单位是适配器选择 | 决定穿越速度与占用 | 否，但需在论文说明 |
| D-3 | 圆盘碰撞 vs 5 m 车 → 近距事件偏高 | 绝对安全指标不可用 | **是**（若论文要用近距） |
| D-4 | 规划框边界截断在 0.90（上游拒绝越界目标） | 进出点略内缩，穿越距离短 10 % | 否 |
| D-5 | 未使用 `start_time_l` 错峰 | 框内车辆按 5 s 时域行驶，比自由流慢 | 否（定性） |
| D-6 | 每次规划新建 MPD（已加 dataset/权重缓存） | 单次 p50 仍 1.8–2.2 s | 否，但影响"实时"表述 |

