# S4b：可行性—吞吐权衡与跨 epoch 协调（2026-11-15）

两个**适配器层**实验，规划器（prior / MPD / CBS）一行未改。
工况一律为 cross3 · density3 · **1:2:1** · seed 81890 · 200 s · `epoch=2 s` · `max_agents=4`
（除非表中另注）。基线是"无控制"臂：近距 13、完成行程 498、timeLoss 9.30 s。

---

## 1. 实验 A：时间伸缩 λ（执行层速度可行化）

`--time-scale λ` 把每条计划按 `arc(t/λ)` 重放：指令加速度按 `1/λ²` 下降，**所有车辆的相对顺序不变**
（统一 λ，非单车自适应）。校验器用 `dynamics_aware.py --time-scale λ` 保持同口径。

| λ | \|a\| p50 / p95 / max (m/s²) | 在车限内？(accel 2.6) | \|jerk\| p50 (m/s³) | 完成行程 | TL/veh (s) | 近距 | 紧急制动 |
|---|---|---|---|---|---|---|---|
| 1（名义） | 9.59 / 14.08 / 17.97 | ❌ 3.7× | 147.6 | **478** | **18.67** | **449** | 3 212 |
| 2 | 2.46 / 3.69 / 4.89 | p50 内，max 超 | 18.0 | 456 | 21.28 | 640 | 7 608 |
| 3 | **1.17 / 1.62 / 2.48** | ✅ 全部在限内 | 5.6 | 454 | 25.13 | 886 | 11 823 |

**结论**：λ=3 可让全部指令加速度落回车限，但代价是
完成行程 −5 %、timeLoss +35 %、近距事件 **翻倍**。
**紧凑（协调好）与可行（能被车执行）在这套实现里互相排斥**——
要两者兼得必须在**规划时**就带动力学约束，执行层补不了。

## 2. 实验 B：跨 epoch 协调（`--replan-active`）

**缺陷**（适配器，不是上游）：默认模式下，已经进入规划框、正在执行计划的车辆
**不会进入后续 epoch 的 CBS agent 集**。于是一辆新车规划时，完全不知道框内还有谁——
所有"跨 epoch"的交互都是未协调的。

`--replan-active` 让每一批同时包含"框内在执行的车辆 + 新到达车辆"，即真正的滚动重规划。

| 指标 | 默认（跨 epoch 不协调） | `--replan-active` | 变化 |
|---|---|---|---|
| 近距事件 <1.5 m | 449 | **125** | **−72 %** |
| 紧急制动 | 3 212 | **1 110** | **−65 %** |
| 矩形重叠车辆对 | 87 / 27 966（0.31 %） | **6 / 25 878（0.023 %）** | **−93 %** |
| 完成行程 | 478 | 453 | −5 % |
| 逐车 timeLoss (s) | 18.67 | 18.72 | ≈0 |
| \|a\| p50 / max (m/s²) | 9.59 / 17.97 | **3.96 / 14.62** | −59 %（p50） |
| 规划 p50 (s) | 1.81 | 1.77 | ≈0 |

**结论**：
1. **近距事件的主要来源是适配器的跨 epoch 缺口，不是规划器。** 一旦把框内车辆纳入协调，
   近距从 449 掉到 125、矩形重叠从 87 对掉到 6 对。
2. 完成行程只掉 5 %、timeLoss 基本不变，说明这不只是"变慢换安全"。
3. 指令加速度仍偏高（p50 3.96 > 2.6），**把 λ=1.3 叠加到这一变体上应能压到限内**——未做。

## 3. 对论文口径的影响

- 上一轮"近距 13→449"的结论**必须修正**：那是 `--replan-active` 关闭时的数，
  属于适配器缺陷，不是 DSIP 的性质。**正确数字是 125（仍需说明是重建值）。**
- 但仍**不能**说 "DSIP 把冲突降下来"：125 vs 13 仍是无控制臂的约 10 倍，
  且指令加速度仍超车限。原因（圆盘 vs 5 m 车）没有被消除。
- 因此论文里可用的表述仍然只有**同一臂内的相对响应**（`s1-s3-runlog.md` §4.1）。

## 4. 复现

```bash
# 实验 A（λ 扫描）
for L in 1 2 3; do
  /home/qian/anaconda3/envs/mmd/bin/python src/dsip_reconstruction/s3_run.py \
    --rou scenarios/flows/lanes3_density3.rou.xml --end 200 --epoch 2 \
    --max-agents 4 --seed 81890 --no-compile --time-scale $L \
    --out results/dsip_lambda_$L
  /home/qian/anaconda3/envs/mmd/bin/python src/dsip_reconstruction/dynamics_aware.py \
    --run results/dsip_lambda_$L --out results/dsip_s4 --time-scale $L
done

# 实验 B（跨 epoch 协调）
/home/qian/anaconda3/envs/mmd/bin/python src/dsip_reconstruction/s3_run.py \
  --rou scenarios/flows/lanes3_density3.rou.xml --end 200 --epoch 2 \
  --max-agents 4 --seed 81890 --no-compile --replan-active \
  --out results/dsip_replan_active
```
