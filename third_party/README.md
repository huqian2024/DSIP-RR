# third_party — 上游项目固定记录

本目录用于存放**固定 commit 的上游参考实现**。当前为空（仅 `.gitkeep`），原因见 §3。
按 `.gitignore` 规则，`third_party/*/` 下的源码目录默认不纳入本仓库（避免嵌套 `.git` 与体积膨胀）；如确实需要入库，改为 git submodule 并在此登记。

---

## 1. 已调查的上游项目

### 1.1 MMD（DSIP 的方法学上游）

| 项目 | 值 |
|---|---|
| URL | https://github.com/yoraish/mmd |
| 本机副本 | `~/Downloads/mmd`（另有 `~/Downloads/sumo_rl_demo/mmd/` 一份完整拷贝） |
| HEAD commit | `5c2597eb3e2def9f0a87d7972811d340343c0738`（2025-02-12） |
| 本地改动 | `scripts/inference/inference_multi_agent.py`（+15/−12，去年实验期间形成，未回滚） |
| 许可 | 见上游 `LICENSE`（未在本轮复核） |

### 1.2 AIM4 / FCFS 参考实现

| 项目 | 值 |
|---|---|
| URL | https://github.com/spartalab/aim |
| 默认分支 | `master` |
| 固定 commit | `2c7a61d9b10049307570aba15f842221e97cc529`（2019-08-30） |
| 许可 | GitHub 元数据 **GPL-3.0**；但 `aim4/*.java` 文件头为 UT Austin 的 BSD 三条款式声明，仓库另含 `COPYRIGHT.txt`。**口径不一致，复用前须确认** |
| 关键文件 | `src/main/java/aim4/im/v2i/RequestHandler/FCFSRequestHandler.java`（FCFS 协议本体）、`aim4/im/v2i/policy/BasePolicy.java`、`aim4/im/v2i/reservation/*` |
| 用途 | **只作协议参考**，不复制源码（GPL 传染风险）；FCFS 在我们的仓库中独立实现于 `baselines/fcfs_sumo/` |

### 1.3 CCAM-DI

| 项目 | 值 |
|---|---|
| URL | https://github.com/KULeuven-COSIC/CCAM-DI |
| 默认分支 | `main` |
| 固定 commit | `c781a644f1df9315a804699296bf3950217886e9`（2026-04-29） |
| 许可 | **MIT** |
| 依赖 | Python 3.10.12、`ray[rllib]==2.9.3`、`gymnasium==0.28.1`、`torch==2.0.1`、`pandas==2.0.0`、`numpy==1.23.5` |
| 注意 | 仓库**未发布** `saved_model/` 权重；`env/8_8_network.net.xml` 为 8×8 网格路网，需适配 |

---

## 2. 复现时如何取得源码（待网络恢复）

```bash
cd third_party
git clone https://github.com/spartalab/aim.git aim
git -C aim checkout 2c7a61d9b10049307570aba15f842221e97cc529

git clone https://github.com/KULeuven-COSIC/CCAM-DI.git CCAM-DI
git -C CCAM-DI checkout c781a644f1df9315a804699296bf3950217886e9
```

克隆后请在 `docs/decisions/` 记录：实际 commit、许可证、是否入库（submodule / 忽略）。

---

## 3. 为什么当前没有本地克隆

2026-10-30 审计中，直连 GitHub 的 `git clone --depth 1` 两次超时：

```
fatal: unable to access 'https://github.com/...': Failed to connect to github.com
port 443 after 133740 ms: Connection timed out
```

本轮改由 GitHub REST API / raw 文件只读阅读，已取得 HEAD SHA 与许可信息（见上）。
故 `third_party/` 保持空目录，未放入任何第三方源码，也未提交任何模型权重或大体积资产。
