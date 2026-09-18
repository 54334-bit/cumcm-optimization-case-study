# -*- coding: utf-8 -*-
"""电价波动效应的时间块拆解（队长强调"电价波动要谨慎对待"）
用 2×2 反事实的同一套计划（附件1 价下优化 / 附件4 价下优化），把
  ①价格环境效应 = Cash(计划1, 附件4价) − Cash(计划1, 附件1价)
  ②重优化效应   = Cash(计划4, 附件4价) − Cash(计划1, 附件4价)
按 6 个四小时块（0-4/4-8/…/20-24）拆开，看效应集中在哪个时段。
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
BLK = [(0, 36), (36, 72), (72, 108), (108, 144)]


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


def plan_and_exec(price_of_day):
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
    return Gs, Hs


def cost_by_block(Gs, Hs, price_of_day):
    out = np.zeros(len(BLK))
    for i, d in enumerate(DAYS):
        pk = price_of_day(d)
        for bi, (a, b) in enumerate(BLK):
            out[bi] += float((pk[a:b] * Gs[i][a:b]).sum() + (5.0 * pk[a:b] * Hs[i][a:b]).sum())
    return out


print("=== 电价效应分块拆解（4 个四小时块） ===", flush=True)
G1, H1 = plan_and_exec(lambda d: PRICE1)
G4, H4 = plan_and_exec(lambda d: P4[d])
c11 = cost_by_block(G1, H1, lambda d: PRICE1)
c14 = cost_by_block(G1, H1, lambda d: P4[d])
c44 = cost_by_block(G4, H4, lambda d: P4[d])
eff_price = c14 - c11
eff_reopt = c44 - c14
print("  %-14s %16s %16s %16s %16s" % ("时段块", "①价格效应", "②重优化", "①+②", "占块内①比%"), flush=True)
tot = 0.0
for bi, (a, b) in enumerate(BLK):
    lbl = "%02d:00-%02d:00" % (a * 10 // 60, b * 10 // 60)
    print("  %-14s %16s %16s %16s %16.1f%%" % (
        lbl, format(eff_price[bi], ",.2f"), format(eff_reopt[bi], ",.2f"),
        format(eff_price[bi] + eff_reopt[bi], ",.2f"),
        100 * eff_price[bi] / c11[bi]), flush=True)
    tot += eff_price[bi]
print("  合计 ①=%s 元、②=%s 元、①+②=%s 元" % (
    format(eff_price.sum(), ",.2f"), format(eff_reopt.sum(), ",.2f"), format((eff_price + eff_reopt).sum(), ",.2f")), flush=True)
json.dump(dict(blocks=["%02d-%02d" % (a * 10 // 60, b * 10 // 60) for a, b in BLK],
               c11=list(c11), c14=list(c14), c44=list(c44),
               eff_price=list(eff_price), eff_reopt=list(eff_reopt),
               total_price=float(eff_price.sum()), total_reopt=float(eff_reopt.sum())),
          open(OUT + r"\q4_price_block_decomp.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("已落盘 q4_price_block_decomp.json", flush=True)
