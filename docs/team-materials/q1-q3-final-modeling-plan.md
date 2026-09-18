# Q1–Q3 终极建模方案 FINAL

> **版本日期：2026-09-12**  
> **定位：** 数据预处理—建模—求解—验证—灵敏度的最终技术方案，不是论文叙述稿。  
> **最终冻结口径：** Q1 保留题面明确的单日 \(S_0=S_{144}=6000\)；Q2/Q3 不设置“年度末必须回到 6000 kWh”的硬约束。Q2 统一采用“逐日 LP + 日界残值 \(\lambda^*=0.4720\) 元/kWh”；Q3 采用信息条件 PWL continuation，并以同一 \(\lambda^*\) 作为远端软价值锚。  
> **结果纪律：** 既有已验证数值可引用；新增计算、敏感性和 Q3 全年结果在实际运行前均标记“待计算”，不得预写结论。

---

## 0. 最终总纲

### 0.1 三问统一递进

三问不是三个互不相关的模型，而是同一微电网储能决策问题在不同信息条件下的逐层升级：

\[
\boxed{
Q1:\ \text{确定性精确调度}
\rightarrow
Q2:\ \text{因果预测下的逐日日前决策}
\rightarrow
Q3:\ \text{滚动预报下的多阶段自适应决策}
}
\]

对应统一状态价值主线：

\[
\boxed{
V_0(s)
\rightarrow
\widetilde V(s)=\beta-\lambda^*s
\rightarrow
\widehat V_{d,r}(s\mid\mathcal I_{d,r})
}
\]

其中

\[
\lambda^*=0.4720\ \text{元/kWh}.
\]

含义：

- **Q1：** 用确定性 LP、对偶、有限差分和 DP verifier 识别储能库存的局部边际价值；
- **Q2：** 用常边际仿射残值压缩跨日未来价值，避免逐日 LP 只顾当天；
- **Q3：** 用随 0/6/12/18 信息更新的凸 PWL continuation 恢复“状态相关 + 信息相关”的未来价值，并在更远端用 \(-\lambda^*s\) 软锚定。

### 0.2 最终终端裁决

1. **Q1**：题面明确单日循环，因此
   \[
   S_0=S_{144}=6000.
   \]

2. **Q2**：不设置年度末硬循环。每天求解
   \[
   \min \sum_t p_tG_{d,t}^{plan}-\lambda^*S_{d,144}^{plan},
   \]
   日末真实状态链式传递到下一天。

3. **Q3**：同样不设置年度末硬循环。日内/跨日未来价值由
   \[
   \widehat V_{d,r}(s\mid\mathcal I_{d,r})
   \]
   承接；其有限 continuation horizon 的最远端采用
   \[
   V_{\text{anchor}}(s)=\beta-\lambda^*s
   \]
   作为软价值锚。

4. 年末 \(6000\) 仅可作为**软目标敏感性**：
   \[
   J_\rho=J+\rho |S_T-6000|,
   \]
   不能作为主模型硬可行约束。

### 0.3 终端库存的公平比较

由于 Q2/Q3 不强制相同期末 SOC，正式跨策略比较同时报告：

- **现金费用**
  \[
  J^{cash};
  \]

- **统一库存价值修正费用**
  \[
  J^{cmp}
  =
  J^{cash}+\lambda^*(S_{start}-S_{end}).
  \]

所有策略正式比较使用同一 \(S_{start}=6000\) 与同一 \(\lambda^*=0.4720\)。  
\(J^{cash}\) 回答“实际支付多少钱”；\(J^{cmp}\) 控制不同期末库存带来的边界偏差。

### 0.4 最终证据等级

- **题面事实：** 储能参数、10 min 数据、Q1 单日首末状态相等、Q2/Q3 计划与调整规则、应急购电价格等；
- **统一建模假设：** 路线 A 令当日负荷在 0:00 已知，用于隔离光伏信息价值；
- **既有已验证结果：** 仅引用原 Q1/Q2 已实际复核数值；
- **本终极版方法增强：** 严格 filtration、条件场景更新、源—汇分解、迭代 MILP exactification、Bellman continuation、自适应 PWL；
- **待运行结果：** Q3 全年结果、新增消融和新增敏感性。

---

# 1. 统一建模合同

## 1.1 时间、索引与单位

日期索引 \(d\)，日内槽索引

\[
t=0,\ldots,143,\qquad \Delta t=\frac16\ \text{h}.
\]

槽 \(t\) 对应

\[
[t/6,(t+1)/6).
\]

附件输出统一采用**右端点标签、位置对齐**：

\[
B[2+t]=x[t].
\]

禁止循环回卷。

原始负荷与光伏为 kW，进入模型前统一转换：

\[
L_{d,t}=\frac{P^{load}_{d,t}}6,\qquad
P_{d,t}=\frac{P^{pv}_{d,t}}6,
\]

单位均为 kWh/slot。价格 \(p_t\) 为元/kWh。

## 1.2 储能物理

统一参数：

\[
S^{min}=1200,\qquad
S^{max}=10800\quad(\mathrm{kWh}),
\]

\[
\bar E=\frac{5000}{6}=833.333333\quad(\mathrm{kWh/slot}),
\]

\[
\eta_c=\eta_d=0.9.
\]

状态方程：

\[
S_{t+1}=S_t+0.9C_t-\frac{D_t}{0.9}.
\]

约束：

\[
0\le C_t,D_t\le\bar E,
\qquad
1200\le S_t\le10800.
\]

往返效率为 \(0.81\)。  
单边效率取 \(\sqrt{0.9}\) 仅作为敏感性，不替换主模型。

## 1.3 市场与物理规则

统一：

- 禁止向电网售电；
- 允许弃光；
- 普通购电的未使用部分不能跨槽转移；
- 应急电 \(H_t\) 按 \(5p_t\) 计费；
- 应急电只能供负荷，不能给储能充电；
- 实际充放电必须互斥；
- Q2/Q3 日末真实 SOC 连续传递，普通日不重置到 6000；
- Q2/Q3 年度末不设置硬 SOC 约束。

## 1.4 评价期

2025 年 1 月仅用于：

- warm-up；
- 预测器和残差池初始化；
- 超参数冻结；
- Q3 场景/PWL/runtime pilot；
- 数值单元测试。

正式评价期：

\[
2025\text{-}02\text{-}01
\sim
2025\text{-}12\text{-}31,
\]

共 334 天。

初态统一：

\[
S_{2025-02-01,0}=6000.
\]

## 1.5 统一符号分层

| 层 | 符号 | 含义 |
|---|---|---|
| 日前合同 | \(G^{plan}_{d,t}\) | 0:00 提交的普通购电量 |
| Q3 调整后合同 | \(A^F_{d,t}\) | 执行前最后一次生效普通购电量 |
| 普通电流向 | \(U^L,U^C,W^G\) | 供负荷、供充电、已付未用 |
| PV 流向 | \(P^L,P^C,R^{PV}\) | 供负荷、供充电、弃光 |
| 实际储能动作 | \(C^{exec},D^{exec},S^{exec}\) | 真实执行量 |
| 应急电 | \(H\) | 高价补负荷缺口 |
| Q3 参考动作 | \(x^{ref}\) | 槽首可测参考控制 |
| Q3 实际补偿 | \(x^{exec}\) | 当前槽真实 PV 实现后的物理 recourse |

计划层变量不得直接写成实际执行结果。

---

# 2. 统一数据预处理、防泄漏与冻结配置

## 2.1 附件 2 主表

建立唯一键：

```text
(date, slot)
```

检查：

1. 365 个连续日期；
2. 每日恰好 144 槽；
3. 无重复键；
4. 无 NaN / Inf；
5. 负荷非负；
6. 光伏原始异常值先记录后处理；
7. 电价映射唯一；
8. kW 与 kWh/slot 分列保存；
9. 输出后重新读取首槽、末槽、6:00、12:00、18:00。

任一日期缺槽、键冲突、单位不明均为 `fatal`。

## 2.2 夜间与近零光伏

相对误差仅在

\[
\widetilde P_{d,t}\ge\varepsilon_{pv}
\]

的有效白天槽使用。

夜间/近零槽：

- 不使用不稳定的相对误差；
- 保存原始值与异常标记；
- 预测层按预注册规则置零或采用绝对误差；
- 不允许因分母接近 0 产生异常风险裕度。

## 2.3 信息成熟性

每条训练样本至少保存：

```text
source_date
issue_time
target_time
mature_time
version
```

决策日 \(d\) 的历史数据必须满足：

\[
source\_date<d.
\]

Q3 forecast residual 还必须满足：

\[
target\_time\le decision\_time.
\]

正式期禁止：

- 读取未来实际光伏；
- 读取未来实际负荷；
- 用 2–12 月结果重新选择 q、窗口、场景数、带宽、PWL knot、MPC 频率；
- 为提高结果事后改变时间映射。

## 2.4 冷启动回退

Q2：

- 4 日均值不足：已有完整日均值 \(\rightarrow\) 1 月同槽均值；
- 28 日误差池不足：使用全部成熟历史；
- 记录 `fallback_level`。

Q3：

- 场景样本不足：使用全部成熟历史；
- 条件 ESS 太低：按 §5.4 的兼容回退链；
- 不允许未来日补样本。

## 2.5 超参数冻结表

正式运行前在 1 月冻结：

| 参数 | 主值 |
|---|---:|
| Q2 同槽均值窗口 | 4 日 |
| Q2 误差窗口 | 28 日 |
| Q2 PV error quantile | 0.20 |
| Q2 折减上限 | 0.35 |
| 日界残值 \(\lambda^*\) | 0.4720 元/kWh |
| Q3 历史池 | 60 日 |
| Q3 最大场景叶 | 8 |
| Q3 最小子节点样本 | 3 日 |
| Q3 初始 PWL knots | 5 |
| Q3 continuation horizon | 主设置 3–7 日中预注册一值 |
| Q3 MPC 频率 | 10 min |
| random seed | 固定 |
| solver primal/dual tolerance | 固定配置 |
| \(\varepsilon_{energy},\varepsilon_{soc},\varepsilon_E,\varepsilon_H,\varepsilon_V\) | 统一配置对象 |

带宽 \(h\)、ESS 阈值、距离标准化尺度等必须在 1 月 pilot 中定案并记录，不得在正式期回调。

## 2.6 可复现日志

每次运行保存：

- 输入文件 hash；
- 清洗规则版本；
- 时间映射版本；
- 训练日期上界；
- 超参数配置；
- random seed；
- 场景池 hash；
- solver 版本；
- 输出 hash；
- fallback 日志；
- MILP exactification 日志。

---

# 3. Q1：确定性调度与储能价值

## 3.1 数据预处理

Q1 单日数据：

1. 检查 144 槽完整；
2. 按位置映射时间；
3. kW \(\rightarrow\) kWh/slot；
4. 校验价格/负荷/PV；
5. 输出后位置回读。

## 3.2 主模型：词典序确定性 LP

变量：

\[
G_t,C_t,D_t,R_t,S_{t+1}.
\]

约束：

\[
G_t+P_t+D_t=L_t+C_t+R_t,
\]

\[
S_{t+1}=S_t+0.9C_t-\frac{D_t}{0.9},
\]

\[
0\le R_t\le P_t,
\]

\[
0\le C_t,D_t\le\bar E,
\]

\[
1200\le S_t\le10800,
\]

\[
S_0=S_{144}=6000.
\]

### 第一目标

\[
J_1^*=\min\sum_t p_tG_t.
\]

### 第二目标

锁定：

\[
\sum_t p_tG_t
\le
J_1^*+\varepsilon_J,
\]

其中

\[
\varepsilon_J=
\max\{10^{-6},10^{-9}\max(1,|J_1^*|)\}.
\]

再求

\[
\min\sum_t(C_t+D_t).
\]

作用：消除最优面上无意义的同时充放电和循环。

## 3.3 互斥 exactification

首先解 LP。

定义：

\[
\chi_{CD}
=
\max_t\min(C_t,D_t).
\]

若

\[
\chi_{CD}\le\varepsilon_E,
\]

记录 LP 互斥 exactness certificate。

否则采用**迭代 active-set MILP**：

\[
\mathcal V^{(k)}
=
\{t:\min(C_t,D_t)>\varepsilon_E\}.
\]

将新违规槽加入 binary 集：

\[
\mathcal B^{(k+1)}
=
\mathcal B^{(k)}\cup\mathcal V^{(k)},
\]

重新求解，直到

\[
\mathcal V^{(k)}=\varnothing.
\]

禁止只修一次后默认没有新违规槽。

## 3.4 状态价值层

定义：

\[
V_0(s)
=
\min
\left\{
\sum_tp_tG_t:
S_0=s,\ S_{144}=6000,\ x\in\mathcal F
\right\}.
\]

在 \(s=6000\) 邻域用三条证据：

1. LP 初始状态等式对偶；
2. 中心有限差分
   \[
   \widehat V'_0(s)
   =
   \frac{V_0(s+\Delta)-V_0(s-\Delta)}{2\Delta};
   \]
3. 粗 SOC 网格 DP / 枚举 verifier。

严格区分：

\[
-\frac{\partial J^*}{\partial S_0}
\]

与

\[
\frac{\partial J^*}{\partial S_T}.
\]

Q1 的局部边际价值仅用于 Q2 \(\lambda^*\) 的数量级一致性检验，不能直接声称两者相同。

## 3.5 \(\lambda^*=0.4720\) 的接口说明

Q2 使用的

\[
\lambda^*=0.4720
\]

是跨日库存的**统一局部残值参数**。

要求：

- 校准只使用 1 月或预先冻结的价值标定数据；
- 不使用 2–12 月正式费用倒推；
- Q1 对偶/有限差分仅作为 cross-scale sanity check；
- 在 Q3 中其价值函数斜率对照应写成
  \[
  \widehat V'(6000)\approx-\lambda^*.
  \]

## 3.6 求解与验证

主求解器：HiGHS LP。  
互斥必要时：HiGHS MILP。

独立 validator 重算：

- 能量平衡；
- SOC 递推；
- 初末状态；
- 变量域；
- 成本锁定；
- \(\chi_{CD}\)；
- 循环守恒；
- 输出位置映射。

只有 `optimal + errors=[]` 才能称该模型精确最优。

## 3.7 已验证结果

保留既有已验证数值：

- 正式购电费：35126.948624416575 元；
- 一级最优：35126.94858928963 元；
- 购电量：59482.698915258756 kWh；
- 无储能费用：48052.046590846665 元。

## 3.8 灵敏度（简）

只需：

- \(\eta=0.85/0.90/0.95\)；
- \(\sqrt{0.9}\) 效率语义；
- 容量 ±10%；
- 功率 ±10%；
- 初始 SOC；
- 负荷/PV/价格扰动。

---

# 4. Q2：因果保守预测 + 逐日 LP + 日界残值

## 4.1 信息集

每天 0:00：

已知：

\[
\mathcal I_{d,0}^{Q2}
=
\{
L_{d,0:143},
p_{0:143},
S_{d,0}^{exec},
\text{成熟历史}
\}.
\]

未知：

\[
P_{d,t}^{real},\quad t\ge0.
\]

当天普通购电 \(G^{plan}\) 一经形成，不再调整。

当槽 \(t\) 真实 PV 实现后，才允许执行层使用该值。

## 4.2 因果 PV 基础预测

最近 4 个完整成熟日同槽均值：

\[
\widetilde P_{d,t}
=
\frac{1}{|\mathcal D_d^{(4)}|}
\sum_{j\in\mathcal D_d^{(4)}}P_{j,t},
\qquad
j<d.
\]

历史日 \(j\) 的误差必须用当时可见信息重新构造：

\[
e_{j,t}
=
\frac{
P_{j,t}-\widetilde P_{j,t}
}{
\max(\widetilde P_{j,t},\varepsilon_{pv})
}.
\]

## 4.3 Q20 因果保守折减

过去 28 个成熟日同槽误差：

\[
m_{d,t}
=
\operatorname{clip}
\left[
-Q_{0.20}(e_{j,t}),
0,
0.35
\right].
\]

最终 PV 计划输入：

\[
\widehat P_{d,t}
=
(1-m_{d,t})\widetilde P_{d,t}.
\]

### 经济解释

若忽略跨时耦合做单槽局部近似：

- 过购边际损失约 \(p\)；
- 缺购后转应急，相对计划购电的增量损失约 \(4p\)。

故净负荷报童先验：

\[
q_N
=
\frac{4p}{4p+p}
=
0.80.
\]

随机性主要来自 PV 时：

\[
q_N=0.80
\Longleftrightarrow
q_{PV,error}=0.20.
\]

该关系只用于解释 Q20 的经济方向；储能跨时耦合下不声称其为动态系统闭式最优分位，最终由 \(q=0.10/0.20/0.30\) 因果敏感性检验。

## 4.4 日前计划 LP：最终统一口径

计划变量：

\[
G_t^{plan},
C_t^{plan},
D_t^{plan},
R_t^{plan},
S_t^{plan}.
\]

目标：

\[
\boxed{
\min
J_d^{plan}
=
\sum_{t=0}^{143}p_tG_t^{plan}
-\lambda^*S_{d,144}^{plan}
}
\]

\[
\lambda^*=0.4720.
\]

约束：

\[
G_t^{plan}+\widehat P_t+D_t^{plan}
=
L_t+C_t^{plan}+R_t^{plan},
\]

\[
0\le R_t^{plan}\le\widehat P_t,
\]

\[
S_{t+1}^{plan}
=
S_t^{plan}+0.9C_t^{plan}-\frac{D_t^{plan}}{0.9},
\]

以及统一 SOC/功率边界。

计划日初状态：

\[
S_{d,0}^{plan}
=
S_{d,0}^{exec}.
\]

跨日：

\[
S_{d+1,0}^{exec}
=
S_{d,144}^{exec}.
\]

**所有日期，包括 12 月 31 日，均不设置硬 \(S_{d,144}=6000\)。**

日界残值表示评价边界之后库存仍具有经济机会价值；其只进入规划决策，不重复进入现金费用。

## 4.5 计划层互斥

与 Q1 相同：

1. 先解 LP；
2. 计算
   \[
   \chi_{CD}^{plan}
   =
   \max_t\min(C_t^{plan},D_t^{plan});
   \]
3. 若超过容差，按 active-set 迭代加入 binary；
4. 直到无新违规槽。

## 4.6 实际透明执行器

定义计划购电相对真实净需求的差：

\[
g_t
=
L_t-P_t^{real}-G_t^{plan}.
\]

### 缺口 \(g_t>0\)

禁止充电：

\[
C_t^{exec}=0.
\]

优先放电：

\[
D_t^{exec}
=
\min
\left\{
g_t,\bar E,0.9(S_t-1200)
\right\}.
\]

应急：

\[
H_t
=
\max\{g_t-D_t^{exec},0\}.
\]

### 富余 \(g_t<0\)

禁止放电：

\[
D_t^{exec}=0.
\]

充电：

\[
C_t^{exec}
=
\min
\left\{
-g_t,
\bar E,
\frac{10800-S_t}{0.9}
\right\}.
\]

状态：

\[
S_{t+1}^{exec}
=
S_t^{exec}
+0.9C_t^{exec}
-\frac{D_t^{exec}}{0.9}.
\]

这一定义直接保证实际

\[
C_t^{exec}D_t^{exec}=0.
\]

## 4.7 唯一源—汇会计

为了唯一确定弃光和未用计划电，冻结会计优先级：

1. PV 优先供负荷；
2. 剩余负荷由普通电供给；
3. 若需要充电，剩余 PV 优先充电；
4. 仍需充电时再调用普通电；
5. 剩余普通电记 \(W^G\)；
6. 剩余 PV 记 \(R^{PV}\)。

变量满足：

\[
G_t^{plan}
=
U_t^L+U_t^C+W_t^G,
\]

\[
P_t^{real}
=
P_t^L+P_t^C+R_t^{PV},
\]

\[
U_t^L+P_t^L+D_t^{exec}+H_t=L_t,
\]

\[
C_t^{exec}=U_t^C+P_t^C.
\]

因此：

- \(H_t\) 无法流向充电端；
- \(W_t^G\) 不进入能量平衡；
- \(R_t^{PV}\) 才是弃光。

## 4.8 现金费用与价值修正费用

现金费用：

\[
J^{Q2,cash}
=
\sum_{d,t}p_tG_{d,t}^{plan}
+
\sum_{d,t}5p_tH_{d,t}.
\]

统一比较费用：

\[
J^{Q2,cmp}
=
J^{Q2,cash}
+
\lambda^*
\left(
S_{start}-S_{end}
\right).
\]

日界残值已参与计划，不再次加到现金费用中。

## 4.9 预测质量 → 决策质量验证

除 MAE/RMSE 外，必须报告：

### 预测层

- MAE；
- RMSE；
- PV 下侧覆盖率；
- 净负荷 0.8 服务覆盖率；
- 分时段 coverage。

### 决策层

报告：

\[
H_{d,t}
\]

与预测误差的关系：

- 误差 decile 对应平均应急量；
- 大误差时应急发生概率；
- \(q\) 改变对计划费/应急费的 trade-off。

目标不是追求最低 MAE，而是证明保守预测降低总决策成本。

## 4.10 求解流程

334 日 walk-forward：

1. 冻结日 \(d\) 信息截点；
2. 更新 4 日均值；
3. 更新 28 日误差池；
4. 构造 Q20 保守 PV；
5. 求 144 槽计划 LP；
6. 必要时迭代 MILP exactification；
7. 固定 \(G^{plan}\)；
8. 真实 PV 逐槽实现；
9. 执行透明控制；
10. 日末 SOC 传递；
11. 目标日完全成熟后才加入误差池；
12. 汇总现金费和价值修正费。

## 4.11 验证

### 数据 Gate

- 365×144；
- 单位；
- 时间映射；
- 位置回读。

### 信息 Gate

修改日 \(d\) 未来真实 PV：

\[
P_{d,\tau}^{real},\quad \tau\ge0
\]

不得改变当日 0:00 的

\[
G_{d,:}^{plan}.
\]

修改未来日期数据，不得改变更早日计划。

### 物理 Gate

- \(C^{exec}D^{exec}=0\)；
- SOC 连续；
- \(H\) 只供负荷；
- \(R^{PV}\le P^{real}\)；
- \(W^G\ge0\)。

### 会计 Gate

\[
J^{cash}
=
J^{plan}+J^{emergency}.
\]

### 终端 Gate

不检查“是否回 6000”；只检查：

\[
1200\le S_{end}\le10800
\]

并必须报告真实 \(S_{end}\) 与统一价值修正费用。

## 4.12 已验证主结果

沿用既有冻结结果：

- 总现金费用：13,252,341.09 元；
- 计划购电费：12,891,818.24 元；
- 应急购电费：360,522.85 元；
- 计划购电量：21,283,432.62 kWh；
- 应急购电量：55,801.05 kWh。

真实年末 SOC、计划文件版本归属、互斥数值证书必须从正式 result2 回读后填写，不能猜测。

## 4.13 灵敏度（简）

- \(q=0.10/0.20/0.30\)；
- cap = 0.25/0.35/0.45；
- 基础窗口 3/4/7 日；
- 误差窗口 14/28/56 日；
- \(\lambda=0/0.4126/0.4720/0.60\)；
- \(\eta\)；
- 容量/功率 ±10%；
- 年末软目标
  \[
  \rho|S_T-6000|
  \]
  仅作敏感性。

---

# 5. Q3：官方滚动预报 + 条件 SAA + 因果 MPC

## 5.1 相对 Q2 的增量

Q3 只增加：

1. 0/6/12/18 官方光伏预报；
2. 6/12/18 对尚未执行时段的普通购电调整权；
3. forecast error + revision 场景；
4. 多阶段 nonanticipative SAA；
5. 10 min 因果 MPC；
6. 信息条件 PWL continuation。

负荷信息条件、储能物理和评价期与 Q2 保持一致。

## 5.2 附件 3 数据预处理

解析为：

\[
(issue\_datetime,lead\_hour,target\_datetime)
\]

且

\[
target=issue+lead.
\]

理论节点数：

\[
365\times4\times24=35040.
\]

检查：

- 空白日期向下继承；
- 主键无重复；
- lead 完整；
- target 单调；
- 跨入 2026 的 target 不进入 2025 误差池；
- 原始负值先登记，不静默截断。

## 5.3 预报时序

第 \(k\) 小时：

\[
[\tau+k-1,\tau+k).
\]

0:00 发布版直接覆盖当天 0:00–24:00，并用于当天 0:00 计划。

前一日 18:00 版只用于：

- forecast revision 特征；
- 对照敏感性；
- 历史 revision path。

不替代当天 0:00–6:00。

6/12/18 新版只作用于尚未执行未来。

## 5.4 小时节点 → 10 min 电量

附件值按小时末采样点解释。

构造 \(F_0\)：

- 6/12/18：使用发布时刻前刚结束 10 min 的已实现 PV；
- 0:00：使用前一日 23:50–24:00 已实现 PV。

得到：

\[
F_0,\ldots,F_{24}.
\]

相邻节点线性插值，再对每个 10 min 区间积分：

\[
\widehat E_t^{PV}
=
\int_t^{t+1/6}\widehat P^{PV}(\tau)\,d\tau.
\]

敏感性比较：

- 因果锚点 + 线性积分；
- 首小时阶梯；
- 全时域阶梯。

## 5.5 Forecast leakage sanity gate

每个 forecast 节点必须满足：

\[
issue\_time\le decision\_time<target\_end.
\]

任何进入 residual pool 的实现值满足：

\[
realization\_time\le decision\_time.
\]

分别报告：

- daylight MAE；
- night MAE；
- 全时段 MAE；
- 0/6/12/18 分发布时刻误差。

若某发布时刻出现接近 0 的异常 MAE，必须单独复核：

- target 对齐；
- F0 锚点；
- 夜间零值占比；
- source/target 泄漏。

## 5.6 两层 filtration：槽首参考与槽内 recourse

定义槽首信息：

\[
\mathcal F_{t^-}
=
\sigma(
\text{当前 SOC},
\text{已实现 }PV_{<t},
\text{最新官方 forecast},
\text{已冻结合同}
).
\]

槽首参考动作必须满足：

\[
x_t^{ref}\in\mathcal F_{t^-}.
\]

当前槽真实 PV 实现后：

\[
\mathcal F_t
=
\mathcal F_{t^-}
\vee
\sigma(P_t^{real}),
\]

实际物理补偿满足：

\[
x_t^{exec}\in\mathcal F_t.
\]

因此：

- 槽首不能偷看当前槽真实 PV；
- 实际应急电可以响应当前槽已实现缺口；
- 当前槽 PV 改变不能修改已经形成的槽首参考动作。

## 5.7 Q3 信息集

发布时点 \(r\in\{0,6,12,18\}\)：

\[
\mathcal I_{d,r}
=
\{
L_{d,0:143},
p_{0:143},
S_{d,r}^{exec},
PV_{d,<r}^{real},
F^0,\ldots,F^r,
\mathcal H_{d,r}
\}.
\]

合同决策：

\[
G_d\in\sigma(\mathcal I_{d,0}),
\]

\[
A_d^r\in\sigma(\mathcal I_{d,r}).
\]

## 5.8 场景样本

随机对象只包含：

- 当前 forecast 对未来真实 PV 的误差；
- 下一次 forecast 相对当前 forecast 的 revision；
- 日内相关结构。

历史池：

\[
\mathcal H_{d,r}
=
\{j<d:\text{目标与所需 revision 均成熟}\}.
\]

主设置：

- 最近 60 个成熟日；
- 不足则全部成熟历史；
- 白天按 lead/太阳高度 robust scale；
- 夜间绝对误差；
- 保留整日路径相关性。

## 5.9 场景树

按信息揭示：

\[
0\rightarrow6\rightarrow12\rightarrow18.
\]

使用：

- k-medoids；
- 最多 8 个叶；
- 每个非退化子节点至少 3 个历史日；
- 样本频率为先验概率；
- 保留尾部极端路径。

缩减前后校验：

- mean；
- variance；
- P10/P90；
- 日内自相关；
- revision correlation；
- 尾部净缺口。

## 5.10 条件更新：只用外生信息

概率更新状态只包含外生量：

\[
z_r^{exo}
=
(
\Delta F_r,
E_r^{cum},
E_r^{recent},
\text{season/time features}
).
\]

**SOC 不进入概率特征。**

SOC：

\[
S_r
\]

仅作为优化状态进入价值函数与约束。

对当前已映射信息节点 \(n_r^*\)，只允许其兼容后继集合：

\[
\Omega_r^{comp}
=
\{\omega:\omega\text{ 与已观测信息历史兼容}\}.
\]

核权重：

\[
\tilde p_\omega
=
p_\omega
\exp
\left[
-\frac{d(z_r^{exo},z_\omega^{exo})^2}{2h^2}
\right],
\qquad
\omega\in\Omega_r^{comp}.
\]

归一化：

\[
p_\omega^{new}
=
\frac{\tilde p_\omega}
{\sum_{j\in\Omega_r^{comp}}\tilde p_j}.
\]

有效样本量：

\[
ESS
=
\frac1{\sum_\omega(p_\omega^{new})^2}.
\]

ESS 过低时：

1. 增大预注册带宽；
2. 合并当前兼容子节点；
3. 从原始成熟轨迹库重新进行更粗条件化；
4. 最后回退为相同季节/时段的无条件未来 residual 分布。

**禁止给与已实现历史明显冲突的旧分支重新赋概率。**

## 5.11 严格因果 LDR

槽首参考控制：

\[
x_t^{ref,\omega}
=
x_t^0
+
\sum_{\tau<t}
B_{t\tau}\xi_\tau^\omega,
\]

并强制：

\[
B_{t\tau}=0,\qquad \tau\ge t.
\]

\(\xi_\tau\) 只能由已实现 forecast error / revision 构造。

为控制维数，可在 0–6 / 6–12 / 12–18 / 18–24 四块共享系数，但不能允许未来 residual 进入当前特征。

未来扰动测试：

修改

\[
PV_\tau^{real},\quad \tau>t,
\]

必须保持：

\[
x_t^{ref,new}
=
x_t^{ref,old}.
\]

修改当前槽真实 PV 时：

- 槽首参考动作不变；
- 当前槽物理 recourse 可变化；
- 下一槽状态可变化。

## 5.12 四阶段 conditional SAA

合同阶段：

\[
G
\rightarrow
A^6
\rightarrow
A^{12}
\rightarrow
A^{18}.
\]

最终生效量：

\[
A_t^F.
\]

同一信息节点共享合同调整：

\[
A^{r,\omega}
=
A^{r,\omega'}
\]

若 \(\omega,\omega'\) 在 \(r\) 前拥有相同信息历史。

在发布时点 \(r\) 的条件子树上求：

\[
\min
\mathbb E_{\omega\mid\mathcal I_{d,r}}
\left[
\sum_{t\ge r}
\left(
p_tA_t^{F,\omega}
+0.5p_tZ_t^\omega
+5p_tH_t^\omega
\right)
+
\widehat V_{d,r}
(S_{d,144}^\omega\mid\mathcal I_{d,r})
\right],
\]

其中

\[
Z_t\ge G_t-A_t^F,
\qquad
Z_t\ge A_t^F-G_t.
\]

## 5.13 Q3 结算

主读法 B：

\[
C_B(G,A)
=
pA+0.5p|G-A|.
\]

验证锚点：

\[
G=100,A=80\Rightarrow90p,
\]

\[
G=100,A=120\Rightarrow130p.
\]

每槽只用：

- 原计划 \(G_t\)；
- 最终生效量 \(A_t^F\)

结算一次。

中间调整版本不重复收费。

现金费用：

\[
J^{Q3,cash}
=
\sum_{d,t}C_B(G_{d,t},A_{d,t}^F)
+
\sum_{d,t}5p_tH_{d,t}.
\]

统一比较费用：

\[
J^{Q3,cmp}
=
J^{Q3,cash}
+
\lambda^*(S_{start}-S_{end}).
\]

读法 A 仅作完整重优化敏感性，禁止只对读法 B 轨迹换公式计价。

## 5.14 SAA 源—汇结构

每场景：

\[
A_t^F
=
U_t^L+U_t^C+W_t^G,
\]

\[
P_t^\omega
=
P_t^L+P_t^C+R_t^{PV},
\]

\[
U_t^L+P_t^L+D_t+H_t=L_t,
\]

\[
C_t=U_t^C+P_t^C.
\]

因此应急电没有流向充电的弧。

## 5.15 SAA 互斥 exactification

先求连续 LP。

定义：

\[
\mathcal V^{(k)}
=
\{
(\omega,t):
\min(C_t^\omega,D_t^\omega)>\varepsilon_E
\}.
\]

若非空，将其及必要的信息等价 closure 加入 binary 集：

\[
\mathcal B^{(k+1)}
=
\operatorname{closure}
(
\mathcal B^{(k)}\cup\mathcal V^{(k)}
).
\]

重新求解，直至：

\[
\mathcal V^{(k)}=\varnothing.
\]

closure 至少覆盖因 nonanticipativity / LDR 共享而与违规单元耦合的等价变量。  
禁止“一次局部加 binary 后不重新全局扫描”。

## 5.16 Planning surrogate 与真实 MPC 分离

外层 SAA 采用因果 LDR 作为可计算的 recourse surrogate：

\[
(G,A)
=
\arg\min
\widehat J^{SAA}(\pi^{LDR}).
\]

真实执行采用：

\[
\pi^{MPC}.
\]

因此必须明确：

\[
\pi^{LDR}\neq\pi^{MPC}
\]

是允许的，但二者职责不同：

- LDR：用于外层合同优化；
- MPC：用于真实实时执行。

报告：

\[
\Delta_{policy}
=
J_{real}^{MPC}
-
\widehat J_{SAA}^{LDR},
\]

并检查：

- 合同可行性；
- realized emergency；
- expected vs realized cost 偏差；
- SOC 演化差异。

## 5.17 10 min MPC

槽首根据：

- 当前 \(S_t^{exec}\)；
- \(PV_{<t}^{real}\)；
- 最新 forecast；
- 当前生效合同 \(A_t^F\)；
- continuation value；

解短 horizon LP，仅执行第一槽参考动作。

规划窗口至少到：

- 下一发布时点；
- 或日末，

并携带跨日 continuation。

## 5.18 当前槽物理投影

当前真实 PV 实现后，固定 \(A_t^F\)，求两个微型 LP。

### 模式 C：充电

\[
D_t=H_t=0.
\]

### 模式 D：供电

\[
C_t=0.
\]

两个模式均满足真实：

- 负荷平衡；
- SOC；
- 功率；
- source-flow；
- \(W^G,R^{PV}\) 非负。

采用词典序目标：

1. 最小应急费用；
2. 最小偏离槽首参考动作；
3. 按固定 source priority 最小化会计退化。

选更优可行模式。

因此实际层精确保证：

\[
C_t^{exec}D_t^{exec}=0
\]

且

\[
H_t\not\rightarrow C_t.
\]

## 5.19 Bellman 嵌套 continuation

官方 forecast 只覆盖未来 24 h。  
不能将“官方段价值”和“历史尾部价值”简单相加。

设最新官方可见 horizon 结束于 \(T_1\)，则：

\[
\boxed{
V_{d,r}(s)
=
\min_{x_{r:T_1}}
\left[
C_{r:T_1}(x)
+
V^{hist}_{T_1}(S_{T_1})
\right]
}
\]

其中：

- \(C_{r:T_1}\)：当前官方 forecast / scenario 覆盖区内优化成本；
- \(V^{hist}_{T_1}\)：超过官方 horizon 后，只用决策日前历史构造的未来 cost-to-go。

历史尾部可使用：

- 同星期统计；
- 同季节统计；
- 最近成熟光伏 residual path；
- bootstrap 场景；

但必须满足：

\[
source\_date<d.
\]

未来自然日负荷同样只能用历史代理，不能读取实际未来负荷。

## 5.20 远端软价值锚

历史尾部有限 horizon 的最远端采用：

\[
V_{anchor}(s)
=
\beta-\lambda^*s,
\]

\[
\lambda^*=0.4720.
\]

因此：

- Q2：直接使用 affine residual；
- Q3：短中期使用信息条件 PWL，远端回归同一 affine salvage。

不设置年度末硬 \(S=6000\)。

## 5.21 自适应 PWL continuation

在当前可达 SOC 区间设置初始 knots：

\[
s_1,\ldots,s_K
\]

主设置 \(K=5\)。

对每个 \(s_j\) 解 continuation LP：

\[
v_j=V(s_j).
\]

取初始 SOC 等式的对偶次梯度：

\[
\mu_j.
\]

支持下界：

\[
V^L(s)
=
\max_j
\left\{
v_j+\mu_j(s-s_j)
\right\}.
\]

由于 continuation cost 随库存增加通常下降：

\[
\mu_j<0,
\]

在 \(s\approx6000\) 附近应检查：

\[
\mu_j\approx-\lambda^*.
\]

相邻 knot 弦线给出凸上界 \(V^U(s)\)。

在最大 gap 处：

\[
s^*
=
\arg\max_s
[V^U(s)-V^L(s)]
\]

自适应加点，直到：

\[
\max_s[V^U(s)-V^L(s)]
\le\varepsilon_V
\]

或达到预注册 knot 上限。

报告：

- knot 集；
- 最大 gap；
- continuation LP 次数；
- slope convexity；
- \(-\lambda^*\) 局部一致性。

## 5.22 Q3 求解流程

每天 0:00：

1. 冻结当前信息；
2. 读取当天 0:00 forecast；
3. 更新成熟 residual/revision 池；
4. 生成场景树；
5. 构造 continuation PWL；
6. 求阶段 0 conditional SAA；
7. 冻结 \(G\)。

逐槽：

8. 槽首 MPC；
9. 当前真实 PV 实现；
10. 两模式 micro-LP；
11. 更新真实 SOC。

6/12/18：

12. 读取新 forecast；
13. 更新兼容场景概率；
14. 更新 continuation；
15. 只调整未来 \(A\)；
16. 已执行动作和过去合同不回溯。

日末：

17. 传递实际 SOC 到次日。

## 5.23 分级求解

所有结构与计算预算决策在 **1 月** 完成。

### Level 1：解析/微型测试

验证：

- 读法 B；
- 单槽分位；
- no-adjust；
- source-flow；
- filtration；
- current-slot recourse。

### Level 2：连续 7 日 January pilot

检查：

- 因果性；
- 跨日 SOC；
- 场景更新；
- PWL；
- LDR/MPC 接口。

### Level 3：连续 31 日 January / 预注册 pilot

统计：

- LP/MILP 次数；
- matrix nnz；
- 场景数；
- MILP trigger rate；
- runtime median/P95/max；
- memory。

### Level 4：334 日 formal run

2–12 月配置全部冻结。

允许的预注册计算降级顺序：

\[
K:5\rightarrow3
\]

\[
|\Omega|:8\rightarrow6
\]

\[
MPC:10\rightarrow20\rightarrow30\text{ min}
\]

但必须在正式期之前选定最终配置。

## 5.24 Q3 验证

### 数据 Gate

- 35040 forecast nodes；
- issue/lead/target；
- F0；
- 小时→10 min；
- 跨年成熟性。

### 信息 Gate

- future perturbation；
- current-slot perturbation；
- 已执行动作冻结；
- 兼容场景不复活。

### 概率 Gate

\[
\sum_\omega p_\omega=1.
\]

检查 ESS、fallback、节点样本量。

### 物理 Gate

- source-flow；
- SOC；
- \(CD=0\)；
- \(H\not\rightarrow C\)；
- 不售电；
- 不跨槽使用 \(W^G\)。

### Continuation Gate

- knot 可行；
- slope convexity；
- PWL gap；
- 无未来实际数据；
- 远端 affine anchor 为 \(-0.4720\,s\)。

### 结算 Gate

\[
J^{cash}
=
J^{contract}
+
J^{emergency}.
\]

### 终端 Gate

不要求年末回 6000。

仅要求：

\[
1200\le S_{end}\le10800
\]

并报告：

- \(S_{end}\)；
- \(J^{cash}\)；
- \(J^{cmp}\)。

## 5.25 Q3 灵敏度（简）

- 结算读法 A/B；
- 场景叶 6/8/10；
- 历史窗 30/60/expanding；
- kernel bandwidth / ESS threshold；
- knots 3/5/7；
- continuation 3/5/7 日；
- MPC 10/20/30 min；
- forecast mapping；
- \(\eta\)；
- 容量/功率 ±10%；
- 远端 \(\lambda\)；
- 年末软目标 \(\rho|S_T-6000|\)；
- CVaR 仅作风险扩展；
- 负荷未知只作代表窗口扩展。

---

# 6. 公平基线、消融与价值归因

## 6.1 比较合同

所有正式比较统一：

- 评价期；
- 初始 SOC；
- 真实轨迹；
- 储能物理；
- 应急规则；
- 读法 B；
- random seed；
- solver budget；
- 统一终端库存价值修正
  \[
  \lambda^*=0.4720.
  \]

主比较优先使用：

\[
J^{cmp}
=
J^{cash}+\lambda^*(S_{start}-S_{end}).
\]

现金费用同时报告。

## 6.2 基线族

### B0a：Q2 exact replay

\[
\text{Q2 predictor}
+
\text{Q2 daily LP}
+
\text{Q2 transparent executor}.
\]

因此：

\[
J_{B0a}=J^{Q2}.
\]

### B0b：Q2 plan + Q3 MPC executor

保持 Q2：

- predictor；
- \(G^{plan}\)；
- 无 6/12/18 adjustment；

只替换执行器为 Q3 MPC。

于是：

\[
J_{B0a}-J_{B0b}
\]

刻画闭环执行升级价值。

### B1：Q3 point forecast

官方 forecast + adjustment + MPC，但不做 SAA。

### B2：Q3 conditional SAA

完整主模型。

### B3：同信息无储能

用于储能价值参照。

### LB1：hindsight lower bound

仅作为不可执行下界。

### LB2：clairvoyant lower bound

全年真实信息可见的离线下界。

可比版本应满足：

\[
J^{clairvoyant}
\le
J^{hindsight}
\le
J^{strategy}.
\]

比较使用相同的 \(J^{cmp}\) 定义。

## 6.3 官方预报服务价值

由于 2×2×2 中所有 Q3 cell 均使用官方预报，它不能单独识别“官方 forecast service value”。

单独设置：

- F0：Q2 历史 PV predictor + Q3 executor/合同规则；
- F1：官方 0:00 forecast + 同一 executor/合同规则。

则：

\[
V_{forecast}
=
J(F0)-J(F1).
\]

保持其他机制相同。

## 6.4 2×2×2 机制消融

连续 14 日季节窗口：

\[
\text{Point / SAA}
\times
\text{No-adjust / Adjust}
\times
\text{Transparent / MPC}.
\]

三因子分别解释：

- Point \(\rightarrow\) SAA：**随机/分布优化价值**；
- No-adjust \(\rightarrow\) Adjust：**合同灵活性价值**；
- Transparent \(\rightarrow\) MPC：**闭环控制价值**。

报告主效应和交互项。

不再把 Point/SAA 误称为“官方预报价值”。

## 6.5 预报时点嵌套价值

\[
N_0=\{0\},
\]

\[
N_1=\{0,6\},
\]

\[
N_2=\{0,6,12\},
\]

\[
N_3=\{0,6,12,18\}.
\]

每个集合独立重新优化。

定义：

\[
V_6=J(N_0)-J(N_1),
\]

\[
V_{12}=J(N_1)-J(N_2),
\]

\[
V_{18}=J(N_2)-J(N_3).
\]

使用同一 \(J^{cmp}\)。

不预设各边际价值为正。

---

# 7. 独立验证器与结果物化

## 7.1 独立 validator

validator 不调用模型组装函数，直接读取持久化变量并重算：

- 索引；
- 单位；
- 能量平衡；
- SOC；
- source-flow；
- 非预见性；
- 互斥；
- 目标分项；
- 费用恒等式；
- 位置映射；
- 输出 readback。

结论：

- `pass`：静态/数值检查通过；
- `partial`：有已披露限制；
- `fail`：阻断正式结果。

正式输出：

```text
fatal_day_count = 0
errors = []
```

## 7.2 Q2/Q3 终端输出

必须写：

- \(S_{start}=6000\)；
- 真实 \(S_{end}\)；
- \(J^{cash}\)；
- \(\lambda(S_{start}-S_{end})\)；
- \(J^{cmp}\)。

禁止再用“是否回 6000”作为通过条件。

## 7.3 result3

计划表：

- \(G_{d,t}\)；
- EP/EQ。

调整表：

- 最终 \(A^F_{d,t}\)；
- 中间 \(A^6,A^{12},A^{18}\) 存审计长表。

执行表：

- \(C^{exec}\)；
- \(D^{exec}\)；
- \(S^{exec}\)。

紧急表：

- \(H_t>\varepsilon_H\) 的同日连续区间合并；
- 跨日不合并；
- 无应急日不填 0 行。

输出回读必须还原：

- 首槽；
- 末槽；
- 6/12/18；
- EP/EQ；
- 费用分项；
- 紧急区间。

---

# 8. 静态修复台账

| 编号 | 原问题 | 最终修复 | 静态状态 |
|---|---|---|---|
| P0-01 | Q2 年末硬循环冲突 | 删除 Q2 年度硬约束；逐日 LP + \(-0.4720S_{day-end}\) | STATIC-PASS |
| P0-02 | Q3 年末硬回 6000 | 删除硬终端；PWL continuation + affine soft anchor | STATIC-PASS |
| P0-03 | Q2 最后一天残值是否保留 | 明确残值代表评价边界外 salvage，所有日统一 \(\lambda=0.4720\) | STATIC-PASS |
| P0-04 | Q2/Q3 期末库存不可比 | 新增 \(J^{cmp}=J^{cash}+\lambda(S_{start}-S_{end})\) | STATIC-PASS |
| P0-05 | Q3 0:00 forecast 时序 | 当日 0:00 版直接覆盖 0–24h | STATIC-PASS |
| P0-06 | Q3 6h 块 hidden clairvoyance | 槽首 filtration + 下三角 LDR | STATIC-PASS |
| P0-07 | 当前槽真实 PV 与参考动作混淆 | 区分 \(\mathcal F_{t^-}\) 与 \(\mathcal F_t\) | STATIC-PASS |
| P0-08 | 应急电可能间接充电 | source-flow 结构切断 \(H\to C\) | STATIC-PASS |
| P0-09 | continuation 超 24h 泄漏 | Bellman 嵌套 + 历史尾部 | STATIC-PASS |
| P0-10 | continuation 被误写为简单相加 | 明确嵌套 \(C_{r:T_1}+V^{hist}(S_{T_1})\) | STATIC-PASS |
| P0-11 | selective MILP 一次修补 | active-set 迭代闭包 | STATIC-PASS |
| P1-01 | kernel 使用内生 SOC | SOC 从概率特征删除 | STATIC-PASS |
| P1-02 | 场景回退复活不相容路径 | 只在 \(\Omega^{comp}\) 中重加权 | STATIC-PASS |
| P1-03 | PWL slope 符号 | 明确局部斜率为 \(-\lambda^*\) | STATIC-PASS |
| P1-04 | SAA recourse 与 MPC 未分层 | planning surrogate / actual policy 分离 | STATIC-PASS |
| P1-05 | Q2 弃光与未用电不唯一 | 固定 source priority | STATIC-PASS |
| P1-06 | Q20 理论解释弱 | 增加 0.8 净负荷 / 0.2 PV 局部报童先验 | STATIC-PASS |
| P1-07 | Q2 计划弃光无上界 | 加 \(R^{plan}\le\widehat P\) | STATIC-PASS |
| P1-08 | 预测指标与决策脱节 | 增加 coverage→H→cost 验证链 | STATIC-PASS |
| P1-09 | forecast 异常低 MAE 泄漏风险 | 增加 daylight/night/origin sanity gate | STATIC-PASS |
| P1-10 | B0 定义矛盾 | 拆 B0a exact replay / B0b Q2+MPC | STATIC-PASS |
| P1-11 | 2×2×2 归因错误 | 改为随机优化/调整权/闭环控制 | STATIC-PASS |
| P1-12 | 官方 forecast value 未单独识别 | 新增 F0/F1 同机制对照 | STATIC-PASS |
| P1-13 | 参数可事后调 | 1 月冻结超参数与计算配置 | STATIC-PASS |
| P1-14 | micro-LP 会计退化 | 增加第三级 source-priority tie-break | STATIC-PASS |

---

# 9. 最终方法总表

| 问题 | 数据预处理 | 主模型 | 求解 | 核心验证 | 灵敏度 |
|---|---|---|---|---|---|
| Q1 | 144 槽、位置映射、kW→kWh | 词典序确定性 LP + \(V_0(s)\) | HiGHS LP + active-set MILP | dual/FD/DP、物理与输出 | η、容量、功率、负荷/PV/价格 |
| Q2 | 365×144、Jan warm-up、成熟历史、近零 PV | 4 日均值 + 28 日 Q20；逐日 LP + \(-0.4720S_{day-end}\)；透明执行器 | 334 日 walk-forward HiGHS；active-set MILP | causality、coverage→H→cost、source-flow、SOC、\(J^{cmp}\) | q、窗口、cap、λ、η、容量/功率、软年末 |
| Q3 | issue/lead/target、F0、小时→10min、revision residual | 四阶段 conditional SAA + causal LDR + MPC + two-mode recourse + Bellman PWL | sparse HiGHS；条件更新；active-set MILP；Jan pilot→334d | filtration、nonanticipativity、compatible scenario、PWL gap、policy consistency、\(J^{cmp}\) | K、history、ESS/h、knots、horizon、MPC、settlement、λ、η、容量/功率 |

---

# 10. 最终论文方法结构

论文中按以下顺序展开即可：

## Q1

\[
\boxed{
\text{数据清洗}
\rightarrow
\text{词典序 LP}
\rightarrow
\text{库存值函数}
\rightarrow
\text{对偶/有限差分/DP 互证}
}
\]

## Q2

\[
\boxed{
\text{成熟历史}
\rightarrow
\text{4日同槽均值}
\rightarrow
\text{Q20 因果裕度}
\rightarrow
\text{逐日 LP + }0.4720\text{ 日界残值}
\rightarrow
\text{透明实际执行}
\rightarrow
\text{跨日 SOC 链}
}
\]

## Q3

\[
\boxed{
\text{官方滚动 forecast}
\rightarrow
\text{error/revision 场景树}
\rightarrow
\text{conditional SAA}
\rightarrow
\text{causal LDR}
\rightarrow
\text{10min MPC}
\rightarrow
\text{槽内两模式 recourse}
\rightarrow
\text{Bellman PWL continuation}
}
\]

三问最终统一为：

\[
\boxed{
\text{确定性经济调度}
\rightarrow
\text{因果预测下的逐日最优决策}
\rightarrow
\text{滚动信息驱动的多阶段自适应控制}
}
\]

而贯穿三问的核心数学主线为：

\[
\boxed{
\text{库存边际价值识别}
\rightarrow
\text{仿射日界残值}
\rightarrow
\text{信息条件凸 PWL 未来价值}
}
\]

---

# 11. 最终静态验收结论

本终极版在**方案规格层面**已经完成以下闭环：

1. 时间/单位/位置映射统一；
2. Q1/Q2/Q3 储能物理统一；
3. Q2/Q3 均删除年度硬 SOC 循环；
4. Q2 明确为逐日 LP + \(\lambda^*=0.4720\) 日界残值；
5. Q3 continuation 以同一 \(\lambda^*\) 为远端软锚；
6. 期末库存差异通过统一 \(J^{cmp}\) 处理；
7. Q3 0:00 forecast 时序闭合；
8. 槽首/槽内信息结构闭合；
9. scenario conditioning 与内生 SOC 解耦；
10. 场景回退不复活冲突历史；
11. continuation 使用 Bellman composition；
12. PWL slope 符号闭合；
13. LP→MILP exactification 使用迭代闭包；
14. SAA planning policy 与真实 MPC policy 分层；
15. Q2/Q3 source-flow 与紧急电路径闭合；
16. B0、公平比较与 2×2×2 价值归因闭合；
17. 超参数只在 1 月冻结；
18. 静态方案中不再存在“必须年末回 6000 才通过”的硬门。

仍需运行后才能变成 `RUN-PASS` 的项目只有：

- Q2 正式 result2 的真实期末 SOC 回读；
- Q2 互斥 exactness 数值证书；
- Q3 January pilot；
- Q3 334 日正式运行；
- Q3 PWL gap / scenario / MPC / MILP 实证统计；
- 新增 F0/F1、2×2×2、灵敏度数值。

这些是**计算结果待运行**，不是方案结构未闭合。

> **最终冻结声明：** 后续除非发现题面事实理解错误、程序实现与本方案不一致或独立 validator 出现 fail，否则不再修改模型结构；后续工作仅包括实现、运行、数值验证和论文表达。
