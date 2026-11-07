# PSL 复现记录（PBS + SIPP + LP）

- 文档状态：**Stage 1 完成（克隆 + 许可证/依赖审计 + 编译尝试）**；Stage 2（单样例）**未开始**
- 上游登记：见 `third_party/UPSTREAMS.md` §2
- 上游 commit：`5686e15092fd95a46309a118655a5ab0c23c60fa`（分支 **`AAAI22_PBS-SIPP`**，2022-08-18）
- 本地路径：`third_party/_local/AIM-PSL/`（未入库、未修改、pristine）

> 分级同 `psb-reproduction.md`：**【已验证】** / **【当前实现】** / **【计划】** / **【未解决】**。

---

## 1. 【已验证】已完成的事情

| # | 事项 | 证据 |
|---|---|---|
| 1 | 克隆成功 | 退出码 0；494 MB；`git rev-parse HEAD` = `5686e15…` |
| 2 | 默认分支记录 | **`AAAI22_PBS-SIPP`**（不是 `main`）；**未切换分支** |
| 3 | 许可证检查 | 无 `LICENSE`/`COPYING`/`NOTICE` ⇒ 无再分发权 |
| 4 | 依赖审查 | C++14 + CMake≥3.10 + Boost + **CPLEX/Concert**（`/opt/ibm/ILOG/CPLEX_Studio1210`） |
| 5 | CMake 配置 | `Configuring done / Generating done` |
| 6 | 编译尝试 | **失败**：`SIPP.cpp:9  fatal error: ilcplex/ilocplex.h`（`Instance/PTNode/PBS/Driver.cpp` 已编译通过，仅告警） |
| 7 | 目录作用确认 | `PBS-SIPP-ver2`（主体）/ `PBS-SIPP-ver2-BFS`（变体）/ `MILP-FCFS`+`src`（MILP、FCFS 对照）/ `Controller`（批量脚本）/ `SUMO`（作者自带 net） |
| 8 | **Controller 规模确认** | `range(1)` + `range(99)` = **100 次**；内含 `range(4,30,5)` = 6 个车辆数档 ⇒ **禁止直接运行** |
| 9 | 输入/输出格式确认 | 输入 JSON 与 PSB **同构**；输出 `output.txt` 每车一行 schedule（无 Bézier 列） |
| 10 | 预编译二进制确认 | `PBS-SIPP-ver2/AIMPBS`（41.7 MB）为静态链接，`ldd` **无** cplex 动态依赖 |

**没有做的事（不得声称完成）**：未编译出可执行文件、未运行任何样例（**包括未运行那个预编译 `AIMPBS`**）、
未产生本轮实验数据。

## 2. 【未解决】两个阻塞

### 2.1 重新编译：缺 CPLEX（确定）

与 PSB 同源：LP 求解在 `SIPP.cpp:205-223`，无 CPLEX 无法编译。
选项 A/B/C 见 `third_party/UPSTREAMS.md` §3，**需作者决定**。

### 2.2 运行：预编译 `AIMPBS` 是否可用（**待 Stage 2 验证**）

- 有利证据：ELF 静态链接，`ldd` 无 `libcplex.so` 依赖，说明 `libcplex.a` 已链入。
- 风险：CPLEX **静态库在运行期仍可能校验许可**（尤其超过 Community Edition 规模时）；
  其 12.10 版本的运行时行为无法从源码判断。
- 因此：允许在 Stage 2 **单次、小规模**试跑以判定可用性；
  **不得**据此声称"PSL 已复现"，也不得用它跑批量实验。

## 3. 【计划】Stage 2 的单样例复现方案（待批准，勿执行）

上游 `Driver.cpp` 的调用约定（已验证）：

```cpp
int step = atoi(argv[1]);              // 车辆数（agent 数），不是 -k 参数
Instance instance("intro_graph_3.json");   // 硬编码
instance.loadVehicles("vehicleArrival.json", step);  // 硬编码
pbs.run("output.txt");                 // 硬编码
```

⇒ 必须在 `PBS-SIPP-ver2/` 目录内运行，且**只给一个位置参数**：

```bash
cd third_party/_local/AIM-PSL/PBS-SIPP-ver2
./AIMPBS 4          # 参数是"档位值 step"，loadVehicles 用 i<=step，故实际载入 5 辆车
```

（若改用重新编译的版本，则用 `third_party/_local/_build/psl-pbs/AIMPBS 4`。）

需要记录：`argv`、wall time（stdout 打印秒数）、`output.txt` 行数与内容、
`model.lp`/`solution` 是否生成、是否出现 CPLEX 许可报错、退出码。

**禁止**：`python Controller/controller.py`（100 次）、`PBS-SIPP-ver2-BFS` 与 `MILP-FCFS` 的批量跑。

## 4. 【未解决】SUMO 适配的接口缺口

| 缺口 | 说明 |
|---|---|
| 图模型与 SUMO 路网不同 | 上游用**顶点=冲突点**的自定义图（`WSR_0…` 命名，`vertex_conflicts` 显式列出），SUMO net 用 lane/connection；映射需显式构造，不能按名字猜 |
| 无逐时刻轨迹 | `output.txt` 只有进入/离开时刻、平均速度；`ReservationTable.txt` 为二进制 |
| 批处理 vs 在线 | 上游对给定车辆集合一次性规划；DSIP/FCFS 每 0.1 s 决策 |
| 车道语义 | `vehicleArrival.json` 的 `lane` 字段是 0–3 的入口车道编号，与 SUMO `laneIndex` 的对应关系**未验证** |

## 5. 下一步（最小动作）

1. 作者决定 CPLEX 方案；
2. Stage 2：单次 `./AIMPBS 4`，判定预编译二进制可用性 + 记录输出；
3. 用 `output.txt` 评估"能否构造 SUMO 可执行速度曲线"，
   并据此在 `sumo-adaptation-design.md` 中定死映射规则（**不得凭文件名猜**）。
