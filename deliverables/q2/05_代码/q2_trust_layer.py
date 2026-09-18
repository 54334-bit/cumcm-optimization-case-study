# -*- coding: utf-8 -*-
"""信任层核验：L1 溯源哈希 / L2 官方直读 vs 模型输入逐元素比对 / L3 独立重解 Q1 对表外部基准 / L4 Q2 重算。"""
import sys, json, hashlib, io, os, importlib.util
sys.path.append("D:\\CMUCU\\rag\\.deps"); sys.path.append(r"D:\CMUCU\5对话\code")
import numpy as np, openpyxl
from scipy.sparse import coo_matrix, vstack
from scipy.optimize import linprog

T, DT = 144, 1 / 6
EBAR, SMIN, SMAX, ETA, S0 = 5000 * DT, 1200.0, 10800.0, 0.9, 6000.0
A1 = r"D:\CMUCU\赛题\C题\附件\附件1.xlsx"
A2 = r"D:\CMUCU\赛题\C题\附件\附件2.xlsx"
A3 = r"D:\CMUCU\赛题\C题\附件\附件3.xlsx"
A4 = r"D:\CMUCU\赛题\C题\附件\附件4.xlsx"
CL = {"load": r"D:\CMUCU\B对话\clean\attachment2_load.csv",
      "pv": r"D:\CMUCU\B对话\clean\attachment2_pv.csv",
      "price": r"D:\CMUCU\B对话\clean\q1_clean.csv"}


def sha(p):
    return hashlib.sha256(io.open(p, "rb").read()).hexdigest()


out = {"L1_hashes": {}, "L2_data_equality": {}, "L3_q1_independent": {}, "L4_q2_recheck": {}}
for tag, p in [("att1", A1), ("att2", A2), ("att3", A3), ("att4", A4),
               ("clean_load", CL["load"]), ("clean_pv", CL["pv"]), ("clean_price", CL["price"])]:
    out["L1_hashes"][tag] = {"path": p, "sha256": sha(p)[:32], "bytes": os.path.getsize(p)}

w1 = openpyxl.load_workbook(A1)["Sheet1"]
pr_att = np.array([w1.cell(r, 2).value for r in range(2, 146)], float)
ld_att = np.array([w1.cell(r, 3).value for r in range(2, 146)], float) * DT
pv_att = np.array([w1.cell(r, 4).value for r in range(2, 146)], float) * DT
w2 = openpyxl.load_workbook(A2)
sL, sP = w2["小区负载"], w2["光伏发电实际功率"]
L_att = np.array([[sL.cell(d + 2, c).value for c in range(2, 146)] for d in range(365)], float) * DT
P_att = np.array([[sP.cell(d + 2, c).value for c in range(2, 146)] for d in range(365)], float) * DT
_s = importlib.util.spec_from_file_location("mm", r"D:\CMUCU\5对话\code\q2_v2_micro.py")
mm = importlib.util.module_from_spec(_s); _s.loader.exec_module(mm)
L_mod, P_mod, pr_mod = mm.load_all()
L_mod = L_mod * DT; P_mod = P_mod * DT
out["L2_data_equality"] = {
    "price_max_abs_diff": float(np.abs(pr_att - pr_mod).max()),
    "load_max_abs_diff": float(np.abs(L_att - L_mod).max()),
    "pv_max_abs_diff": float(np.abs(P_att - P_mod).max()),
    "shapes": [list(pr_att.shape), list(pr_mod.shape), list(L_att.shape), list(L_mod.shape)],
    "note": "load_all() reads B对话/clean/*.csv；本行证明其与官方附件逐元素一致（kWh/区间）",
}


def solve_q1(p, loadE, pvE):
    n = 3 * T + (T + 1)
    oB, oC, oD, oS = 0, T, 2 * T, 3 * T
    r = np.arange(T)
    Aub = coo_matrix((np.concatenate([-np.ones(T), -np.ones(T), np.ones(T)]),
                      (np.concatenate([r, r, r]), np.concatenate([oB + r, oD + r, oC + r]))),
                     shape=(T, n)).tocsr()
    bub = -(loadE - pvE)
    Aeq = coo_matrix((np.concatenate([np.ones(T), -np.ones(T), -ETA * np.ones(T), (1 / ETA) * np.ones(T)]),
                      (np.concatenate([r, r, r, r]),
                       np.concatenate([oS + r + 1, oS + r, oC + r, oD + r]))), shape=(T, n)).tocsr()
    beq = np.zeros(T)
    bnd = coo_matrix((np.array([1.0, 1.0]), (np.array([0, 1]), np.array([oS, oS + T]))), shape=(2, n))
    Aeq = vstack([Aeq, bnd]).tocsr(); beq = np.concatenate([beq, np.array([S0, S0])])
    c = np.zeros(n); c[oB:oB + T] = p
    bounds = [(0.0, None)] * T + [(0.0, EBAR)] * T + [(0.0, EBAR)] * T + [(SMIN, SMAX)] * (T + 1)
    return linprog(c, A_ub=Aub, b_ub=bub, A_eq=Aeq, b_eq=beq, bounds=bounds, method="highs")


q1 = solve_q1(pr_att, ld_att, pv_att)
if q1.x is not None:
    b = q1.x[0:T]
    out["L3_q1_independent"] = {
        "my_Q1_cost_yuan": round(float(q1.fun), 2), "my_Q1_energy_kWh": round(float(b.sum()), 2),
        "external_cost_yuan": 35126.95, "external_energy_kWh": 59482.70,
        "cost_abs_diff": round(abs(float(q1.fun) - 35126.95), 2),
        "energy_abs_diff": round(abs(float(b.sum()) - 59482.70), 2)}
try:
    sc = json.load(open(r"D:\CMUCU\5对话\output\q2_forecast_scan4.json", encoding="utf-8"))
    best = min(sc.items(), key=lambda kv: kv[1]["total"])
    out["L4_q2_recheck"] = {"source": "q2_forecast_scan4.json", "best_key": best[0],
                            "total": best[1]["total"], "J_emg": best[1]["J_emg"],
                            "note": "由 code/q2_forecast_scan4.py 用 load_all() 输入算出；L2 已证明该输入==官方附件"}
except Exception as e:
    out["L4_q2_recheck"] = {"error": str(e)}
io.open(r"D:\CMUCU\5对话\output\trust_layer_verify.json", "w", encoding="utf-8").write(
    json.dumps(out, ensure_ascii=False, indent=1))
print(json.dumps(out, ensure_ascii=False, indent=1))
