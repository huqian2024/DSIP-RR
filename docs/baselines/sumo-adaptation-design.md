# PSB / PSL → SUMO 适配设计（DRAFT，尚未实现）

- 版本：**v0（设计草案，2026-11-07）**
- 状态：**【计划】**。目前**没有任何一行适配代码**，也**没有任何一次接入验证**。
- 前置：`docs/baselines/psb-reproduction.md`、`psl-reproduction.md` 的 Stage 2 必须先通过。
- 铁律：上游 `third_party/_local/*` 保持 pristine；所有适配代码在此路径下：

```text
baselines/
├── psb_sumo/     # PSB 适配（instance 生成 + 结果解析 + SUMO 执行）
├── psl_sumo/     # PSL 适配（同上）
└── common/       # 统一请求/结果/指标接口（与 fcfs_sumo 共享）
```

---

## 1. 统一下行接口：车辆请求（`VehicleRequest`）

字段必须**来自实际 SUMO 配置**，不许凭空设默认值。

```python
@dataclass(frozen=True)
class VehicleRequest:
    vehicle_id: str            # SUMO vehID
    request_time: float        # s，进入控制区时刻（口径须与 FCFS/D 项一致）
    entry_edge: str            # e.g. "west2center"
    entry_lane: int            # SUMO laneIndex
    exit_edge: str             # e.g. "center2east"
    exit_lane: int
    turning_movement: str      # "left" | "straight" | "right"
    initial_speed: float       # m/s
    vehicle_length: float      # m, 5.0  (types.typ.xml)
    vehicle_width: float       # m, 未在 vType 中给出 -> 需作者确认（见 §5）
    max_acceleration: float    # m/s^2, 1.0 (vType accel)
    max_deceleration: float    # m/s^2, 4.5 (vType decel)
    speed_limit: float         # m/s, 13.9 (vType maxSpeed)
```

**已验证的来源**：`scenarios/original/types.typ.xml` 给出
`accel=1.0 / decel=4.5 / length=5.0 / minGap=3.0 / maxSpeed=13.9 / tau=2.0 / carFollowingModel=IDM`。
`vehicle_width` **不在** vType 中 ⇒ 标 **NOT VERIFIED**，不得编造。

## 2. 统一交叉口描述（`IntersectionModel`）

上游 PSB/PSL 需要的是"**顶点图**"而非 SUMO 的 lane/connection：

```jsonc
// intro_graph_3.json（上游格式，已验证）
{"vertices":[{"name":"WSR_0","pos":[-7.3152,-5.4864],"vertex_conflicts":["WER_0"]}, ...]}
```

因此适配器要做的是 **SUMO net → 顶点图** 的显式映射，包含：

| 需要的东西 | SUMO 来源 | 状态 |
|---|---|---|
| 入口/出口车道 | `<edge>`/`<lane>` | 可解析 |
| 连接关系（from→via→to） | `<connection from to fromLane toLane via>` | 可解析（`conflicts.py` 已用同样方式） |
| 内部车道形状/长度 | `<edge function="internal">` 的 lane `shape`/`length` | 可解析 |
| 冲突点坐标 | 内部 lane 中心线的几何交点 | 可解析（`conflicts.py` 的方法可复用） |
| 顶点命名 `WSR_0…` | **无对应** | **必须自建映射表并声明**，不能按名字猜 |
| 车辆尺寸/运动学 | `types.typ.xml` | 可解析（宽度除外） |

**关键决策（待作者确认）**：顶点图是"重新生成一份"（我们自己从 net 导出 JSON），
还是"沿用上游 `intro_graph_3.json` 并只做名字对齐"？
前者可复现、可审计；后者省事但依赖上游坐标语义未证实。

**当前建议**：从 `scenarios/original/cross{2,3,4}.net.xml` **程序化生成**顶点图，
与上游 `intro_graph_3.json` 做交叉核对（顶点数、冲突对数）后再生效；
差异必须记录，不允许"看起来差不多"就通过。

## 3. 统一输出契约（`PlanningResult`）

```python
@dataclass
class PlanningResult:
    method: str                     # "psb" | "psl" | "fcfs" | "dsip"
    upstream_commit: str
    vehicles: list[VehiclePlan]     # 每车一条
    output_kind: str                # "search_stats_only" | "schedule_only" | "trajectory_available"
    solver_runtime_s: float         # 求解耗时（与 SUMO 仿真时间严格分开）
    feasible: bool | None
    raw_output_path: str

@dataclass
class VehiclePlan:
    vehicle_id: str
    entry_time: float | None        # "In Time"
    exit_head_time: float | None    # "Out Time Head"
    exit_tail_time: float | None    # "Out Time Tail"
    speed: float | None             # 上游给出的平均速度
    control_points: list | None     # 仅 PSB 有（Bézier）
```

**已核实的真实可用字段**（来自上游 `output.txt` 表头，PSL 与 PSB 共有前 10 列）：

```
In Point;Out Point;Length;Earliest Arrival;In Time;Out Time Head; Out Time Tail;Time spend; Speed;Importance
```

PSB 额外有 `Optimal T; Start Time; Control Points;`。

⇒ **当前可诚实声明的等级**：`schedule_only`（PSB 可能升级到"带控制点"，但不是时间索引轨迹）。
**没有任何证据**表明上游能输出 `trajectory_available`。

## 4. SUMO 执行层（最难的一步）

上游输出的是**时刻表**，SUMO 需要**每步速度**。可选做法：

| 方案 | 做法 | 风险 |
|---|---|---|
| E1 `setStop` 到停止线 + 按时刻 `resume` | 复用 FCFS 已验证的 `setStop/resume`（TraCI 写入已验证可用） | 只保证"进入时刻"，区内速度由 IDM 决定，无法兑现上游的 `Speed` |
| E2 `slowDown()` 柔化 | 提前减速使得到达时刻贴近 `In Time` | 精度依赖步长；可能破坏 SUMO 跟驰安全 |
| E3 `moveToXY()` 直接置位 | 按轨迹强制移动 | **改变车辆动力学语义**，会绕过碰撞检测，**不作为主方案** |
| E4 只做离线映射评估 | 不做闭环，只把 `schedule` 与 SUMO 的"无控制基线"比较 | 最诚实，但结论弱 |

**当前建议**：Stage 4 先做 E1（复用已验证的 TraCI 写入），并**同时**记录
"上游计划时刻 vs SUMO 实际时刻"的偏差分布；若偏差过大，退回 E4 并如实说明。

## 5. 未解决问题清单（阻塞 Stage 4）

1. CPLEX 落地方式（`third_party/UPSTREAMS.md` §3）。
2. 顶点图：自建还是沿用上游（§2）。
3. `vehicle_width` 无来源 ⇒ 若上游公式用到宽度，必须请作者给值。
4. 上游 `lane`（0–3）↔ SUMO `laneIndex` 的对应（未验证）。
5. 上游是**单交叉口 4 进口**图；DSIP 场景是 2/3/4 车道/进口 ⇒ 顶点图规模差异大，
   映射规则必须能扩展到 3/4 车道（上游只有一套图数据）。
6. 规划时间 vs 仿真时间不可混用：上游 `runtime` 是**离线求解**耗时，
   与 1000 s 交通仿真无可比性。

## 6. 明确不做

- 不修改上游算法、不改其 CMake 之外的任何文件；
- 不伪造轨迹（不允许由 `Speed` 列插值出一份"轨迹"当成上游输出）；
- 不在没有碰撞/完成率数据的情况下声称"已接入 SUMO"。
