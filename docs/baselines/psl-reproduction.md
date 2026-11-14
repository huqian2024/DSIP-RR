# PSL 复现记录（PBS + SIPP + LP）

- 文档状态：**Stage 0–3 完成（规划侧）**，2026-11-14 更新
- **P0 最高优先级任务**（见 `docs/HANDOFF.md` §15）
- 运行证据（命令、退出码、哈希、指标）：**`docs/baselines/psl-stage1-runlog.md`**
- 上游登记：见 `third_party/UPSTREAMS.md` §2
- 上游 commit：`5686e15092fd95a46309a118655a5ab0c23c60fa`（分支 **`AAAI22_PBS-SIPP`**，2022-08-18）
- 本地路径：`third_party/_local/AIM-PSL/`（未入库、未修改、pristine）
- 适配代码：`baselines/psl_sumo/`（新增，入库）

> **2026-11-14 状态变化（重要）**
> 1. **预编译 `AIMPBS` 已实测可运行**：exit 0、CPLEX `optimal`、无许可报错、确定性可复现。
>    ⇒ "缺 CPLEX" **不再是 PSL 的运行阻塞**，只阻塞"重新编译"（以及 PSB）。
> 2. **已在本项目 SUMO 路网（cross2/3/4）上端到端跑通**，15 车与 25 车两种规模，
>    并通过独立冲突可行性校验（64 / 175 对冲突顶点，**0 违规**）。
> 3. **但仍不是闭环交通仿真**：没有把计划回灌 SUMO，因此**不能**报告吞吐/行程时间/碰撞数。
> 4. 已知偏离：上游硬编码 `v_max=15 m/s`，高于 `types.typ.xml` 的 13.9。

> 分级：**【已验证】** / **【当前实现】** / **【计划】** / **【未解决】**。

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

**2026-11-07 时未做的事（当时）**：未编译出可执行文件、未运行任何样例、未产生实验数据。
**2026-11-14 已全部补齐**，见 §2–§3。

## 2. 【已验证】原两个阻塞的现状（2026-11-14）

### 2.1 重新编译：仍然缺 CPLEX（阻塞未解除）

与 PSB 同源：LP 求解在 `SIPP.cpp:205-223`，无 CPLEX 无法编译。
选项 A/B/C 见 `third_party/UPSTREAMS.md` §3，**仍需作者决定**。
**但本轮不再被它阻塞**，因为预编译二进制可用。

### 2.2 运行：预编译 `AIMPBS` **实测可用**（原风险已排除）

| 检查 | 结果 |
|---|---|
| 上游样例 `./AIMPBS 4`（5 车） | **exit 0**，stderr 0 字节，`solutionStatusString="optimal"` |
| CPLEX 许可报错 | **无**（CPLEX 静态链入，运行期校验通过） |
| 连续 3 次同输入 | `output.txt` / `model.lp` sha256 **完全一致**（确定性） |
| 5/10/15/20/25 车 | 全部 `optimal`，自报 0.011 / 0.020 / 0.040 / 0.041 / 0.053 s |
| 本项目 SUMO 图（cross3）15 / 25 车 | exit 0，`optimal`，0.067 / 0.208 s |

⇒ **可以说"PSL 的求解器在本机跑通了"**，但**不能说"PSL 基线已复现"**，
因为还缺闭环执行（§4）与多 seed/多密度（§5）。

## 3. 【已验证】Stage 1/2 的上游自检（已执行）

上游 `Driver.cpp` 的调用约定：

```cpp
int step = atoi(argv[1]);                    // 索引，不是车辆数
Instance instance("intro_graph_3.json");     // 硬编码
instance.loadVehicles("vehicleArrival.json", step);  // i <= step
pbs.run("output.txt");                       // 硬编码
```

⇒ 只给一个位置参数，且必须在**含这几个文件名的目录**里运行：

```bash
cd third_party/_local/_scratch/psl-stage1    # 独立副本，不动上游 checkout
./AIMPBS 4                                   # step=4 ⇒ 载入 5 辆车
```

**未执行且仍然禁止**：`python Controller/controller.py`（~100 次 × 6 档 × 3 方法）、
`PBS-SIPP-ver2-BFS` 与 `MILP-FCFS` 的批量跑。

## 4. 【部分解决】SUMO 适配的接口缺口

| 缺口 | 2026-11-14 状态 |
|---|---|
| 图模型与 SUMO 路网不同 | **已实现**：`baselines/psl_sumo/net_to_graph.py` 从 `*.net.xml` 程序化生成，不按名字猜 |
| 无逐时刻轨迹 | **仍未解决**：`output.txt` 只有进入/离开时刻 + 平均速度；无法据此重建 SUMO 速度曲线，只能靠 E1 执行层逼近 |
| 批处理 vs 在线 | **仍未解决**：上游一次性求解；需滚动窗口封装才能与 DSIP 公平比较 |
| 车道语义 | **已澄清**：`lane` 字段**二进制根本不读**（`Instance.cpp:44-95` 只读 `id`/`importance`/`arrivalTime`/`trajectory`）；因此车道对应问题不影响求解，但影响"实例是否忠实于 SUMO 车道"这一建模判断 |
| **入口顶点必须有冲突（新发现）** | **已解决**：`PBS.cpp:268` 对空冲突列表取 `[0]` 会段错误；`net_to_graph.py` 按上游语义折叠入口/出口点 |

## 5. 下一步（最小动作）

1. **E1 执行层**：把 `In Time` 变成 SUMO 的 `setStop`/`resume`，并记录
   "计划进入时刻 vs 实际进入时刻"的偏差分布；若偏差过大则退回纯规划侧对比。
2. **滚动窗口批规划**（每 0.4 s 用当前在途车辆重解）。
3. 通过后再谈 1 lane × 1 density × 3–5 seeds。
4. CPLEX 安装（可选，只为"能从源码复现"这一点；不装也能继续）。
