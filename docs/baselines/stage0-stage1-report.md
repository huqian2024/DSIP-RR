# Stage 0 / Stage 1 执行报告（2026-11-07）

> 本文件是**本轮的第一份证据记录**。Stage 0 = 仓库与环境审计（不跑仿真）；
> Stage 1 = 克隆 + 许可证/依赖审计 + 原始编译尝试。
> **Stage 2 及之后未执行**，等待作者确认。

---

## 1. 目标与范围

- 按任务书 §7：先做 Stage 0（只检查），再做 Stage 1（只克隆与编译）。
- 未运行任何仿真实验、未改任何研究代码、未改 `scenarios/original/` 的任何字节。

## 2. 检查过的文件

| 类别 | 路径 |
|---|---|
| 规则 | `AGENTS.md`、`docs/HANDOFF.md`、`.gitignore`、`third_party/README.md` |
| FCFS | `baselines/fcfs_sumo/{control,booking,conflicts,queue,tracker,shadow,test_logic,runner,analyze_shadow}.py` |
| 实验脚本 | `experiments/run_fcfs_sweep.py`、`experiments/seeds_30.txt` |
| 场景 | `scenarios/original/{cross.sumocfg,routes.rou.xml,types.typ.xml,cross{1..4}.net.xml,tls{2,3,4}.net.xml}`、`scenarios/smoke/cross3_smoke.sumocfg`、`scenarios/flows/lanes*_density*.rou.xml` |
| 结果（只读） | `results/fcfs_sweep/{summary.csv,sweep.log}`、`results/fcfs_control/`、`results/fcfs_shadow/`、`results/smoke/` |
| 决策 | `docs/decisions/fcfs-parameters.md`、`docs/env/environment-audit.md` |

## 3. 环境实测（**已验证**）

| 项 | 值 |
|---|---|
| OS / 内核 | Ubuntu 22.04.5 LTS（上游要求 20.04，可编译） |
| CPU / 内存 / 磁盘 | 16 线程 / 62 GiB（可用 55 GiB）/ 916 G（可用 683 G） |
| Python | 3.12.2（conda base）；`traci`/`sumolib` **1.24.0** |
| SUMO | **1.12.0**（`/usr/bin/sumo`，`SUMO_HOME=/usr/share/sumo`） |
| CMake / g++ / make | 3.22.1 / 11.4.0 / 4.3 |
| Boost | 系统头 1.74 + conda 1.82.0（CMake 实际选中 conda 1.82.0） |
| **CPLEX** | **未安装**（`/opt` 无 ibm；无 `cplex` 可执行；无 python `cplex`；无环境变量） |
| Git | 2.34.1；工作树仅有 1 个未跟踪文件 `scenarios/original/routes.txt`（作者要求不入库） |
| 网络 | 直连 GitHub 失败；本地代理 `127.0.0.1:7890` 可用（HTTP 200） |

## 4. 仓库状态（**已验证**）

```text
git rev-parse HEAD = 52a63429b2dc6a4d5a6bdb2fa8482987afd9acb3   (main == origin/main)
git status --porcelain = "?? scenarios/original/routes.txt"      (仅此一项未跟踪)
git diff --stat = 空                                             (无未提交改动)
```

⇒ 本轮开始前**没有需要保护的未提交改动**；`routes.txt` 保持未跟踪、未修改。

## 5. 最重要的新发现：旧 FCFS 扫描是**异常中断**，不是"跑完"

`results/fcfs_sweep/summary.csv` 只有 **227 / 450** 行（`ok` 216、`skipped` 11），
`sweep.log` 末尾出现：

```
Error: Answered with error to command 0xc4: Failed to resume from stopping for vehicle 'flow_se.18',
       reached: 0, duration:9223372036854775807, edge:south2center, startPos: 84.3     (连续 7+ 步)
Error: tcpip::Socket::recvAndCheck @ recv: Connection reset by peer
malloc_consolidate(): unaligned fastbin chunk detected                                  (8 次)
```

进度日志停在 `[220/450]`，此后无任何输出 ⇒ **SUMO 进程堆损坏并崩溃**，
`HANDOFF.md` §11.7.2 的"扫描中/可续跑"描述应视为"已中断"。
因果链假设（**待 Stage 3 验证**）：`control.py:324-328` 把 `setStop` 失败的车
也放进 `stopped`，随后对**没有活动 stop** 的车调用 `resume()` → 逐步报错洪泛 → 连接重置 → 崩溃。
该缺陷已记为 `fcfs-correctness-audit.md` 的 **D-03（最高优先级）**。

## 6. Stage 1 结果：两个上游

| 项 | PSB | PSL |
|---|---|---|
| URL | `JingtianYan/PSB-RAL` | `theanhhoang/AIM` |
| 分支 | `main` | **`AAAI22_PBS-SIPP`** |
| commit | `0b3f6eb34bf69a6d6d6a0fc2db5505073c90af24` | `5686e15092fd95a46309a118655a5ab0c23c60fa` |
| 大小 | 29 MB | 494 MB（含 `venv/`、预编译二进制、MP4/PDF） |
| LICENSE | **无** ⇒ 不可再分发 | **无** ⇒ 不可再分发 |
| CMake 配置 | ✅ 成功 | ✅ 成功 |
| `make` | ❌ `ilcplex/ilocplex.h` 缺失 | ❌ 同一错误（`SIPP.cpp:9`） |
| 预编译二进制 | 无 | **有**：`PBS-SIPP-ver2/AIMPBS`（静态链接，无 cplex 动态依赖） |
| 运行过样例 | **否** | **否** |

详见 `third_party/UPSTREAMS.md`、`psb-reproduction.md`、`psl-reproduction.md`。

## 7. 本轮改动清单（仅文档，无代码改动）

| 类型 | 文件 |
|---|---|
| 新增 | `third_party/UPSTREAMS.md` |
| 新增 | `docs/baselines/baseline-strategy.md` |
| 新增 | `docs/baselines/fcfs-correctness-audit.md` |
| 新增 | `docs/baselines/psb-reproduction.md` |
| 新增 | `docs/baselines/psl-reproduction.md` |
| 新增 | `docs/baselines/sumo-adaptation-design.md` |
| 新增 | `docs/baselines/fairness-protocol.md` |
| 新增 | `docs/baselines/stage0-stage1-report.md`（本文件） |
| 修改 | `AGENTS.md`（§2 baseline 结构 + 上游授权）、`docs/HANDOFF.md`（本轮检查点） |
| 新增 | `README.md`（仓库根，简介 + baseline 方向） |
| 未入库 | `third_party/_local/{PSB-RAL,AIM-PSL}`、`third_party/_local/_build/`（`.gitignore` 已覆盖） |

**未改动**：`scenarios/**`、`paper/**`、`baselines/fcfs_sumo/**`、`experiments/**`、`results/**`。

## 8. 验证命令（可复跑）

```bash
git rev-parse HEAD && git status --porcelain
sumo --version | head -1
python3 -c "import traci,sumolib;print(traci.__file__)"
ls /opt ; command -v cplex ; python3 -c "import cplex"
git -C third_party/_local/PSB-RAL rev-parse HEAD
git -C third_party/_local/AIM-PSL  rev-parse HEAD && git -C third_party/_local/AIM-PSL branch --show-current
cmake -S third_party/_local/PSB-RAL/Intersection/PSB-Intersection -B third_party/_local/_build/psb-intersection
make -C third_party/_local/_build/psb-intersection -j4      # 预期：ilcplex/ilocplex.h 缺失
cmake -S third_party/_local/AIM-PSL/PBS-SIPP-ver2 -B third_party/_local/_build/psl-pbs
make -C third_party/_local/_build/psl-pbs -j4              # 预期：同上
```

## 9. 阻塞与不确定性

1. **CPLEX 缺失** ⇒ PSB 完全无法编译/运行；PSL 无法重编译（预编译二进制待验证）。
   需作者选择方案 A/B/C（`third_party/UPSTREAMS.md` §3）。
2. **上游无许可证** ⇒ 不得把上游源码提交/再发布；论文只能引用论文与 URL。
3. **FCFS 旧扫描已崩溃且不完整**（227/450）⇒ 任何基于它的数字都不能进论文。
4. **FCFS 实现存在 12 项缺陷**（其中 3 项严重），详见审计文档。
5. 旧 `HANDOFF.md` 把该扫描描述为"进行中"，与本轮实测不一致，已在本轮更新中纠正。

## 10. 下一步（最小动作，需作者确认）

**Stage 2**（二选一或同时）：

- **PSL**：在 `PBS-SIPP-ver2/` 目录内运行**一次** `./AIMPBS 4`，判定预编译二进制可用性；
  记录 `output.txt`、退出码、CPLEX 许可报错（若有）。
- **PSB**：**被 CPLEX 阻塞**，只能等作者决定方案 A/B/C。

同时建议（可与 Stage 2 并行，不违反闸门）：**Stage 3 的 D-03 修复 + 纯逻辑单测**，
因为它能让 FCFS 的崩溃消失，且不需要 CPLEX。
