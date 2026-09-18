# -*- coding: utf-8 -*-
"""现行口径（非预见 + 因果保守裕度）下的 λ 终端残值敏感性扫描。
计划：负荷已知、光伏 = 过去 4 天均值 × (1 − 因果裕度)；其求解目标含 −λ·S_T；
结算：附件2 实际值 + 5 倍紧急购电。
产出：output/q2_lam_new_caliber.json
"""
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
EBAR, SMIN, SMAX, ETA = mm.EBAR, mm.SMIN, mm.SMAX, mm.ETA
OUT = r"D:\CMUCU\5对话\output"; DAYS = list(range(31, 365))
K, RELQ, WIN, CAP = 4, 0.20, 28, 0.35


def causal_margin(d):
    rels = []
    for tau in range(max(K, d - WIN), d):
        kk = [x for x in range(max(0, tau - K), tau)]
        if len(kk) == K:
            f = (P[kk] * DT).mean(axis=0)
            m = f > 1.0
            if m.any():
                rels.append((P[tau] * DT - f)[m] / f[m])
    if not rels:
        return 0.0
    return float(np.clip(-np.quantile(np.concatenate(rels), RELQ), 0.0, CAP))


def run(lam, tag):
    s = S0; tot = emg = qg = 0.0; edays = eseg = 0
    for d in DAYS:
        ks = [x for x in range(max(0, d - K), d)]
        base = (P[ks] * DT).mean(axis=0) * (1 - causal_margin(d))
        base = np.clip(base, 0.0, None)
        Le = np.tile(L[d] * DT, (len(ks), 1)); Pe = np.tile(base, (len(ks), 1))
        c, Aeq, beq, Aub, bub, bd, integ, nk, nz = mp._build(Le, Pe, price, s, lam, [])
        r = linprog(c, A_eq=Aeq, b_eq=beq, A_ub=Aub, b_ub=bub, bounds=bd, method="highs")
        if not r.success:
            print("  lam=%.3f d=%d FAIL" % (lam, d)); return None
        G = r.x[0:T]
        H = np.zeros(T); ss = s
        for t in range(T):
            gap = L[d][t] * DT - P[d][t] * DT - G[t]
            if gap > 1e-12:
                dd = max(0.0, min(EBAR, ETA * max(0.0, ss - SMIN), gap))
                ss -= dd / ETA; H[t] = gap - dd
            else:
                ss += ETA * max(0.0, min(EBAR, (SMAX - ss) / ETA, -gap))
        tot += float((price * G).sum() + (5 * price * H).sum())
        emg += float((5 * price * H).sum()); qg += float(G.sum())
        if float(H.sum()) > 1e-9:
            edays += 1; prev = False
            for v in H:
                cur = v > 1e-9
                if cur and not prev:
                    eseg += 1
                prev = cur
        s = float(ss)
    r = dict(tag=tag, lam=lam, total=round(tot, 2), J_plan=round(tot - emg, 2), J_emg=round(emg, 2),
             QG=round(qg, 2), emg_days=edays, emg_segments=eseg, s_end=round(s, 2))
    print(f"  lam={lam:.3f}  total {tot:14,.2f} | J_plan {r['J_plan']:13,.0f} | emg {r['J_emg']:11,.0f} | days {edays:3d} | s_end {s:7.1f}", flush=True)
    return r


if __name__ == "__main__":
    t0 = time.time(); res = []
    for lam in [0.0, 0.15, 0.30, 0.40, 0.4720, 0.55, 0.70, 0.90]:
        r = run(lam, "lam=%.4f" % lam)
        if r:
            res.append(r)
    json.dump(res, open(OUT + r"\q2_lam_new_caliber.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    if res:
        b = min(res, key=lambda x: x["total"])
        print(f"BEST lam = {b['lam']:.4f} -> {b['total']:,.2f}")
    print("wall %.0fs" % (time.time() - t0))
