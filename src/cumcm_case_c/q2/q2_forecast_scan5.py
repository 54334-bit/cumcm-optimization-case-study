# -*- coding: utf-8 -*-
"""第五轮逼近：① K=4..7（负载已知、最近 K 天光伏情景）② 在 K=8 上加偏置裕度（情景×(1-m)）。"""
import sys, json, time, importlib.util
sys.path.append("D:\\CMUCU\\rag\\.deps"); sys.path.append(r"D:\CMUCU\5对话\code")
import numpy as np
from scipy.optimize import linprog


def load_mod(n, p):
    s = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


mm = load_mod("mm", r"D:\CMUCU\5对话\code\q2_v2_micro.py")
mp = load_mod("mp", r"D:\CMUCU\5对话\code\q2_milp_plan.py")
L, P, price = mm.load_all(); T, DT, S0 = mm.T, mm.DT, mm.S0
LAM = 0.4720; OUT = r"D:\CMUCU\5对话\output"; DAYS = list(range(31, 365))


def run(K, margin=0.0):
    s = S0; tot = emg = qg = 0.0; edays = eseg = 0
    for d in DAYS:
        ks = [x for x in range(max(0, d - K), d)]
        Le = np.tile(L[d] * DT, (len(ks), 1))
        Pe = P[ks] * DT * (1.0 - margin)
        c, Aeq, beq, Aub, bub, bd, integ, nk, nz = mp._build(Le, Pe, price, s, LAM, [])
        r = linprog(c, A_eq=Aeq, b_eq=beq, A_ub=Aub, b_ub=bub, bounds=bd, method="highs")
        if not r.success:
            return None
        G = r.x[0:T]
        H, RP, RG, se, Cx, Dx = mm.exec_E1(G, L[d] * DT, P[d] * DT, s)
        tot += float((price * G).sum() + (5 * price * H).sum()); emg += float((5 * price * H).sum())
        qg += float(G.sum())
        if float(H.sum()) > 1e-9:
            edays += 1; prev = False
            for v in H:
                cur = v > 1e-9
                if cur and not prev:
                    eseg += 1
                prev = cur
        s = float(se)
    return dict(K=K, margin=margin, total=round(tot, 2), J_emg=round(emg, 2), emg_days=edays,
                emg_segments=eseg, QG=round(qg, 2), s_end=round(s, 1))


if __name__ == "__main__":
    t0 = time.time(); res = []
    for K in (4, 5, 6, 7):
        r = run(K)
        if r:
            res.append(r)
            print(f"  K={K} (load known)  total {r['total']:14,.2f} | emg {r['J_emg']:11,.0f} | "
                  f"days {r['emg_days']:3d} | seg {r['emg_segments']:4d} | {time.time()-t0:.0f}s", flush=True)
    for m in (0.05, 0.10):
        r = run(8, m)
        if r:
            res.append(r)
            print(f"  K=8 margin {m:.0%}  total {r['total']:14,.2f} | emg {r['J_emg']:11,.0f} | "
                  f"days {r['emg_days']:3d} | {time.time()-t0:.0f}s", flush=True)
    json.dump(res, open(OUT + r"\q2_forecast_scan5.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if res:
        b = min(res, key=lambda x: x["total"])
        print("best:", b)
    print("wall %.0fs" % (time.time() - t0))
