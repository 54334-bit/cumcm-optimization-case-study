# -*- coding: utf-8 -*-
"""口径 B′（题面信息结构：负载已知、光伏不确定）微实验：
  * 日前计划：负载 = 当日**实际**负载（附件2，题面从未给负载预报；Q3 也只预报光伏）
  *            光伏 = **过去同星期几 4 个情景** (d-7,d-14,d-21,d-28)（0:00 可得，非预见）
  * 结算执行：实际负载 + **实际**光伏，缺口按 5 倍价紧急购电（E1 规则）
输出：全年费用、紧急购电天数/段数/电量、日费用分布。只写 output/q2_bprime.json。
"""
import sys, json, time, importlib.util
sys.path.append("D:\\CMUCU\\rag\\.deps"); sys.path.append(r"D:\CMUCU\5对话\code")
import numpy as np
from scipy.sparse import csr_matrix
from scipy.optimize import milp, Bounds, LinearConstraint


def load_mod(n, p):
    s = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


mm = load_mod("mm", r"D:\CMUCU\5对话\code\q2_v2_micro.py")
mp = load_mod("mp", r"D:\CMUCU\5对话\code\q2_milp_plan.py")
L, P, price = mm.load_all(); T, DT, S0 = mm.T, mm.DT, mm.S0
LAM = 0.4720
OUT = r"D:\CMUCU\5对话\output"
DAYS = list(range(31, 365))


def solve_plan(Le, Pe, s0):
    K, Tt = Le.shape
    c, Aeq, beq, Aub, bub, bd, integ, nk, nz = mp._build(Le, Pe, price, s0, LAM, [])
    lo = np.array([x[0] if x[0] is not None else -np.inf for x in bd], float)
    hi = np.array([x[1] if x[1] is not None else np.inf for x in bd], float)

    def go(cc, extra=None):
        cons = [LinearConstraint(Aeq, beq, beq)]
        A, b = Aub, bub
        if extra is not None:
            from scipy.sparse import vstack
            A = vstack([Aub, extra[0]]).tocsr(); b = np.concatenate([bub, extra[1]])
        if A is not None:
            cons.append(LinearConstraint(A, -np.inf, b))
        return milp(cc, constraints=cons, integrality=integ, bounds=Bounds(lo, hi),
                    options={"time_limit": 300, "mip_rel_gap": 1e-6})

    r1 = go(c)
    if r1.x is None:
        return None
    obj = float(r1.fun); tol = 1e-6 * max(1.0, abs(obj))
    cc = c.copy()
    for k in range(K):
        off = Tt + k * nk
        cc[off + 4 * Tt + Tt] = 0.0
    Ar = csr_matrix(c.reshape(1, -1)); br = np.array([obj + tol])
    r2 = go(cc, (Ar, br))
    x = r2.x if r2.x is not None else r1.x
    return x[0:Tt]


t0 = time.time(); s = S0
tot = 0.0; emg = 0.0; qg = 0.0; emg_days = 0; emg_seg = 0; rows = []
for d in DAYS:
    ks = [d - 7, d - 14, d - 21, d - 28]
    Le = np.tile(L[d] * DT, (4, 1))          # 负载已知：四个情景同一实际负载
    Pe = P[ks] * DT                           # 光伏不确定：四个历史同星期几情景
    G = solve_plan(Le, Pe, s)
    if G is None:
        print("d=%d fail" % d); sys.exit(2)
    H, RP, RG, se, Cx, Dx = mm.exec_E1(G, L[d] * DT, P[d] * DT, s)
    cash = float((price * G).sum() + (5 * price * H).sum())
    e = float((5 * price * H).sum()); eh = float(H.sum())
    tot += cash; emg += e; qg += float(G.sum())
    if eh > 1e-9:
        emg_days += 1
        prev = False
        for v in H:
            cur = v > 1e-9
            if cur and not prev:
                emg_seg += 1
            prev = cur
    rows.append(dict(d=int(d), cash=cash, emg=e, emg_kwh=eh, qg=float(G.sum())))
    s = float(se)
    if (d - 31) % 60 == 0:
        print(f"  d={d}  累计 {tot:,.0f}  紧急 {emg:,.0f}  天数 {emg_days}  ({time.time()-t0:.0f}s)", flush=True)
res = dict(caliber="B' : load known (actual) + PV scenarios (same weekday history) + E1 settlement",
           total=round(tot, 2), J_plan=round(tot - emg, 2), J_emg=round(emg, 2),
           QG=round(qg, 2), emergency_days=emg_days, emergency_segments=emg_seg,
           s_end=round(s, 4), days=len(DAYS), wall_sec=round(time.time() - t0, 1))
json.dump(dict(res=res, rows=rows), open(OUT + r"\q2_bprime.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
