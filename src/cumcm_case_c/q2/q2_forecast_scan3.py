# -*- coding: utf-8 -*-
"""第三轮扫描：在"只用过去信息"约束下寻找更低费用（SAA 情景数/结构 + 负载是否已知）。"""
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


def run(tag, K, load_known=True):
    s = S0; tot = emg = qg = 0.0; edays = eseg = 0
    for d in DAYS:
        ks = [x for x in range(max(0, d - K), d)]
        Pe = P[ks] * DT
        Le = np.tile(L[d] * DT, (len(ks), 1)) if load_known else (L[ks] * DT)
        c, Aeq, beq, Aub, bub, bd, integ, nk, nz = mp._build(Le, Pe, price, s, LAM, [])
        r = linprog(c, A_eq=Aeq, b_eq=beq, A_ub=Aub, b_ub=bub, bounds=bd, method="highs")
        if not r.success:
            print("  %s d=%d FAIL" % (tag, d)); return None
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
    print(f"  {tag:<44s} total {tot:14,.2f} | emg {emg:11,.0f} | days {edays:3d} | seg {eseg:4d}", flush=True)
    return dict(tag=tag, K=K, load_known=load_known, total=round(tot, 2), J_emg=round(emg, 2),
                emg_days=edays, emg_segments=eseg, QG=round(qg, 2), s_end=round(s, 1))


if __name__ == "__main__":
    t0 = time.time(); res = []
    res.append(run("SAA K=12 recent days (load known)", 12, True))
    res.append(run("SAA K=16 recent days (load known)", 16, True))
    res.append(run("SAA K=20 recent days (load known)", 20, True))
    res.append(run("SAA K=16 recent days (load UNKNOWN)", 16, False))
    res.append(run("SAA K=28 recent days (load known)", 28, True))
    json.dump([r for r in res if r], open(OUT + r"\q2_forecast_scan3.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("wall %.0fs" % (time.time() - t0))
