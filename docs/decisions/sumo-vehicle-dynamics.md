# SUMO 中"common 车辆"的动力学约束（口径登记）

- 建立日期：**2026-11-14**
- 状态：**§1 已核实（工作区内文件）／§2 作者调研项（NOT VERIFIED）／§3 使用规则**
- 唯一来源：`scenarios/original/types.typ.xml`（工作区内）
- 说明：本文件只做**登记**。凡工作区内无据的项，一律标 `作者调研项`，
  由作者（2026-11-14 指示）负责调研后回填；**agent 不得猜测、不得引用外部材料补齐**。

---

## 1. 【已验证】工作区 `types.typ.xml` 固定了什么

```xml
<vTypeDistribution id="vehDist">
  <vType id="car" vClass="passenger" accel="1.0" decel="4.5" sigma="0.5"
         length="5.0" maxSpeed="13.9" guiShape="passenger"
         carFollowingModel="IDM" tau="2.0" minGap="3.0"/>
</vTypeDistribution>
```

| 参数 | 值 | 在本文/本仓库中的作用 |
|---|---|---|
| `vClass` | `passenger` | 决定 SUMO 的默认让行/限速继承 |
| `accel` | **1.0 m/s²** | 期望最大加速度；也是 `kinematics.ACCEL` 的取值 |
| `decel` | **4.5 m/s²** | 期望最大减速度；本仓库把 `|a| > 4.5` 计为"急减速事件"（对应稿件 §III-B） |
| `sigma` | 0.5 | 驾驶员不完美度（IDM 的随机扰动） |
| `length` | **5.0 m** | 车辆长度；`Instance.cpp` 的 `ag.length` 也是 5 |
| `minGap` | **3.0 m** | 静止最小车距；`--collision.mingap-factor 0.5` ⇒ **1.5 m** 近距阈值（稿件口径） |
| `maxSpeed` | **13.9 m/s**（50 km/h） | 与稿件 L135 一致 |
| `tau` | **2.0 s** | 期望车头时距；也是 FCFS 的 `DT_SAFE` 来源 |
| `carFollowingModel` | **IDM** | 跟驰模型 |
| `id` | `car` | 所有 flow 的 `type` 都是 `car` |

**由此可得、可直接引用的推论**：

- 车辆**长度 5 m、静止间距 3 m** ⇒ 一条车道清空停止线的最小占用 8 m
  （`plan_scenario.LANE_CLEAR = 8.0` 即来源于此）。
- "急减速事件"的阈值 = `decel` = **4.5 m/s²**（`execute_plan.py` 用的就是它）。
- "近距事件"的 1.5 m 阈值是 `minGap × 0.5`，**不是** SUMO 的默认碰撞判据。

---

## 2. 【NOT VERIFIED】需要作者调研的项

以下各项**在工作区内没有任何依据**。它们直接影响 R2-3（运动学可行性）的判据，
以及"急减速/碰撞"的统计口径，因此**必须由作者确认**后才能写进论文。

| # | 项 | 为什么需要 | 需要确认什么 |
|---|---|---|---|
| D1 | **`emergencyDecel`** | SUMO 的碰撞/紧急制动判定用的不是 `decel` 而是 `emergencyDecel`（vType 未显式给出时取 SUMO 默认值）。本仓库目前把 `|a|>4.5` 当急减速，可能与 SUMO 内部判据不一致 | 本机 SUMO **1.12.0** 下 `emergencyDecel` 的默认值；是否需要在 `types.typ.xml` 显式写出（**写=改场景，须作者授权**） |
| D2 | **车辆宽度** | 碰撞/近距的几何判定、以及"平面圆盘"模型的半径换算需要车宽；`vType` 里**没有** width | 采用的宽度（例如 1.8 m）及其来源 |
| D3 | **jerk / 舒适性阈值** | §3.2 只报分布；若要与"舒适性"对照，需要一个权威阈值 | 采用哪个阈值（文献/标准）、单位 |
| D4 | **`speedFactor` 分布** | 未指定 ⇒ SUMO 默认 1.0（无随机）；这会影响"自由流最优时间"与 TimeLoss 口径 | 历史实验是否用了默认 1.0 |
| D5 | **换道模型参数**（`lcStrategic` 等） | 未指定 ⇒ SUMO 默认；影响多车道利用率与进口排队形态 | 是否接受默认值 |
| D6 | **IDM 其余参数**（`delta`、`stepping`） | 未指定 ⇒ 默认 | 是否接受默认值 |
| D7 | **`sigma=0.5` 是否有意为之** | 0.5 的驾驶员不完美度在确定性对照实验里会引入额外随机性 | 历史实验是否就是这个值 |
| D8 | **`vTypeDistribution` 只有单一 `car`** | 文件用 `vTypeDistribution` 包了一个 `vType`，语义上等于固定车队构成 | 是否为有意简化 |

> **纪律**：在 D1–D8 回填之前，任何"加速度/jerk 是否可行"的结论都**不得**写出；
> 只能报分布，并在表注里说明判据待定。

---

## 3. 使用规则（对所有方法一致）

1. **所有方法共用同一份 `types.typ.xml`**。为某个方法改 vType（长度/加速度/限速）= 破坏公平，
   除非作者明确授权，且必须在 `run_manifest.json` 写 `kinematics_deviation`，并在论文中披露。
2. 该方法特有的运动学假设（例如 PSL 二进制硬编码的 `v ∈ [3,15]`、
   `Li/w + Li/v` 的 `w = 7`）**不得**改写 SUMO 的 vType 去迁就，只能作为**偏离**记录。
3. 新增任何 SUMO 版本相关的默认值依赖时，必须记录 `sumo_version`（当前 **1.12.0**）。

---

## 4. 已记录在案的具体偏离（工作区内可查）

| 偏离 | 位置 | 说明 |
|---|---|---|
| PSL 硬编码 `v_min=3 / v_max=15 / length=5` | `third_party/_local/AIM-PSL/PBS-SIPP-ver2/Instance.cpp:86-88` | 与 `maxSpeed=13.9` 不一致；适配层用 `--w 13.9` 在**执行侧**标定占用，二进制未改 |
| 适配层 `w = 13.9`（上游默认 7） | `docs/baselines/psl-experiment-adaptation.md` §8 | 只作用于适配层的强制执行模型，上游二进制仍用 7 |
| 稿件"最小车距 1.5 m + 其余动力学为 SUMO 默认" | `main.tex` L135 | 与 `types.typ.xml`（`minGap=3.0`、IDM 非默认参数全给出）**不一致**；属历史陈述，**不得据新推测改写**，需作者裁定（见 `docs/audits/latex-audit.md` §4） |
