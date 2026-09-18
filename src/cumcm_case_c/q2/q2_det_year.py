# -*- coding: utf-8 -*-
"""口径 A（题面主口径，请神裁定）：确定性、已知当天实际负载/光伏 —— 全年联立 LP 全局最优。

变量（按 10 分钟区间 i 展开，N = 334*144 = 48,096）：
  G_i >= 0                计划购电量（take-or-pay，按量计费）
  C_i, D_i in [0, EBAR]   充电/放电电量
  S_i in [SMIN, SMAX]     储电量（N+1 个节点）
约束：① 供电不低于负载：G_i + PV_i + D_i >= L_i + C_i
      ② SOC 递推：S_{i+1} - S_i - ETA*C_i + D_i/ETA = 0
      ③ S_0 = S_N = 6000 kWh（终端闭合；Q2 无"每日 0:00=24:00"约束）
目标：min sum p_i*G_i（已知信息下最优不会触发紧急购电，另以可行性检查确认）
数据：官方附件 1/附件 2（已逐格对拍通过）。
"""
import sys, json, time, importlib.util
sys.path.append("D:\\CMUCU\\rag\\.deps"); sys.path.append(r"D:\CMUCU\5对话\code")
import numpy as np
from scipy.sparse import coo_matrix, vstack, csr_matrix, eye
from scipy.optimize import linprog


def load(n, p):
    s = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


mm = load("mm", r"D:\CMUCU\5对话\code\q2_v2_micro.py")
L, P, price = mm.load_all()
T, DT, EBAR, SMIN, SMAX, ETA, S0 = mm.T, mm.DT, mm.EBAR, mm.SMIN, mm.SMAX, mm.ETA, mm.S0
DAYS = list(range(31, 365))
N = len(DAYS) * T
Lv = np.concatenate([L[d] * DT for d in DAYS])
Pv = np.concatenate([P[d] * DT for d in DAYS])
pv = np.tile(price, len(DAYS))

oG, oC, oD, oS = 0, N, 2 * N, 3 * N
n = 3 * N + (N + 1)

# ① 供电不低于负载： -(G + D - C) <= -(L - PV)
r = np.arange(N)
Aub = coo_matrix((np.concatenate([-np.ones(N), -np.ones(N), np.ones(N)]),
                  (np.concatenate([r, r, r]), np.concatenate([oG + r, oD + r, oC + r]))),
                 shape=(N, n)).tocsr()
bub = -(Lv - Pv)

# ② SOC：S_{i+1} - S_i - ETA*C_i + D_i/ETA = 0
Aeq = coo_matrix((np.concatenate([np.ones(N), -np.ones(N), -ETA * np.ones(N), (1.0 / ETA) * np.ones(N)]),
                  (np.concatenate([r, r, r, r]),
                   np.concatenate([oS + r + 1, oS + r, oC + r, oD + r]))),
                 shape=(N, n)).tocsr()
beq = np.zeros(N)
# ③ 终端/初始 SOC
bnd = csr_matrix((np.array([1.0, 1.0]), (np.array([0, 1]), np.array([oS, oS + N]))), shape=(2, n))
Aeq = vstack([Aeq, bnd]).tocsr()
beq = np.concatenate([beq, np.array([S0, S0])])

c = np.zeros(n); c[oG:oG + N] = pv
bounds = ([(0.0, None)] * N + [(0.0, EBAR)] * N + [(0.0, EBAR)] * N + [(SMIN, SMAX)] * (N + 1))
print(f"N={N} vars={n} Aeq={Aeq.shape} nnz={Aeq.nnz} Aub_nnz={Aub.nnz}", flush=True)
t0 = time.time()
res = linprog(c, A_ub=Aub, b_ub=bub, A_eq=Aeq, b_eq=beq, bounds=bounds, method="highs")
print("status", res.status, str(res.message)[:70], "obj", res.fun, f"{time.time()-t0:.0f}s", flush=True)
if res.x is None:
    sys.exit(2)
x = res.x
G = x[oG:oG + N]; C = x[oC:oC + N]; D = x[oD:oD + N]; S = x[oS:oS + N + 1]
slack = G + Pv + D - Lv - C
soc = np.diff(S) - ETA * C + D / ETA
out = dict(caliber="A deterministic (known actual L/PV), full-year joint LP",
           total_cost=float(res.fun), days=len(DAYS), intervals=N,
           plan_kwh=float(G.sum()), charge_kwh=float(C.sum()), discharge_kwh=float(D.sum()),
           curtail_pv_kwh=float(slack.clip(min=0).sum()),
           shortfall_kwh=float((-slack).clip(min=0).sum()),
           soc_min=float(S.min()), soc_max=float(S.max()), s_end=float(S[-1]),
           check_supply_slack_min=float(slack.min()), check_soc_resid_max=float(np.abs(soc).max()),
           wall_sec=round(time.time() - t0, 1))
json.dump(out, open(r"D:\CMUCU\5对话\output\q2_det_year.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
np.save(r"D:\CMUCU\5对话\output\_det_year_plan.npy", np.vstack([G, C, D, S[:-1]]))
print(json.dumps(out, ensure_ascii=False, indent=1))
