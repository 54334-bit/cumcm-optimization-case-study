# -*- coding: utf-8 -*-
"""第七轮：K×裕度组合扫描 + 因果偏差校正（修好早期无历史的回退）。"""
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


def one_day(d, K, s, margin=0.0, causal_q=None, win=28):
    ks = [x for x in range(max(0, d - K), d)]
    base = (P[ks] * DT).mean(axis=0)
    if causal_q is not None:
        errs = []
        for tau in range(max(K, d - win), d):
            kk = [x for x in range(max(0, tau - K), tau)]
            if len(kk) == K:
                errs.append(P[tau] * DT - (P[kk] * DT).mean(axis=0))
        if errs:
            E = np.array(errs)
            base = base + E.mean(axis=0)
            if causal_q > 0:
                base = base + np.quantile(E, causal_q, axis=0)
    else:
        base = base * (1 - margin)
    Le = np.tile(L[d] * DT, (len(ks), 1)); Pe = np.tile(base, (len(ks), 1))
    c, Aeq, beq, Aub, bub, bd, integ, nk, nz = mp._build(Le, Pe, price, s, LAM, [])
    r = linprog(c, A_eq=Aeq, b_eq=beq, A_ub=Aub, b_ub=bub, bounds=bd, method="highs")
    return (r.x[0:T] if r.success else None)


def run(tag, K, margin=0.0, causal_q=None):
    s = S0; tot = emg = qg = 0.0; edays = eseg = 0
    for d in DAYS:
        G = one_day(d, K, s, margin, causal_q)
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
    r = dict(tag=tag, K=K, margin=margin, causal_q=causal_q, total=round(tot, 2), J_emg=round(emg, 2),
             emg_days=edays, emg_segments=eseg, QG=round(qg, 2), s_end=round(s, 1))
    print(f"  {tag:<32s} total {tot:14,.2f} | emg {emg:11,.0f} | days {edays:3d} | seg {eseg:4d}", flush=True)
    return r


if __name__ == "__main__":
    t0 = time.time(); res = []
    for K, m in [(4, 0.05), (6, 0.05), (10, 0.05), (8, 0.045), (8, 0.055)]:
        r = run("K=%d margin %.1f%%" % (K, 100 * m), K, margin=m)
        if r:
            res.append(r)
    for q in (0.0, 0.3):
        r = run("K=8 causal bias%s" % ("+q30" if q else ""), 8, causal_q=q)
        if r:
            res.append(r)
    json.dump(res, open(OUT + r"\q2_forecast_scan7.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if res:
        print("BEST:", min(res, key=lambda x: x["total"]))
    print("wall %.0fs" % (time.time() - t0))
