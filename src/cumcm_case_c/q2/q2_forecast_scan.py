# -*- coding: utf-8 -*-
"""预报质量扫描：计划只用【过去可得信息】，结算用【实际】负载/光伏 + E1 规则。
比较不同日前光伏预报构造下的全年费用与紧急购电形态（均为非预见、可复现口径）。
"""
import sys, json, time, importlib.util
sys.path.append("D:\\CMUCU\\rag\\.deps"); sys.path.append(r"D:\CMUCU\5对话\code")
import numpy as np
import openpyxl
from scipy.optimize import linprog


def load_mod(n, p):
    s = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


mm = load_mod("mm", r"D:\CMUCU\5对话\code\q2_v2_micro.py")
mp = load_mod("mp", r"D:\CMUCU\5对话\code\q2_milp_plan.py")
L, P, price = mm.load_all(); T, DT, S0 = mm.T, mm.DT, mm.S0
LAM = 0.4720
OUT = r"D:\CMUCU\5对话\output"
DAYS = list(range(31, 365))
_w1 = openpyxl.load_workbook(r"D:\CMUCU\赛题\C题\附件\附件1.xlsx")["Sheet1"]
PV_A1 = np.array([_w1.cell(r, 4).value for r in range(2, 146)], float) * DT   # 附件1 典型日光伏预报
LD_A1 = np.array([_w1.cell(r, 3).value for r in range(2, 146)], float) * DT   # 附件1 典型日负载
print("附件1 典型日: 负载 %.1f kWh | 光伏 %.1f kWh" % (LD_A1.sum(), PV_A1.sum()))


def plan_point(Lday, Pvhat, s0):
    Le = Lday.reshape(1, -1); Pe = Pvhat.reshape(1, -1)
    c, Aeq, beq, Aub, bub, bd, integ, nk, nz = mp._build(Le, Pe, price, s0, LAM, [])
    r = linprog(c, A_eq=Aeq, b_eq=beq, A_ub=Aub, b_ub=bub, bounds=bd, method="highs")
    if not r.success:
        return None
    return r.x[0:T]


def run(tag, pvhat_fn, load_fn=None):
    s = S0; tot = 0.0; emg = 0.0; qg = 0.0; edays = 0; eseg = 0
    for d in DAYS:
        Lp = (load_fn(d) if load_fn else L[d] * DT)
        G = plan_point(Lp, pvhat_fn(d), s)
        if G is None:
            print("  %s d=%d FAIL" % (tag, d)); return None
        H, RP, RG, se, Cx, Dx = mm.exec_E1(G, L[d] * DT, P[d] * DT, s)
        tot += float((price * G).sum() + (5 * price * H).sum())
        emg += float((5 * price * H).sum()); qg += float(G.sum())
        if float(H.sum()) > 1e-9:
            edays += 1
            prev = False
            for v in H:
                cur = v > 1e-9
                if cur and not prev:
                    eseg += 1
                prev = cur
        s = float(se)
    r = dict(tag=tag, total=round(tot, 2), J_emg=round(emg, 2), QG=round(qg, 2),
             emg_days=edays, emg_segments=eseg, s_end=round(s, 1))
    print(f"  {tag:<40s} total {tot:14,.2f} | emg {emg:11,.0f} | days {edays:3d} | seg {eseg:4d}", flush=True)
    return r


def past_mean_pv(d, ks, margin=0.0):
    idx = [d - 7 * k for k in ks if d - 7 * k >= 0]
    if not idx:
        return PV_A1 * (1 - margin)
    return (P[idx] * DT).mean(axis=0) * (1 - margin)


if __name__ == "__main__":
    t0 = time.time()
    res = []
    res.append(run("C: att1 typical-day forecast", lambda d: PV_A1))
    for m in (0.10, 0.20, 0.30):
        res.append(run("C+margin %.0f%% (att1 x (1-m))" % (100 * m), lambda d, m=m: PV_A1 * (1 - m)))
    res.append(run("past-4-same-weekday MEAN (point)", lambda d: past_mean_pv(d, [1, 2, 3, 4])))
    for m in (0.10, 0.20, 0.30):
        res.append(run("past-4-same-weekday MEAN -%.0f%%" % (100 * m),
                       lambda d, m=m: past_mean_pv(d, [1, 2, 3, 4], m)))
    res.append(run("past-8-same-weekday MEAN", lambda d: past_mean_pv(d, [1, 2, 3, 4, 5, 6, 7, 8])))
    res.append(run("past-12-same-weekday MEAN", lambda d: past_mean_pv(d, list(range(1, 13)))))
    res.append(run("last-7-days MEAN", lambda d: (P[[x for x in range(max(0, d - 7), d)]] * DT).mean(axis=0)))
    res.append(run("actual PV (perfect info bound)", lambda d: P[d] * DT))
    json.dump([r for r in res if r], open(OUT + r"\q2_forecast_scan.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("wall %.0fs" % (time.time() - t0))
