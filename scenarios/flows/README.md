# `scenarios/flows` — 15 组车流（5 档密度 × 3 种车道数）

生成脚本：`generate_flows.py`（**唯一来源** `scenarios/original/routes.txt`；
结构与非需求属性逐项复制自 `scenarios/original/routes.rou.xml`）。
重新生成：`python3 scenarios/flows/generate_flows.py`
独立校验：`python3 scenarios/flows/validate_flows.py`（不 import 生成器，直接从
`routes.txt` 重算期望值；当前结果 15/15 OK，退出码 0）

## 换算口径（作者确认，见 `docs/HANDOFF.md` §10.6）

| 项目 | 规则 |
|---|---|
| 车辆数 | `routes.txt` 数字 × **10**（= 1000 s 运行、每进口每方向） |
| 平均发车间隔 | **100 ÷ `routes.txt` 数字** 秒（= 括号值 ÷ 10） |
| 方向比例 | 直行 : 每个转向方向 = **2 : 1**（L:S:R = 1:2:1） |
| 视界 | `begin=0`、`end=1000` |
| 间隔分布 | `normal(μ, 1.0)`（沿用原文件约定；σ 未改动） |
| 其他属性 | `departPos="random"`、`departSpeed="random"`、`type="car"`、flow 种子 82339–82350（与原文件一致） |

## 文件清单（15 个）

| 文件 | 车道/进口 | 档 | 直行数 | 单转向数 | 直行间隔 | 转向间隔 | 全路网车辆/1000 s | 直行 veh/(h·lane) |
|---|---|---|---|---|---|---|---|---|
| `lanes2_density1.rou.xml` | 2 | 1 | 260 | 130 | 3.846 s | 7.692 s | 2080 | 468 |
| `lanes2_density2.rou.xml` | 2 | 2 | 340 | 170 | 2.941 s | 5.882 s | 2720 | 612 |
| `lanes2_density3.rou.xml` | 2 | 3 | 420 | 210 | 2.381 s | 4.762 s | 3360 | 756 |
| `lanes2_density4.rou.xml` | 2 | 4 | 540 | 270 | 1.852 s | 3.704 s | 4320 | 972 |
| `lanes2_density5.rou.xml` | 2 | 5 | 660 | 330 | 1.515 s | 3.030 s | 5280 | 1188 |
| `lanes3_density1.rou.xml` | 3 | 1 | 400 | 200 | 2.500 s | 5.000 s | 3200 | **480** |
| `lanes3_density2.rou.xml` | 3 | 2 | 500 | 250 | 2.000 s | 4.000 s | 4000 | **600** |
| `lanes3_density3.rou.xml` | 3 | 3 | 640 | 320 | 1.563 s | 3.125 s | 5120 | **768** |
| `lanes3_density4.rou.xml` | 3 | 4 | 800 | 400 | 1.250 s | 2.500 s | 6400 | **960** |
| `lanes3_density5.rou.xml` | 3 | 5 | 1000 | 500 | 1.000 s | 2.000 s | 8000 | **1200** |
| `lanes4_density1.rou.xml` | 4 | 1 | 520 | 260 | 1.923 s | 3.846 s | 4160 | 468 |
| `lanes4_density2.rou.xml` | 4 | 2 | 680 | 340 | 1.471 s | 2.941 s | 5440 | 612 |
| `lanes4_density3.rou.xml` | 4 | 3 | 840 | 420 | 1.190 s | 2.381 s | 6720 | 756 |
| `lanes4_density4.rou.xml` | 4 | 4 | 1080 | 540 | 0.926 s | 1.852 s | 8640 | 972 |
| `lanes4_density5.rou.xml` | 4 | 5 | 1320 | 660 | 0.758 s | 1.515 s | 10560 | 1188 |

`lanes3_*` 一列与论文 Table I 的 S 值（480/600/768/960/1200）**精确吻合**；
`lanes2_*` 与 `lanes4_*` 相差 ±12，来自整数取整（480×2/36 = 26.67 → 26）。

## 加载校验（2026-11-01，SUMO 1.12.0）

15 个文件全部 **rc=0**，无 XML/属性错误。示例：

```bash
sumo -n scenarios/original/cross3.net.xml \
     -r scenarios/flows/lanes3_density1.rou.xml \
     -a scenarios/original/types.typ.xml --end 100 --no-step-log true
```

⚠️ **网络与车流的实际配对尚未确认**：`cross1` 与 `cross2` 都是每进口 2 车道，
本表按 `lanes{n}` → `cross{n}.net.xml` 做校验；"论文 4/6/8 车道"对应哪一组仍为 NOT VERIFIED。

## 校验中发现的问题（重要）

在**无任何控制**的条件下，这 15 组车流都会产生 SUMO 碰撞（默认 `collision.action=teleport`），
且**100% 发生在出口车道汇流处**，交叉口内部（`:center_*`）为 **0**：

| 步长 | 碰撞数/100 s（lanes2 d1–d5） | （lanes3） | （lanes4） |
|---|---|---|---|
| 1 s | 8, 11, 16, 16, 4 | 9, 5, 6, 11, 5 | 8, 5, 11, 12, 7 |
| 0.1 s | 10, 16, 17, 12, 12 | 11, 12, 11, 12, 13 | 14, 7, 8, 12, 10 |

- **不是步长伪影**：0.1 s 下依然出现（有时更多）。
- 碰撞对与 Task 04 识别的 8 对"共享出口车道"完全对应，例如
  `flow_we`(直行) + `flow_se`(右转) → `center2east`；`flow_nw`(右转) + `flow_ew`(直行) → `center2west`。
- 因此：(a) 这些"无控制"运行**不能**作为"零碰撞基线"；(b) FCFS 的资源除"交叉口内部通过"外
  **必须覆盖出口车道汇流**；(c) 论文中历史"无碰撞告警"的结论与本条件不可比。

## 尚未决定（不阻塞生成，但阻塞实验）

1. **步长** 1 s 还是 0.1 s（论文写 0.1 s）。
2. **σ** 是否保持固定 1 s。高密度档（直行间隔 < 3 s）会抽到**负间隔**，被 SUMO 变成"立即出发"，
   造成成批同时发车；受影响文件已在生成脚本输出中列出。
3. **`departLane`**：默认 `first` 使直行车全部从最右车道进入，加剧出口汇流；
   是否改为 `best` 属交通输入变更。
4. **车道数 ↔ 网络文件映射**（`cross1` 与 `cross2` 同为 2 车道）。
5. 是否需要对应的 `.sumocfg`（本轮未生成，避免把未决定的步长写进配置）。
