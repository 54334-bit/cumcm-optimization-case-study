# -*- coding: utf-8 -*-
"""第四轮：① 细扫情景数 K（负载已知）② 在最优 K 上扫执行层储备下限（不再重解计划）。"""
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
LAM = 0.4720; OUT = r"D:\CMUCU\5对话\output"; DAYS = list(range(31, 365))


def plan_and_cache(K):
    """返回每日的计划 G（负载已知 + 最近 K 天光伏情景）。"""
    plans = {}; s = S0
    for d in DAYS:
        ks = [x for x in range(max(0, d - K), d)]
        Le = np.tile(L[d] * DT, (len(ks), 1)); Pe = P[ks] * DT
        c, Aeq, beq, Aub, bub, bd, integ, nk, nz = mp._build(Le, Pe, price, s, LAM, [])
        r = linprog(c, A_eq=Aeq, b_eq=beq, A_ub=Aub, b_ub=bub, bounds=bd, method="highs")
        if not r.success:
            return None
        plans[d] = r.x[0:T]
        s = float(r.x[T + 4 * T + T])          # 计划的日末 SOC（用于下一日）
    return plans


def settle(plans, floor=SMIN, cap=0.0):
    """按计划的 G 执行；执行层 = E1 + 储备下限 floor（放电不跌破 floor）。cap：最大放电比例(0=不限制)。"""
    s = S0; tot = emg = qg = 0.0; edays = eseg = 0
    for d in DAYS:
        G = plans[d]
        La, Pa = L[d] * DT, P[d] * DT
        H = np.zeros(T)
        for t in range(T):
            gap = La[t] - Pa[t] - G[t]
            if gap > 1e-12:
                dd = max(0.0, min(EBAR, ETA * max(0.0, s - floor), gap))
                s -= dd / ETA
                H[t] = gap - dd
            else:
                room = max(0.0, min(EBAR, (SMAX - s) / ETA, -gap))
                s += ETA * room
        tot += float((price * G).sum() + (5 * price * H).sum())
        emg += float((5 * price * H).sum()); qg += float(G.sum())
        if float(H.sum()) > 1e-9:
            edays += 1; prev = False
            for v in H:
                cur = v > 1e-9
                if cur and not prev:
                    eseg += 1
                prev = cur
    return dict(total=round(tot, 2), J_emg=round(emg, 2), emg_days=edays, emg_segments=eseg,
                QG=round(qg, 2), s_end=round(s, 1))


if __name__ == "__main__":
    t0 = time.time(); res = {}
    for K in (8, 10, 12, 14):
        pl = plan_and_cache(K)
        if pl is None:
            print("K=%d plan FAIL" % K); continue
        r = settle(pl)
        res["K%d" % K] = dict(K=K, **r)
        print(f"  K={K:2d} (load known)  total {r['total']:14,.2f} | emg {r['J_emg']:11,.0f} | "
              f"days {r['emg_days']:3d} | seg {r['emg_segments']:4d} | {time.time()-t0:.0f}s", flush=True)
    best = min(res.items(), key=lambda kv: kv[1]["total"])
    print("best:", best[0], best[1]["total"])
    pl = plan_and_cache(best[1]["K"])
    for F in (1200, 1500, 1800, 2100, 2400):
        r = settle(pl, floor=F)
        print(f"  floor={F:5d}  total {r['total']:14,.2f} | emg {r['J_emg']:11,.0f} | days {r['emg_days']:3d}", flush=True)
        res["floor%d" % F] = dict(floor=F, **r)
    json.dump(res, open(OUT + r"\q2_forecast_scan4.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("wall %.0fs" % (time.time() - t0))
