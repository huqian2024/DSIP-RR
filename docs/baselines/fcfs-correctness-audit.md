# FCFS Baseline 正确性审计（只审计，不改代码）

- 审计日期：**2026-11-07**
- 审计对象：`baselines/fcfs_sumo/`（`conflicts.py`、`booking.py`、`control.py`、`queue.py`、`tracker.py`、`shadow.py`、`test_logic.py`）
- 参考方法：Dresner & Stone (2008), *A Multiagent Approach to Autonomous Intersection Management*, JAIR
- 结论定位：本实现是 **conflict-point time-window reservation controller inspired by Dresner–Stone**，
  **不是** AIM4 原始时空 tile reservation 的复现。论文/文档必须这样写。
- 本文件**只记录缺陷与修复方案**；Stage 3 才改代码。

---

## 0. 现有实证状态（**来自工作区内已有产物，非本轮新跑**）

`results/fcfs_sweep/summary.csv`（旧扫描，未完成）：

| 项 | 值 |
|---|---|
| 已写出行数 | 227 / 450（`status=ok` 216，`skipped` 11） |
| 中断原因 | `sweep.log` 末尾 **8 次** `malloc_consolidate(): unaligned fastbin chunk detected` + 多次 `tcpip::Socket::recvAndCheck @ recv: Connection reset by peer` |
| 崩溃前错误洪泛 | `Error: Answered with error to command 0xc4: Failed to resume from stopping for vehicle 'flow_se.18', reached: 0, …`（同一车连续 7 步以上） |

分组统计（`lanes/density`: 完成 runs / 有碰撞 runs / 碰撞总数 / 平均 TimeLoss / 平均速度 / 平均完成/平均插入）：

| lanes/density | runs | 有碰撞 | 碰撞数 | TimeLoss | speed | arrived/departed |
|---|---|---|---|---|---|---|
| 2/1 | 30 | **19** | 33 | 65.8 s | 2.62 | 613/674 |
| 2/2 | 30 | **19** | 35 | 65.9 s | 2.60 | 596/658 |
| 2/3 | 30 | **18** | 37 | 66.8 s | 2.60 | 611/673 |
| 2/4 | 30 | **20** | 39 | 67.6 s | 2.55 | 609/671 |
| 2/5 | 30 | **17** | 36 | 67.2 s | 2.57 | 609/673 |
| 3/1 | 24 | 9 | 18 | 62.8 s | 2.85 | 478/528 |
| 3/2 | 30 | 9 | 12 | 60.6 s | 2.92 | 458/510 |
| 3/3 | 12 | 2 | 3 | 62.9 s | 2.90 | 403/455 |

⇒ **"FCFS 零碰撞"在现有实现下不成立**；且性能几乎不随密度变化，说明是**控制器受限**。
这些数字是**旧的不完整扫描**，Stage 3 修复后必须重跑，不得直接进论文。

---

## 1. 缺陷清单

### D-01 快/慢 ETA 使用同一加速度假设（**严重，安全性相关**）

- 位置：`booking.py:51-53`
  ```python
  A_MAX = 1.0   # types.typ.xml accel（best case）
  A_MIN = 1.0   # 注释写"accel 1.0 halved"，但值仍是 1.0
  ```
- 后果：`plan()` 里 `t_eta_fast = tt(0.0, A_MAX)` 与 `t_eta_slow = tt(0.0, A_MIN)` **恒等**，
  于是注释声称的"best case ~ worst case 窗口带"**宽度为零**；
  只要车辆实际减速（排队、让行、`setStop`），真实到达时刻就落到窗口之外，
  而 `free()` 仍认为资源已释放 ⇒ 这正是"预约过了但照样撞"的机制之一。
- 修复方向：`A_MIN` 取与 `decel`/实际减速一致的保守值（例如 0.5 m/s² 或按 `decel` 反推），
  并在算例中核验窗口带非零；**不得**通过缩小 `Δt_safe` 来补偿。

### D-02 `Δt_safe` 被重复计算（**严重，吞吐/口径相关**）

- 位置：`booking.py:204-213`（窗口 `t1` 已 `+ dt_safe`）与 `booking.py:222`（重叠判定再加 `+ dt_safe`）
- 后果：实际安全间隔约为设计值的 **2 倍**，与 `control.py:173-178` 中
  "`_release_lane` 已避免二次叠加"的注释自相矛盾；吞吐被压到远低于设计值。
- 修复方向：明确"窗口内已含间隔"或"判定时加间隔"**只取一处**，
  并在文档里给出公式；修复后必须重跑并如实报告碰撞变化。

### D-03 `too_close` 车辆被记为"已停放"（**严重，稳定性相关**）

- 位置：`control.py:324-328`（`setStop` 前置检查失败 → `too_close`，但仍 `self.stopped.add(vid)`）
- 后果：`self.stopped` 混淆了"我们发过 setStop"与"成功拦住"；
  之后 `_try_resume` 会对**没有活动 stop 的车辆**调用 `resume()`。
  实测症状就是 `Failed to resume from stopping … reached: 0` 的逐步洪泛（见 §0），
  并伴随 TraCI 连接被重置、SUMO 进程堆损坏退出。
- 修复方向：拆分 `stopped_ok` / `stop_failed` 两个集合；
  `resume()` 只对 `stopped_ok` 调用；`stop_failed` 车辆进入显式的 **forced** 分支并计入指标。
  （这是 Stage 3 的**第一优先修复**，因为它直接导致扫描崩溃。）

### D-04 缺少显式预约状态机（**中，可追踪性相关**）

- 现状：状态分散在 `request_time` / `granted` / `stopped` / `pending_resume` / `reserved` /
  `release` / `entered` / `touched` 八个容器里，**没有** `REQUESTED→GRANTED→WAITING→ENTERED→EXITED`
  的单一状态与非法转移检测。
- 后果：`granted` 只增不减（`control.py:360` 一旦 granted 就 `continue`），
  车辆离开后仍留在字典里；没有 `CANCELLED`/`EXPIRED` 语义，资源泄漏无法自证。
- 修复方向：引入 `enum` 状态 + 每步转移表 + 非法转移计数（Shadow 模式已有同类机制可复用）。

### D-05 预约释放依赖 `booker.prune` 的时间窗，不依赖"车尾离开"（**中**）

- 位置：`booking.py:232-241`（`prune` 只按时间裁剪），`control.py:349-350`
- 后果：窗口按**预测**时刻预置；若车辆晚到（D-01 的后果），
  资源在时间上"已释放"而车还在冲突区。缺少 `touched` 校验与车尾离开的实测检查。
- 修复方向：保留窗口法，但增加"实测通过时刻 vs 预约时刻"的偏差统计，
  偏差超阈值时标记该 run 为 `booking_violation`，并在指标里单列。

### D-06 `EXIT_ROOM = 45 m` 是硬阈值，且只用"头部位置"（**中，过度保守**）

- 位置：`control.py:49-55`、`control.py:246-257`
- 后果：出口车道头部必须空 45 m 才放行；出口边总长 83–90 m，这等价于要求出口近乎空载，
  是低吞吐的直接原因之一；且未使用实际车长/车速/队列位置。
- 修复方向：改为"按目标车位是否被占用 + 到达时刻的下游可用空间"判据
  （需要车长 5.0、`minGap` 3.0、当前速度，均来自 `types.typ.xml` 与 TraCI）；
  crossing 冲突与 merge 冲突分别处理（现已混在 `_exit_has_room` 一处）。
  **不得**简单把 45 改成 20/30 后宣称解决问题。

### D-07 `HEAD_LOOKAHEAD = 12 m` 只看"紧随前车"，不看排队长度（**中**）

- 位置：`control.py:46-48`、`control.py:370-371`
- 后果：队列第 2 辆之后的车在 12 m 内会被判为"非队首"而完全不参与 FCFS 排序，
  其 `request_time` 在首次进入 `L_ACZ` 时冻结，可能与真实到达顺序不一致。
- 修复方向：显式队列模型（按车道排队位置排序），或在文档中明确"FCFS 只对队首赋值"，
  并把"排队等待时间"计入指标。

### D-08 规划/仿真口径未分离，且关闭了警告（**中，可审计性**）

- 位置：`control.py:504`（`--no-warnings true`）、`control.py:505`（`--collision.action warn`，
  未启用 `--collision.check-junctions`）
- 后果：紧急制动、非法插入等警告被静默；"0 碰撞"只代表 SUMO 车辆碰撞检测。
- 修复方向：Stage 3 里默认打开警告并落盘；碰撞检测口径写进 `fairness-protocol.md`。

### D-09 无 CANCELLED / 重新规划 / 车辆消失处理（**中**）

- 后果：车辆 teleport 或提前到达（`arrive`）后其预约仍在窗口内，
  后续车辆按旧窗口避让；Shadow 侧有 `gone/gone_inside` 事件，控制侧未消费。

### D-10 `departPos="random"` 触发的 forced vehicle 未分类统计（**中**）

- 现状：`too_close` 与 `forced` 有计数，但没有"因场景初始化（车已过停止线）"与
  "因控制器来不及"两类分开。
- 修复方向：按 `departPos=random` 生成时是否跨越停止线分类统计，见任务书 §4.2-E。

### D-11 测试覆盖不足（**中**）

- `test_logic.py` 覆盖：冲突矩阵、FIFO tie-break、重复请求、tracker 生命周期、Shadow 状态、
  以及"actuation 只出现在 control.py"静态检查。
- **未覆盖**：时间窗重叠/不重叠、同一/不同冲突点、crossing vs merge、预约释放、车尾离开、
  出口拥堵、速度变化导致 ETA 变化、取消预约。⇒ 不满足任务书 §4.3 的测试清单。
- 修复方向：Stage 3 增加 `tests/test_booking_windows.py` 等**纯逻辑**单测（无需 TraCI）。

### D-12 扫描脚本的健壮性（**中，工程性**）

- `experiments/run_fcfs_sweep.py:95-115`：子进程若因 SUMO 崩溃而异常退出，
  只会写 `status=error`；实测崩溃时表现为 `imap_unordered` 卡在某个 worker
  （日志中出现连接重置 + 堆损坏，主进程不退出）。
- 修复方向：给每次 `control.run` 加 wall-clock 超时 + `traci.close()` 保护，
  并对 `status=error` 的 run 记录 stderr 片段。

---

## 2. Stage 3 建议的最小修复顺序

1. **D-03**（先止血：`resume()` 只对成功 setStop 的车调用）→ 崩溃应消失；
2. **D-01**（窗口带非零）与 **D-02**（间隔不重复叠加）→ 安全性与吞吐同时受影响，必须先确认真实语义；
3. **D-04 / D-05**（状态机 + 偏差统计）→ 让"预约是否被兑现"可自查；
4. **D-11**（纯逻辑单测）→ 上述三项都要有回归测试；
5. **D-06 / D-07**（出口与队列模型）→ 只在这之后调，且必须报告碰撞率变化；
6. **D-08 / D-09 / D-10 / D-12**（可审计性与工程稳健性）。

## 3. 明确不做

- 不为提高吞吐而删除或缩小安全间隔；
- 不把 `Δt_safe` / 粒度 / 控制手段做成消融矩阵（任务书 §10.7、§10.8）；
- 不用旧的不完整扫描（227/450）出任何论文数字。
