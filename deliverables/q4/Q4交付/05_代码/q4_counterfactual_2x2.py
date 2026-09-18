# -*- coding: utf-8 -*-
"""2x2 反事实交叉结算（GPT 共验建议："最能封口"的一张表）
 行 = 计划来源（附件1 价下优化 / 附件4 价下优化）；列 = 结算价格（附件1 / 附件4）
 执行器 E1 只依赖 (G, 实际 L/PV)，与价格无关 ⇒ H 由 G 决定，价格只影响计费。
只读；只写 8对话\output。
"""
import sys, os, json
import numpy as np
import pandas as pd
from scipy.optimize import linprog
import importlib.util

sys.path.append("D:\\CMUCU\\rag\\.deps")
sys.path.append(r"D:\CMUCU\5对话\code")

def load(n, p):
    s = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m

mm = load("mm", r"D:\CMUCU\5对话\code\q2_v2_micro.py")
mp = load("mp", r"D:\CMUCU\5对话\code\q2_milp_plan.py")
L, P, PRICE1 = mm.load_all()
T, DT, S0 = mm.T, mm.DT, mm.S0
EBAR, SMIN, SMAX, ETA = mm.EBAR, mm.SMIN, mm.SMAX, mm.ETA
LAM = 0.4720
K, WIN, CAP = 4, 28, 0.35
DAYS = list(range(31, 365))
OUT = r"D:\CMUCU\8对话\output"
P4 = pd.read_csv(r"D:\CMUCU\B对话\clean\attachment4_clean.csv").iloc[:, 1:].to_numpy(float)


def margin(d, relq=0.20):
    rels = []
    for tau in range(max(K, d - WIN), d):
        kk = list(range(max(0, tau - K), tau))
        if len(kk) == K:
            f = (P[kk] * DT).mean(axis=0)
            m = f > 1.0
            if m.any():
                rels.append((P[tau] * DT - f)[m] / f[m])
    if not rels:
        return 0.0
    return float(np.clip(-np.quantile(np.concatenate(rels), relq), 0.0, CAP))


def build_plan(price_of_day, tag):
    """按给定价格优化逐日计划，并对实际数据执行 E1，返回逐日 G/H 与各自价格下的现金。"""
    s = S0
    Gs = np.zeros((len(DAYS), T))
    Hs = np.zeros((len(DAYS), T))
    for i, d in enumerate(DAYS):
        ks = list(range(max(0, d - K), d))
        base = (P[ks] * DT).mean(axis=0)
        Pe_d = np.clip(base * (1 - margin(d)), 0.0, None)
        Le = np.tile(L[d] * DT, (K, 1))
        Pe = np.tile(Pe_d, (K, 1))
        pk = price_of_day(d)
        c, Aeq, beq, Aub, bub, bd, integ, nk, nz = mp._build(Le, Pe, pk, s, LAM, [])
        r = linprog(c, A_eq=Aeq, b_eq=beq, A_ub=Aub, b_ub=bub, bounds=bd, method="highs")
        if not r.success:
            raise RuntimeError("d=%d" % d)
        G = r.x[0:T]
        ss = s
        H = np.zeros(T)
        for t in range(T):
            gap = L[d][t] * DT - P[d][t] * DT - G[t]
            if gap > 1e-12:
                dd = max(0.0, min(EBAR, ETA * max(0.0, ss - SMIN), gap))
                ss -= dd / ETA
                H[t] = gap - dd
            else:
                room = max(0.0, min(EBAR, (SMAX - ss) / ETA, -gap))
                ss += ETA * room
        Gs[i] = G
        Hs[i] = H
        s = ss
    print("  计划来源=%s 已生成（334 天）" % tag, flush=True)
    return Gs, Hs


def settle(Gs, Hs, price_of_day):
    plan = 0.0
    emg = 0.0
    for i, d in enumerate(DAYS):
        pk = price_of_day(d)
        plan += float((pk * Gs[i]).sum())
        emg += float((5.0 * pk * Hs[i]).sum())
    return plan, emg, plan + emg


print("=== 2x2 反事实交叉结算 ===", flush=True)
G1, H1 = build_plan(lambda d: PRICE1, "附件1 价下优化（=Q2 计划）")
G4, H4 = build_plan(lambda d: P4[d], "附件4 价下优化（=Q4-2 计划）")

p1_of = lambda d: PRICE1
p4_of = lambda d: P4[d]
r = {}
r["G1P1"] = settle(G1, H1, p1_of)
r["G1P4"] = settle(G1, H1, p4_of)
r["G4P1"] = settle(G4, H4, p1_of)
r["G4P4"] = settle(G4, H4, p4_of)

print("", flush=True)
print("| 计划来源 | 结算价格 | 计划购电费 | 紧急购电费 | 总成本 | 相对 Q2 |", flush=True)
print("| --- | --- | ---: | ---: | ---: | ---: |", flush=True)
names = {"G1P1": ("Q2 计划(附件1下优化)", "附件1"), "G1P4": ("Q2 计划(附件1下优化)", "附件4"),
         "G4P1": ("Q4 计划(附件4下优化)", "附件1"), "G4P4": ("Q4 计划(附件4下优化)", "附件4")}
base = r["G1P1"][2]
for k in ("G1P1", "G1P4", "G4P1", "G4P4"):
    pl, em, tt = r[k]
    print("| %s | %s | %s | %s | **%s** | %s |" % (names[k][0], names[k][1],
          format(pl, ",.2f"), format(em, ",.2f"), format(tt, ",.2f"), format(100 * (tt - base) / base, "+.3f") + "%"), flush=True)

price_eff = r["G1P4"][2] - r["G1P1"][2]
reopt_eff = r["G4P4"][2] - r["G1P4"][2]
print("", flush=True)
print("  总差 = %s 元" % format(r["G4P4"][2] - r["G1P1"][2], ",.2f"), flush=True)
print("  其中①价格环境效应（同一 Q2 计划只换结算价）= %s 元" % format(price_eff, ",.2f"), flush=True)
print("  其中②计划重优化效应（附件4 价下重新优化）= %s 元" % format(reopt_eff, ",.2f"), flush=True)
print("  校验：①+② = %s 元" % format(price_eff + reopt_eff, ",.2f"), flush=True)

json.dump(dict(cells={k: dict(J_plan=v[0], J_emg=v[1], total=v[2]) for k, v in r.items()},
               price_effect=price_eff, reopt_effect=reopt_eff,
               total_diff=r["G4P4"][2] - r["G1P1"][2]),
          open(OUT + r"\q4_counterfactual_2x2.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("已落盘 q4_counterfactual_2x2.json", flush=True)
