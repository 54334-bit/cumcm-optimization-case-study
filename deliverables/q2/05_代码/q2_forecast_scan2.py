# -*- coding: utf-8 -*-
"""补充扫描：① 多样本 SAA（过去 16 / 30 天情景）② 用附件3 的 0:00 官方预报做计划。
结算一律用附件2 实际负载/光伏 + E1 规则；链式 SOC。"""
import sys, json, time, importlib.util
sys.path.append("D:\\CMUCU\\rag\\.deps"); sys.path.append(r"D:\CMUCU\5对话\code")
import numpy as np, openpyxl
from scipy.optimize import linprog, milp, Bounds, LinearConstraint
from scipy.sparse import vstack, csr_matrix


def load_mod(n, p):
    s = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


mm = load_mod("mm", r"D:\CMUCU\5对话\code\q2_v2_micro.py")
mp = load_mod("mp", r"D:\CMUCU\5对话\code\q2_milp_plan.py")
L, P, price = mm.load_all(); T, DT, S0 = mm.T, mm.DT, mm.S0
LAM = 0.4720; OUT = r"D:\CMUCU\5对话\output"; DAYS = list(range(31, 365))

# ---- 附件3：取每天 0:00 那一条预报（24 个逐时 kW），线性插值到 144 个 10 分钟点 ----
wb3 = openpyxl.load_workbook(r"D:\CMUCU\赛题\C题\附件\附件3.xlsx")["Sheet1"]
FC3 = np.zeros((365, T))
for d in range(365):
    r = 2 + 4 * d                      # 每天第一行 = 0:00 预报
    if str(wb3.cell(r, 2).value).strip() not in ("0:00", "0:00:00"):
        r = 2 + 4 * d
    vals = np.array([wb3.cell(r, 3 + h).value or 0.0 for h in range(24)], float)   # 24 个逐时 kW
    hourly = np.repeat(vals, 6) * DT    # 每小时均分到 6 个 10 分钟区间（kWh/区间）
    FC3[d] = hourly


def plan_saa(Le, Pe, s0):
    K, Tt = Le.shape
    c, Aeq, beq, Aub, bub, bd, integ, nk, nz = mp._build(Le, Pe, price, s0, LAM, [])
    r = linprog(c, A_eq=Aeq, b_eq=beq, A_ub=Aub, b_ub=bub, bounds=bd, method="highs")
    if not r.success:
        return None
    return r.x[0:Tt]


def chain(pv_or_scen, tag, saa=False):
    s = S0; tot = 0.0; emg = 0.0; edays = 0; eseg = 0; qg = 0.0
    for d in DAYS:
        if saa:
            ks = [x for x in range(max(0, d - pv_or_scen), d)]
            Le = np.tile(L[d] * DT, (len(ks), 1)); Pe = P[ks] * DT
        else:
            Le = (L[d] * DT).reshape(1, -1); Pe = pv_or_scen(d).reshape(1, -1)
        G = plan_saa(Le, Pe, s)
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
    print(f"  {tag:<38s} total {tot:14,.2f} | emg {emg:11,.0f} | days {edays:3d} | seg {eseg:4d}", flush=True)
    return dict(tag=tag, total=round(tot, 2), J_emg=round(emg, 2), emg_days=edays, emg_segments=eseg, QG=round(qg, 2))


res = []
res.append(chain(16, "SAA past-16-days scenarios", saa=True))
res.append(chain(30, "SAA past-30-days scenarios", saa=True))
res.append(chain(lambda d: FC3[d], "ATT3 0:00 official forecast (Q3 input!)", saa=False))
json.dump([r for r in res if r], open(OUT + r"\q2_forecast_scan2.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
