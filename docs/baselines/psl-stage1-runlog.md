# PSL 运行证据记录（Stage 0–3，2026-11-14）

- 分级：**【已验证】**（本机实测，有命令与产物）/ **【未验证】** / **【阻塞】**
- 上游：`https://github.com/theanhhoang/AIM.git`，分支 **`AAI22_PBS-SIPP`**
  commit **`5686e15092fd95a46309a118655a5ab0c23c60fa`**
- 本地只读 checkout：`third_party/_local/AIM-PSL/`（**pristine**，`git status --porcelain` 为空）
- 所有运行都在**工作区内**的 scratch/结果目录执行，未写入 `third_party/`
- 原始产物的入库存档状态见本文 §7（`results/**` 默认不入库，见 `.gitignore`）

---

## 1. 【已验证】环境结论：CPLEX 缺失，但预编译二进制可运行

```bash
ls /opt | grep -i ibm        # 空
command -v cplex             # 空
python3 -c "import cplex"    # ModuleNotFoundError
env | grep -i cplex          # 空
```

因此**仍然不能重新编译**（`SIPP.cpp:9 fatal error: ilcplex/ilocplex.h`）。
但上游 `PBS-SIPP-ver2/AIMPBS` 是 **41.7 MB 的预编译 ELF**：

| 项 | 值 |
|---|---|
| `file AIMPBS` | ELF 64-bit LSB pie executable, x86-64, **with debug_info, not stripped** |
| `ldd AIMPBS` | 仅 `libdl/libstdc++/libm/libgcc_s/libpthread/libc`，**无 `libcplex.so`** |
| sha256 | `ef682e25d730876193b0ab7559b99723d8ecf19239b6b46967ea367f9b9d61b8` |
| 结论 | **CPLEX 已静态链入**，且 **CPLEX 12.10 运行期许可校验在本机通过** |

这是本轮最重要的状态变化：**"CPLEX 缺失"不再是 PSL 的阻塞**，
只阻塞"重新编译"（以及 PSB）。

**没有绕过任何许可机制**：使用的是上游分发的原始二进制，未打补丁、未设许可规避环境变量。

---

## 2. 【已验证】Stage 1：上游最小自检（5 辆车）

工作副本：`third_party/_local/_scratch/psl-stage1/`（仅放三个输入文件的副本；
二进制按绝对路径调用，不复制进工作区，也不复制进 `results/`）

```bash
SCRATCH=third_party/_local/_scratch/psl-stage1
mkdir -p "$SCRATCH"
cp third_party/_local/AIM-PSL/PBS-SIPP-ver2/{vehicleArrival.json,intro_graph_3.json,pairDistance_3.json} "$SCRATCH"/
cd "$SCRATCH"
/home/qian/DSIP-RR/third_party/_local/AIM-PSL/PBS-SIPP-ver2/AIMPBS 4   # i <= step ⇒ 载入 5 辆车
```

> 该目录只在 `third_party/*/` 内（已被 `.gitignore` 覆盖），可随时删除重建。
> 二进制本身**永不**复制进 `results/` 或入库（上游无再分发许可，且 41.7 MB）。

| 项 | 结果 |
|---|---|
| 退出码 | **0** |
| stderr | 0 字节 |
| 自报运行时间（stdout） | `0.011151`（另测 `0.010878/0.011395/0.009728`） |
| `output.txt` | 6 行（表头 + 5 车） |
| `model.lp` / `solution` | 均生成；`solutionStatusString="optimal"` |
| CPLEX 许可报错 | **无** |

### 2.1 确定性

同一输入连续运行 3 次：`output.txt` 与 `model.lp` 的 sha256 **完全一致**
（`98a5fd3d…`, `4b1449c7…`）⇒ 该二进制在本机是确定性的。

### 2.2 规模扩展（同一上游样例）

| step | 载入车数 | 输出行数 | 自报时间 (s) | CPLEX 状态 |
|---|---|---|---|---|
| 4 | 5 | 6 | 0.011 | optimal |
| 9 | 10 | 11 | 0.020 | optimal |
| 14 | 15 | 16 | 0.040 | optimal |
| 19 | 20 | 21 | 0.041 | optimal |
| 24 | 25 | 26 | 0.053 | optimal |

### 2.3 发现：上游遗留产物与当前输入不匹配（**只记录，不修改**）

`PBS-SIPP-ver2/` 里已有的 `output.txt`/`model.lp`/`solution` 是**上游作者自己**跑出的遗留物，
其 `Length` 列（如 `EWL_0→EWL_7 = 19.812`）与我们用**当前** `intro_graph_3.json` +
`pairDistance_3.json` 跑出的 `14.6304` **不同**。⇒ 上游仓库内的示例产物并非由当前 committed
输入生成。**不作为任何证据使用**，也不修改。

---

## 3. 【已验证】上游模型的硬约束（读源码确认，决定适配方案）

| 约束 | 出处 | 后果 |
|---|---|---|
| 输入文件名硬编码 `intro_graph_3.json` / `pairDistance_3.json` / `vehicleArrival.json` | `Driver.cpp:16-18`, `Instance.cpp:12` | 每次运行必须在**独立目录**，并用这些文件名 |
| `bool samePoint[104][104]`，`loadSamePoint()` 固定循环 104 | `Instance.h:114`, `Instance.cpp:260` | **顶点数必须 ≤ 104**，否则越界 |
| 方向由**名字子串**判定：`EW/WE/NS/SN`→直行、`EN/WS/NW/SE`→右转、其余→左转 | `Instance.cpp:163-181` | 顶点命名必须满足该分类器 |
| `v_min=3`, `v_max=15`, `length=5` 硬编码 | `Instance.cpp:86-88` | **与 `types.typ.xml` 的 `maxSpeed=13.9` 不一致**（见 §5-D2） |
| `w=7`，右转半径 `10*0.3048 m`，左转半径 `40*0.3048 m` | `SIPP.h:77-79` | 冲突点占用时长口径 |
| `getConflictPoints(trajectory[0])[0]` | `PBS.cpp:268`, `PTNode.cpp:287` | **入口顶点若冲突列表为空 ⇒ 段错误** |

最后一条是本轮实测踩到的真实崩溃：第一次把几何图喂给二进制时 **exit code = -11 (SIGSEGV)**。
原因是我最初按"同一物理点才算冲突"建模，导致部分入口顶点无冲突伙伴；
上游则把**同一进口的所有车道折叠到一个入口点**。按上游语义折叠后即正常。

---

## 4. 【已验证】Stage 3：SUMO → PSL 适配（新增 `baselines/psl_sumo/`）

上游图模型是**理想化几何**（全部进口车道塌缩到一点、6 ft 车道间距），
不能描述 `cross{2,3,4}.net.xml`。因此**从 SUMO net 程序化生成**等价图，而不是给上游顶点改名字。

| 模块 | 作用 |
|---|---|
| `baselines/psl_sumo/net_to_graph.py` | net + connections → `graph.json` / `pairDistance.json` / `paths.json` / `instance_report.json`；自检方向分类、冲突对称性、顶点预算、入口必有冲突 |
| `baselines/psl_sumo/demand.py` | `.rou.xml` → `vehicleArrival.json`（用一次**无信号控制**的 SUMO 参考运行取 FCD/vehroute，再按匀加速运动学算自由流到达时刻） |
| `baselines/psl_sumo/run_psl.py` | 在独立运行目录里以硬编码文件名装配输入、调用 `AIMPBS`、解析 `output.txt` → `plan.csv` + `run_manifest.json` |
| `baselines/psl_sumo/validate_plan.py` | **独立重新推导** `SIPP.cpp:183-380` 的冲突点占用窗，逐对检查是否重叠（不读求解器的预约表） |

### 4.1 图生成结果（`lane_mode=movement`，入口/出口按进口/出口边折叠）

| net | junction | 运动数 | 顶点数 | 顶点预算 | 冲突顶点对 | 自检 |
|---|---|---|---|---|---|---|
| `cross2.net.xml` | center | 12 | 56 | 104 | 40 | ✅ |
| `cross3.net.xml` | center | 12 | 56 | 104 | 40 | ✅ |
| `cross4.net.xml` | center | 12 | 56 | 104 | 40 | ✅ |

- 12 个运动 = 4 进口 × (左/直/右)，U-turn 排除（`routes.rou.xml` 中不存在）
- 每个运动顶点数：右转 2、直行 6、左转 6
- **右转运动没有"内部"冲突点**：`WSR`/`ENR`/`SER`/`NWR` 各只有 2 个顶点（入口、出口），
  二者都只与**同进口/同出口**的运动共享 —— 即右转不穿过任何对向或横向车流。
  这与"右转常绿/让行"的口径一致（对应稿件 Table II 的讨论）。
- 顶点 ≤ 104 是**硬预算**（§3），四个进口扩展到 4 车道仍是 56

### 4.2 端到端运行（cross3，`lanes3_density1`，seed 81890，参考窗 0–40 s）

| run id | 车数 | 退出码 | 求解器自报 (s) | CPLEX | 计划行 | 冲突顶点对检查 | 冲突违规 |
|---|---|---|---|---|---|---|---|
| `psl-cross3-n15-s81890` | 15 | 0 | 0.067 | optimal | 15 | 64 | **0** |
| `psl-cross3-n25-s81890` | 25 | 0 | 0.208 | optimal | 25 | 175 | **0** |

指标（**仅规划侧**，不是 SUMO 交通侧指标）：

| 指标 | n=15 | n=25 |
|---|---|---|
| 平均控制延误 `in_time − earliest_arrival` (s) | 1.680 | 2.636 |
| 最大控制延误 (s) | 4.761 | 7.202 |
| makespan（最后一车尾部离场）(s) | 16.235 | 22.017 |
| 平均速度 (m/s) | 15.00 | 14.86 |
| 平均区内行程时间 (s) | 1.437 | 1.440 |

### 4.3 可重复性

- **求解器层**：同一输入连续 3 次，`output.txt` 与 `model.lp` 的 sha256 完全一致。
- **端到端层**：在**全新目录**（含重新生成一次 SUMO 参考运行）复跑整条管道，
  `plan.csv` 的 sha256 与既有结果**完全相同**：`d82b38f157b9bfb5d2288c4053c0f24a492e951a947bcb8980e0dec6be888bfa`
  （对应 `results/psl_stage3/runs/psl-cross3-n15-repeat{1,2}/` 与 `…-s81890/` 三个目录）。
  ⇒ 参考运行的 seed 81890 足以锁定到达时刻序列，管道确定性可复现。

---

## 5. 【未验证】/ 偏离与限制（必须随任何数字一起引用）

- **D1 不是闭环交通仿真。** 目前只做到"SUMO 场景 → PSL 计划表"，**没有**把计划回灌 SUMO 执行。
  因此**不能**报告吞吐、平均行程时间、碰撞数等交通侧指标。`output_kind = schedule_only`。
- **D2 运动学偏离。** PSL 二进制硬编码 `v_max=15 m/s`、`length=5`、`v_min=3`，
  而 `types.typ.xml` 是 `maxSpeed=13.9`。本轮 n=15 的 15 辆车全部被规划在 **15.0 m/s**，
  **超过场景限速**。这不是可以忽略的细节：论文中必须披露，或作为后续修正项。
- **D3 车道抽象。** `lane_mode=movement` 每个运动只取**中位车道**几何；
  同一运动内其它车道的横向偏移未建模。上游同样只建 2 条直行车道。
- **D4 入口/出口折叠是保守设定。** 同一进口的运动共享一个入口冲突点、同一出口边共享一个出口冲突点，
  因此同进口车辆**不可能同时**进入。这会推高延误，属于上界口径，**不是** PSL 的最好表现。
- **D5 批规划 vs 在线规划。** 上游对给定车辆集合**一次性**求解；DSIP/FCFS 每 0.1/0.4 s 重规划。
  这是**不同问题设定**，不得包装成纯算法优劣（见 `fairness-protocol.md` §2）。
- **D6 到达时刻是模型量。** `arrivalTime` 由 FCD 首帧（位置/速度/车道）+ 匀加速运动学推出，
  未含排队；参考运行本身**无信号控制且发生了碰撞**（60 s 内 6 次），
  它**只用于取时刻**，**不能**当作安全参照。
- **D7 参考运行的时窗/车辆数为人工选择**（0–40 s，取最早 15/25 辆）。
  这不是密度矩阵，也没有多 seed。

### 5.1 作者要求的 8 项指标：当前可获得性（**必须如实对照**）

| # | 指标 | 当前状态 | 缺口 |
|---|---|---|---|
| 1 | Throughput | **不可得** | 需执行层（B2）+ 完整 1000 s 运行 |
| 2 | Average travel time | **不可得** | 同上 |
| 3 | Average delay | **仅规划侧代理**：`in_time − earliest_arrival`（1.680 / 2.636 s） | 不是 tripinfo 口径的延误 |
| 4 | Average speed | **仅规划侧**：规划速度 15.00 / 14.86 m/s | 不是 SUMO 实测速度；且超限速（D2） |
| 5 | Planning/computation time | **已得**：0.067 / 0.208 s（15/25 车，CPLEX `optimal`） | 需在多密度下统计分布 |
| 6 | Collision count | **不可得** | 需执行层 + SUMO 碰撞检测 |
| 7 | Timeout/failure count | **已部分得**：本轮 0 次超时、0 次失败（exit 0，`optimal`） | 需压力场景（更大批、更密需求） |
| 8 | Deadlock / 无法完成规划 | **已部分得**：本轮 0 次（`pbs.run` 未打印 `no solution`） | 同上 |

⇒ **不得**把 3/4 的规划侧代理值写成"平均延误/平均速度"的交通侧结果。
**不得**在 1/2/6 缺位时声称 PSL 的交通性能。

---

## 6. 【阻塞】与下一步

| # | 事项 | 状态 |
|---|---|---|
| B1 | 重新编译 PSL | **阻塞**：需 CPLEX（学术许可，须作者本人获取）。当前用预编译二进制替代，已披露 |
| B2 | 计划回灌 SUMO（E1：`setStop`/`resume` 执行 `In Time`） | **未实现**，是拿到交通侧指标的前提 |
| B3 | 滚动窗口批规划（每 0.4 s 用当前在途车辆重解） | **未实现**，是与 DSIP 公平比较的前提 |
| B4 | 多 seed / 多密度 | **未启动**，按闸门须先通过 B2/B3 |

**下一最小动作**：实现 B2（E1 执行层）+ 记录"计划 `In Time` vs SUMO 实际进入时刻"的偏差分布。
若偏差不可接受，则退回"规划侧对比"并如实说明（`sumo-adaptation-design.md` §4 的 E4）。

---

## 7. 产物位置与入库策略

| 路径 | 内容 | 入库 |
|---|---|---|
| `results/psl_stage3/instance_cross{2,3,4}/` | `graph.json`、`pairDistance.json`、`paths.json`、`instance_report.json` | `results/**` 默认忽略（`.gitignore`），**可用脚本完全再生** |
| `results/psl_stage3/demand_cross3{,_n25}/` | `vehicleArrival.json`、`request_manifest.json`、`fcd.xml`、`vehroute.xml`、`reference_sumo.log` | 同上 |
| `results/psl_stage3/runs/<run_id>/` | `plan.csv`、`output.txt`、`model.lp`、`solution`、`stdout.log`、`stderr.log`、`run_manifest.json`、`validation.json` | 同上 |
| `third_party/_local/_scratch/psl-stage1/` | Stage 1 自检产物 | `.gitignore` 覆盖（`third_party/*/`） |
| `baselines/psl_sumo/*.py` | 适配代码 | **入库** |

复跑命令（全部在工作区内）：

```bash
python3 baselines/psl_sumo/net_to_graph.py \
  --net scenarios/original/cross3.net.xml --out-dir results/psl_stage3/instance_cross3
python3 baselines/psl_sumo/demand.py \
  --net scenarios/original/cross3.net.xml \
  --rou scenarios/flows/lanes3_density1.rou.xml \
  --typ scenarios/original/types.typ.xml \
  --instance-dir results/psl_stage3/instance_cross3 \
  --out-dir results/psl_stage3/demand_cross3 --end 40 --limit 15
python3 baselines/psl_sumo/run_psl.py \
  --instance-dir results/psl_stage3/instance_cross3 \
  --demand-dir results/psl_stage3/demand_cross3 \
  --run-dir results/psl_stage3/runs/psl-cross3-n15-s81890
python3 baselines/psl_sumo/validate_plan.py \
  --plan results/psl_stage3/runs/psl-cross3-n15-s81890/plan.csv \
  --graph results/psl_stage3/instance_cross3/graph.json \
  --paths results/psl_stage3/instance_cross3/paths.json
```

输入校验值（本轮实测）：

| 文件 | sha256 |
|---|---|
| `AIMPBS` | `ef682e25d730876193b0ab7559b99723d8ecf19239b6b46967ea367f9b9d61b8` |
| `scenarios/original/cross3.net.xml` | `4b3ee93de59a9424b66af3b4327ba3d16c1a64fa57db2a4373f9ed5f0bb2ffdf` |
| `scenarios/flows/lanes3_density1.rou.xml` | `c19ee68dbc11587a531ce12d0243d5e87c0391cb3fa62c1d0be35084f31766a6` |
| `scenarios/original/types.typ.xml` | `bdd4fc28bb0e132720d07b5eda19801113de487b90b4636ad1a2561b9a516c5f` |
