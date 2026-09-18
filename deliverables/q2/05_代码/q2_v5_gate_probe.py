# -*- coding: utf-8 -*-
"""按外部方案 v5.0 的 P0 关口，对现有交付解做结构体检（只读）。"""
import sys, json
sys.path.append("D:\\CMUCU\\rag\\.deps")
import numpy as np, openpyxl
from scipy.sparse import coo_matrix, vstack
from scipy.optimize import linprog

T, DT, S0 = 144, 1 / 6, 6000.0
out = {}
J = json.load(open(r"D:\CMUCU\5对话\output\q2_emg_detail.json", encoding="utf-8"))
rows = {int(r["d"]): r for r in J["rows"]}
DAYS = sorted(rows)
w1 = openpyxl.load_workbook(r"D:\CMUCU\赛题\C题\附件\附件1.xlsx")["Sheet1"]
p1 = np.array([w1.cell(r, 2).value for r in range(2, 146)], float)
ld = np.array([w1.cell(r, 3).value for r in range(2, 146)], float) * DT
pv = np.array([w1.cell(r, 4).value for r in range(2, 146)], float) * DT


def solve_q1(eta_c, eta_d, cap=5000 * DT):
    n = 3 * T + (T + 1)
    oB, oC, oD, oS = 0, T, 2 * T, 3 * T
    rr = np.arange(T)
    Aub = coo_matrix((np.concatenate([-np.ones(T), -np.ones(T), np.ones(T)]),
                      (np.concatenate([rr, rr, rr]), np.concatenate([oB + rr, oD + rr, oC + rr]))),
                     shape=(T, n)).tocsr()
    bub = -(ld - pv)
    Aeq = coo_matrix((np.concatenate([np.ones(T), -np.ones(T), -eta_c * np.ones(T), (1 / eta_d) * np.ones(T)]),
                      (np.concatenate([rr, rr, rr, rr]),
                       np.concatenate([oS + rr + 1, oS + rr, oC + rr, oD + rr]))), shape=(T, n)).tocsr()
    beq = np.zeros(T)
    bnd = coo_matrix((np.array([1.0, 1.0]), (np.array([0, 1]), np.array([oS, oS + T]))), shape=(2, n))
    Aeq = vstack([Aeq, bnd]).tocsr(); beq = np.concatenate([beq, np.array([S0, S0])])
    c = np.zeros(n); c[oB:oB + T] = p1
    bd = [(0.0, None)] * T + [(0.0, cap)] * T + [(0.0, cap)] * T + [(1200.0, 10800.0)] * (T + 1)
    r = linprog(c, A_ub=Aub, b_ub=bub, A_eq=Aeq, b_eq=beq, bounds=bd, method="highs")
    return (float(r.fun), float(r.x[0:T].sum())) if r.success else (None, None)


rl = solve_q1(0.9, 0.9)
rr_ = solve_q1(np.sqrt(0.9), np.sqrt(0.9))
out["P0_2_efficiency"] = {
    "external_Q1_benchmark": {"cost": 35126.95, "energy": 59482.70},
    "per_leg_0.9": {"cost": round(rl[0], 2), "energy": round(rl[1], 2)},
    "roundtrip_0.9": {"cost": round(rr_[0], 2), "energy": round(rr_[1], 2)},
    "verdict": "per-leg 0.9 matches external benchmark" if abs(rl[0] - 35126.95) < 0.01 else "needs review",
}
bad_charge = bad_curt = h_ints = 0
worst = 0.0
chi_exec = 0.0
for d in DAYS:
    H = np.array(rows[d]["H"], float); C = np.array(rows[d]["C"], float)
    D = np.array(rows[d]["D"], float)
    RP = np.array(rows[d]["RP"], float); RG = np.array(rows[d]["RG"], float)
    chi_exec = max(chi_exec, float(np.minimum(C, D).max()))
    for t in range(T):
        if H[t] > 1e-9:
            h_ints += 1
            if C[t] > 1e-9:
                bad_charge += 1
            if RP[t] > 1e-6 or RG[t] > 1e-6:
                bad_curt += 1
                worst = max(worst, RP[t] + RG[t])
out["P0_4_emergency_use"] = {"intervals_with_H": h_ints, "H_and_charge": bad_charge,
                             "H_and_curtail": bad_curt, "max_curtail_when_H": round(worst, 6)}
out["P0_5_mutex_executed"] = round(chi_exec, 9)
json.dump(out, open(r"D:\CMUCU\5对话\output\q2_v5_gate_probe.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
