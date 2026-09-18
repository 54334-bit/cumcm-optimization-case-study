# -*- coding: utf-8 -*-
"""把最优的非预见口径跑成"可交付形态"，并输出真实紧急购电明细（逐日/逐段/论文表3 四日期）。"""
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
    rr = np.concatenate(rels)
    return float(np.clip(-np.quantile(rr, RELQ), 0.0, CAP))


s = S0; rows = []; tot = emg_cost = 0.0; qg = 0.0
t0 = time.time()
for d in DAYS:
    ks = [x for x in range(max(0, d - K), d)]
    base = (P[ks] * DT).mean(axis=0)
    marg = causal_margin(d)
    Pe_d = np.clip(base * (1 - marg), 0.0, None)
    Le = np.tile(L[d] * DT, (len(ks), 1)); Pe = np.tile(Pe_d, (len(ks), 1))
    c, Aeq, beq, Aub, bub, bd, integ, nk, nz = mp._build(Le, Pe, price, s, LAM, [])
    r = linprog(c, A_eq=Aeq, b_eq=beq, A_ub=Aub, b_ub=bub, bounds=bd, method="highs")
    if not r.success:
        print("d=%d FAIL" % d); sys.exit(2)
    G = r.x[0:T]
    # 执行：E1（用实际 L/PV），记录真实紧急购电
    ss = s; H = np.zeros(T); Cx = np.zeros(T); Dx = np.zeros(T); RPx = np.zeros(T); RGx = np.zeros(T)
    for t in range(T):
        gap = L[d][t] * DT - P[d][t] * DT - G[t]
        if gap > 1e-12:
            dd = max(0.0, min(EBAR, ETA * max(0.0, ss - SMIN), gap))
            ss -= dd / ETA; H[t] = gap - dd; Dx[t] = dd
        else:
            room = max(0.0, min(EBAR, (SMAX - ss) / ETA, -gap))
            ss += ETA * room; Cx[t] = room
            rest = -gap - room; RPx[t] = min(P[d][t] * DT, max(rest, 0.0)); RGx[t] = max(0.0, rest - RPx[t])
    cash = float((price * G).sum() + (5 * price * H).sum())
    tot += cash; emg_cost += float((5 * price * H).sum()); qg += float(G.sum())
    rows.append(dict(d=int(d), date=str(__import__("datetime").date(2025, 1, 1) + __import__("datetime").timedelta(days=d)),
                     G=[round(float(v), 6) for v in G], C=[round(float(v), 6) for v in Cx],
                     D=[round(float(v), 6) for v in Dx], H=[round(float(v), 6) for v in H],
                     RP=[round(float(v), 6) for v in RPx], RG=[round(float(v), 6) for v in RGx],
                     s0=round(float(s), 6), s1=round(float(ss), 6),
                     J_plan=round(float((price * G).sum()), 6), J_emg=round(float((5 * price * H).sum()), 6),
                     margin=round(marg, 4)))
    s = float(ss)
    if (d - 31) % 80 == 0:
        print("  d=%d 累计 %,.0f (%.0fs)".replace(",.0f", "s") % (d, f"{tot:,.0f}", time.time() - t0), flush=True)


def segs(H):
    out = []; a = None
    for t in range(T):
        pos = H[t] > 1e-9
        if pos and a is None:
            a = t
        if (not pos or t == T - 1) and a is not None:
            b = (t - 1) if not pos else t
            out.append((a, b, float(H[a:b + 1].sum()))); a = None
    return out


day_segs = {r["d"]: segs(np.array(r["H"])) for r in rows}
n_days = sum(1 for r in rows if any(x[2] > 1e-9 for x in day_segs[r["d"]]))
n_seg = sum(len(v) for v in day_segs.values())
emk = sum(sum(x[2] for x in v) for v in day_segs.values())
paper = {}
for k, dd in {"2025-03-20": 78, "2025-06-21": 171, "2025-09-23": 265, "2025-12-21": 354}.items():
    paper[k] = [{"t": "%s-%s" % (f"{a*10//60}:{a*10%60:02d}", "24:00" if (b + 1) * 10 >= 1440 else f"{(b+1)*10//60}:{(b+1)*10%60:02d}"),
                 "kWh": round(kwh, 6)} for a, b, kwh in day_segs[dd]]
res = dict(caliber="非预见：负载已知 + 光伏=最近4天情景均值 + 因果保守裕度(相对误差20%分位, 均值≈7%)；结算用实际",
           total=round(tot, 2), J_plan=round(tot - emg_cost, 2), J_emg=round(emg_cost, 2),
           QG=round(qg, 2), emergency_days=n_days, emergency_segments=n_seg,
           emergency_kwh=round(emk, 3), emergency_max_segment=max((x[2] for v in day_segs.values() for x in v), default=0.0),
           paper_table3=paper, s_end=round(s, 4), days=len(DAYS))
json.dump(dict(res=res, rows=rows), open(OUT + r"\q2_emg_detail.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in res.items() if k != "paper_table3"}, ensure_ascii=False, indent=1))
print("表3 四日期:", json.dumps(paper, ensure_ascii=False))
