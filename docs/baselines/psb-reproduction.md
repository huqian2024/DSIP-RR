# PSB 复现记录（Intersection domain）

- 文档状态：**Stage 1 完成（克隆 + 许可证/依赖审计 + 编译尝试）**；Stage 2（单样例）**未开始**
- 上游登记：见 `third_party/UPSTREAMS.md` §1
- 上游 commit：`0b3f6eb34bf69a6d6d6a0fc2db5505073c90af24`（分支 `main`，2024-02-22）
- 本地路径：`third_party/_local/PSB-RAL/`（未入库、未修改、pristine）

> 本文件严格区分：**【已验证】**（本机实测）/ **【当前实现】** / **【计划】** / **【未解决】**。
> 任何"已完成"表述都必须有对应命令输出作依据；否则一律写"未开始"。

---

## 1. 【已验证】已完成的事情

| # | 事项 | 证据 |
|---|---|---|
| 1 | 克隆成功 | `git clone` 退出码 0；`du -sh` = 29 MB；`git rev-parse HEAD` = `0b3f6eb…` |
| 2 | 分支/commit/日期记录 | `main` / `0b3f6eb34bf69a6d6d6a0fc2db5505073c90af24` / 2024-02-22 |
| 3 | 许可证检查 | 仓库内**无** `LICENSE`/`COPYING`/`NOTICE` ⇒ 无再分发权 |
| 4 | 依赖审查 | C++14 + CMake≥3.10 + Boost(program_options/system/filesystem) + **CPLEX/Concert** |
| 5 | CMake 配置 | `cmake -S … -B …` → `Configuring done / Generating done`（Boost 1.82.0 由 conda 提供） |
| 6 | 编译尝试 | **失败**：`fatal error: ilcplex/ilocplex.h: No such file or directory`（`include/SIPP.h:11`） |
| 7 | 输入格式确认 | `instances = intro_graph_3.json` + `pairDistance_3.json` + `vehicleArrival*.json` |
| 8 | 输出格式确认 | `output.txt` = 每车 schedule（含 Bézier `Control Points`）；`-c` CSV = 搜索统计 |
| 9 | 上游陷阱记录 | `-m` 与 `-o` 参数**被 `Driver.cpp` 忽略**（硬编码 `./data/intro_graph_3.json`、`output.txt`） |

**没有做的事（不得声称完成）**：未编译出可执行文件、未运行任何样例、未产生任何本轮实验数据。

## 2. 【未解决】阻塞：CPLEX

PSB 的 LP 求解嵌在 `src/SIPP.cpp` 内（`IloModel`/`IloCplex`，用于安全区间速度剖面），
是算法本体而非可选组件 ⇒ **无 CPLEX 即无法编译**，也不存在预编译二进制可替代。

处置选项（A/B/C）见 `third_party/UPSTREAMS.md` §3，**需作者决定**。
在作者决定前，Stage 2 的 PSB 单样例复现**不可能进行**。

## 3. 【计划】Stage 2 的单样例复现方案（待批准，勿执行）

目标：仅验证"上游代码在本机可运行且输出可解读"，不做任何性能比较。

```bash
# 前提：CPLEX 就绪，且已用我们自己的 CMakeLists 编译出 AIMPSB
cd third_party/_local/PSB-RAL/Intersection/PSB-Intersection
# 官方示例（README）：3 车以上规模，避免大实例
../../_build/psb-intersection/AIMPSB -k 10 \
  -a ./data/500vphpl/vehicleArrival_500vphpl_random1.json \
  -c /tmp/psb_stats.csv
```

需要记录：输入文件名与 sha256、命令行、wall time、`-c` CSV 全部列、`output.txt` 前若干行、
`solution cost / delay`、是否 feasible、是否触发 CPLEX 许可限制。

**注意**：`-m` 无效（硬编码），所以不要用 `-m` 声称"换了地图"。

## 4. 【未解决】SUMO 适配的接口缺口

| 缺口 | 说明 |
|---|---|
| 无时间索引轨迹 | `output.txt` 只给 **进入/离开时刻 + 平均速度 + Bézier 控制点**，没有逐时刻位置 |
| 控制点语义未核实 | `Control Points` 是否足以复原 SUMO 可执行速度曲线，**尚未验证**（需读 `berstein.cpp`） |
| 一次性批处理 | 上游是"一批车一次规划"，DSIP/FCFS 是**逐步在线**控制；时间对齐方式未定义 |
| 车辆数语义 | `-k` 是 agent 数；与 SUMO 的 flow 车辆数不是同一概念 |

结论：**当前不能声称 PSB 可接入 SUMO**。适配设计见 `docs/baselines/sumo-adaptation-design.md`。

## 5. 下一步（最小动作）

1. 作者决定 CPLEX 方案（A/B/C）；
2. 方案确定后：由 `baselines/psb_sumo/CMakeLists.txt` 编译（不碰上游），跑 §3 的单样例；
3. 根据 `output.txt` 实际内容判定是 `schedule_only` 还是可推导出 `trajectory_available`。
