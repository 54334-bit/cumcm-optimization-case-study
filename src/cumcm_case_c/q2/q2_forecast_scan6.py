# -*- coding: utf-8 -*-
"""第六轮：① K=8 裕度细扫 ② 因果版偏差校正（用 d 之前的历史预报误差，逐日重估，不在同一年调到最优）。"""
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


def solve(Le, Pe, s):
    c, Aeq, beq, Aub, bub, bd, integ, nk, nz = mp._build(Le, Pe, price, s, LAM, [])
    r = linprog(c, A_eq=Aeq, b_eq=beq, A_ub=Aub, b_ub=bub, bounds=bd, method="highs")
    return (r.x[0:T] if r.success else None)


def run(tag, K, margin=0.0, causal=False, q=0.0, win=28):
    """causal=True 时：用过去 win 天的"实际-预测"误差均值(偏差)与 q 分位数(裕度)逐日校正。"""
    s = S0; tot = emg = qg = 0.0; edays = eseg = 0
    for d in DAYS:
        ks = [x for x in range(max(0, d - K), d)]
        base = (P[ks] * DT).mean(axis=0)
        if causal:
            errs = []
            for tau in range(max(1, d - win), d):
                kk = [x for x in range(max(0, tau - K), tau)]
                if len(kk) == K:
                    errs.append(P[tau] * DT - (P[kk] * DT).mean(axis=0))
            if errs:
                E = np.array(errs)
                bias = E.mean(axis=0)
                adj = np.quantile(E, q, axis=0) if q > 0 else np.zeros(T)
                Pe_each = np.tile(base + bias + adj, (len(ks), 1))
            else:
                Pe_each = np.tile(base, (len(ks), 1))
        else:
            Pe_each = np.tile(base * (1 - margin), (len(ks), 1))
        Le = np.tile(L[d] * DT, (len(ks), 1))
        G = solve(Le, Pe_each, s)
        if G is None:
            print("  %s d=%d FAIL" % (tag, d)); return None
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
    r = dict(tag=tag, K=K, margin=margin, causal=causal, quantile=q, total=round(tot, 2),
             J_emg=round(emg, 2), emg_days=edays, emg_segments=eseg, QG=round(qg, 2), s_end=round(s, 1))
    print(f"  {tag:<34s} total {tot:14,.2f} | emg {emg:11,.0f} | days {edays:3d} | seg {eseg:4d}", flush=True)
    return r


if __name__ == "__main__":
    t0 = time.time(); res = []
    for m in (0.02, 0.03, 0.04, 0.06):
        r = run("K=8 margin %d%%" % (100 * m), 8, margin=m)
        if r:
            res.append(r)
    for q in (0.2, 0.4, 0.5):
        r = run("K=8 causal bias+q%d" % (100 * q), 8, causal=True, q=q)
        if r:
            res.append(r)
    json.dump(res, open(OUT + r"\q2_forecast_scan6.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if res:
        print("best:", min(res, key=lambda x: x["total"]))
    print("wall %.0fs" % (time.time() - t0))
