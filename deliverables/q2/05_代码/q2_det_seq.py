# -*- coding: utf-8 -*-
"""口径 A 的逐日决策 + SOC 物理链式传递（请神二次裁定口径）：
  第 d 天只用当天输入 + 当天 0:00 的 SOC；优化完把 S_{d,24} 传给第 d+1 天。
  年度循环边界用两种实现并对比：
    (i)  终端残值 lambda 标定（二分 lambda 使年末 SOC = 6000）
    (ii) 仅最后一天硬约束 S_end = 6000
  参考：全年联立 LP（离线全局下界，不用于提交）= 12,230,383.65（已算）。
产出：output/q2_det_seq.json + output/_det_seq_plan.npy（G,C,D,S，供物化）。
"""
import sys, json, time, importlib.util
sys.path.append("D:\\CMUCU\\rag\\.deps"); sys.path.append(r"D:\CMUCU\5对话\code")
import numpy as np
from scipy.sparse import csr_matrix, vstack
from scipy.optimize import linprog


def load(n, p):
    s = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


mm = load("mm", r"D:\CMUCU\5对话\code\q2_v2_micro.py")
mp = load("mp", r"D:\CMUCU\5对话\code\q2_milp_plan.py")
L, P, price = mm.load_all(); DT = mm.DT; S0 = mm.S0
DAYS = list(range(31, 365))
OUT = r"D:\CMUCU\5对话\output"


def day_opt(d, s0, lam, fix_end=None):
    Le = L[d].reshape(1, -1) * DT; Pe = P[d].reshape(1, -1) * DT
    c, Aeq, beq, Aub, bub, bd, integ, nk, nz = mp._build(Le, Pe, price, s0, lam, [])
    cons = [(Aeq, beq)]
    if fix_end is not None:
        row = csr_matrix(([1.0], ([0], [mp.T + 4 * mp.T + mp.T])), shape=(1, len(c)))
        cons.append((row, np.array([fix_end])))
    A = vstack([x[0] for x in cons]).tocsr(); b = np.concatenate([x[1] for x in cons])
    r = linprog(c, A_eq=A, b_eq=b, bounds=bd, method="highs")
    if not r.success:
        return None
    x = r.x
    return dict(G=x[0:mp.T], C=x[mp.T:mp.T + mp.T], D=x[mp.T + mp.T:mp.T + 2 * mp.T],
                S=x[mp.T + 4 * mp.T: mp.T + 5 * mp.T + 1],
                plan=float((price * x[0:mp.T]).sum()),
                emg=float((5 * price * x[mp.T + 3 * mp.T:mp.T + 4 * mp.T]).sum()))


def run_chain(lam=0.0, last_fix=None):
    s = S0; tot = 0.0; qg = 0.0; emg = 0.0; plans = {}
    for d in DAYS:
        fe = last_fix if (d == DAYS[-1] and last_fix is not None) else None
        r = day_opt(d, s, lam, fe)
        if r is None:
            return None
        plans[d] = r; tot += r["plan"] + r["emg"]; qg += float(r["G"].sum()); emg += r["emg"]
        s = float(r["S"][-1])
    return dict(total=tot, plan=tot - emg, emg=emg, qg=qg, s_end=s, plans=plans)


t0 = time.time()
r0 = run_chain(0.0)
print(f"[free end lam=0]   total {r0['total']:,.2f}  s_end {r0['s_end']:,.1f}  ({time.time()-t0:.0f}s)", flush=True)
rL = run_chain(0.0, last_fix=6000.0)
print(f"[last-day fix 6000] total {rL['total']:,.2f}  s_end {rL['s_end']:,.1f}  ({time.time()-t0:.0f}s)", flush=True)
lo, hi = 0.0, 0.6
for _ in range(8):
    mid = (lo + hi) / 2
    rr = run_chain(mid)
    print(f"   lam={mid:.4f} -> s_end {rr['s_end']:,.1f}  total {rr['total']:,.2f}  ({time.time()-t0:.0f}s)", flush=True)
    if rr["s_end"] > 6000:
        hi = mid
    else:
        lo = mid
lam_star = (lo + hi) / 2
rlam = run_chain(lam_star)
print(f"[lam*={lam_star:.4f}] total {rlam['total']:,.2f}  s_end {rlam['s_end']:,.1f}", flush=True)

best = rL if rL["total"] <= rlam["total"] else rlam
tag = "last_day_fix_6000" if rL["total"] <= rlam["total"] else "lam_star"
np.save(OUT + r"\_det_seq_plan.npy",
        np.vstack([np.concatenate([best["plans"][d]["G"] for d in DAYS]),
                   np.concatenate([best["plans"][d]["C"] for d in DAYS]),
                   np.concatenate([best["plans"][d]["D"] for d in DAYS]),
                   np.concatenate([best["plans"][d]["S"][:-1] for d in DAYS])]))
res = dict(caliber="A: day-by-day decision + SOC physical chain (per GPT 2nd ruling)",
           chosen=tag, total=best["total"], plan=best["plan"], emg=best["emg"], qg=best["qg"],
           s_end=best["s_end"], lam_star=lam_star,
           ref_free_end=r0["total"], ref_last_fix=rL["total"], ref_lam=rlam["total"],
           ref_joint_lp=12230383.646207867, wall_sec=round(time.time() - t0, 1))
json.dump(res, open(OUT + r"\q2_det_seq.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
