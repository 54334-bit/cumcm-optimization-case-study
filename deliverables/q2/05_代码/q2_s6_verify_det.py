# -*- coding: utf-8 -*-
"""独立核验：从提交件 result2.xlsx 自身单元格 + 官方附件1/附件2 反算（口径 A）。
不使用任何中间 npy/json 结论。"""
import sys, json
sys.path.append("D:\\CMUCU\\rag\\.deps")
import numpy as np, openpyxl

XLSX = r"D:\CMUCU\5对话\result2.xlsx"
A1 = r"D:\CMUCU\赛题\C题\附件\附件1.xlsx"
A2 = r"D:\CMUCU\赛题\C题\附件\附件2.xlsx"
T, DT = 144, 1 / 6
EBAR, SMIN, SMAX, ETA = 5000 * DT, 1200.0, 10800.0, 0.9
DAYS = list(range(31, 365))

w1 = openpyxl.load_workbook(A1)["Sheet1"]
price = np.array([w1.cell(r, 2).value for r in range(2, 146)], float)
w2 = openpyxl.load_workbook(A2)
sL, sP = w2["小区负载"], w2["光伏发电实际功率"]
L = np.array([[sL.cell(d + 2, c).value for c in range(2, 146)] for d in DAYS], float)
PV = np.array([[sP.cell(d + 2, c).value for c in range(2, 146)] for d in DAYS], float)

wb = openpyxl.load_workbook(XLSX)
ws1, ws2, ws3 = wb["计划购电量"], wb["充放电量"], wb["紧急购电量"]
res = {}
G = np.zeros((len(DAYS), T)); jp = 0.0; mx = 0.0
for i in range(len(DAYS)):
    r = 2 + i
    for t in range(T):
        G[i, t] = ws1.cell(r, 2 + t).value or 0      # 位置映射：列序=时序
    v = float(np.dot(price, G[i])); jp += v
    mx = max(mx, abs(v - (ws1.cell(r, 147).value or 0)))
res["J_plan_from_xlsx"] = round(jp, 4)
res["row_cost_max_dev"] = mx
res["QG_from_xlsx"] = round(float(G.sum()), 4)
Cb = np.zeros((len(DAYS), 6)); Db = np.zeros((len(DAYS), 6)); soc = np.zeros((len(DAYS), 2))
BLK = [(0, 24), (24, 48), (48, 72), (72, 96), (96, 120), (120, 144)]
for i in range(len(DAYS)):
    for k, (a, b) in enumerate(BLK):
        r = 2 + 6 * i + k
        Cb[i, k] = ws2.cell(r, 3).value or 0
        Db[i, k] = ws2.cell(r, 4).value or 0
    soc[i, 0] = ws2.cell(2 + 6 * i, 6).value or 0
    soc[i, 1] = ws2.cell(3 + 6 * i, 6).value or 0
res["sum_C_blocks"] = round(float(Cb.sum()), 4)
res["sum_D_blocks"] = round(float(Db.sum()), 4)
res["soc_chain_break_max"] = float(np.abs(soc[:-1, 1] - soc[1:, 0]).max())
res["soc_min"] = float(soc.min()); res["soc_max"] = float(soc.max())
res["soc_start"] = float(soc[0, 0]); res["soc_end"] = float(soc[-1, 1])
vals3 = [ws3.cell(r, 3).value for r in range(2, ws3.max_row + 1)]
res["sheet3_rows"] = len(vals3)
res["sheet3_all_zero"] = all((v == 0 or v is None) for v in vals3)
res["unserved_days"] = 0; worst = 0.0
for i in range(len(DAYS)):
    s = soc[i, 0]; bad = 0
    for t in range(T):
        gap = L[i, t] * DT - PV[i, t] * DT - G[i, t]
        if gap > 0:
            dd = min(EBAR, ETA * max(0.0, s - SMIN), gap)
            s -= dd / ETA
            if gap - dd > 1e-6:
                bad += 1; worst = max(worst, gap - dd)
        else:
            room = max(0.0, min(EBAR, (SMAX - s) / ETA, -gap))
            s += ETA * room
    if abs(s - soc[i, 1]) > 1e-3:
        bad += 1
    if bad:
        res["unserved_days"] += 1
res["worst_unserved_kwh"] = worst
ok = (abs(jp - 12254696.55) < 0.01 and mx < 1e-3 and res["soc_chain_break_max"] < 1e-4
      and res["soc_min"] >= SMIN - 1e-6 and res["soc_max"] <= SMAX + 1e-6
      and res["sheet3_all_zero"] and res["unserved_days"] == 0)
res["all_pass"] = bool(ok)
json.dump(res, open(r"D:\CMUCU\5对话\output\q2_cp5_verify_det.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
for k, v in res.items():
    print("  %s: %s" % (k, v))
print("CP5(A):", "ALL PASS" if ok else "FAIL")
