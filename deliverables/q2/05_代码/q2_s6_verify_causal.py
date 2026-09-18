# -*- coding: utf-8 -*-
"""因果裕度口径 result2.xlsx 的独立核验：官方附件直读 + 从成品反解 + 贪心执行复现紧急购电。"""
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
L = np.array([[w2["小区负载"].cell(d + 2, c).value for c in range(2, 146)] for d in DAYS], float)
PV = np.array([[w2["光伏发电实际功率"].cell(d + 2, c).value for c in range(2, 146)] for d in DAYS], float)
wb = openpyxl.load_workbook(XLSX)
ws1, ws2, ws3 = wb["计划购电量"], wb["充放电量"], wb["紧急购电量"]
res = {}
G = np.zeros((len(DAYS), T)); jp = 0.0; mx = 0.0
for i in range(len(DAYS)):
    r = 2 + i
    for t in range(T):
        G[i, t] = ws1.cell(r, 2 + t).value or 0
    v = float(np.dot(price, G[i])); jp += v
    mx = max(mx, abs(v - (ws1.cell(r, 147).value or 0)))
res["J_plan_from_xlsx"] = round(jp, 4)
res["row_cost_max_dev"] = mx
res["QG_from_xlsx"] = round(float(G.sum()), 4)
soc = np.zeros((len(DAYS), 2)); Cb = 0.0; Db = 0.0
BLK = [(0, 24), (24, 48), (48, 72), (72, 96), (96, 120), (120, 144)]
for i in range(len(DAYS)):
    for k, (a, b) in enumerate(BLK):
        r = 2 + 6 * i + k
        Cb += ws2.cell(r, 3).value or 0; Db += ws2.cell(r, 4).value or 0
    soc[i, 0] = ws2.cell(2 + 6 * i, 6).value or 0
    soc[i, 1] = ws2.cell(3 + 6 * i, 6).value or 0
res["sum_C_blocks"] = round(Cb, 4); res["sum_D_blocks"] = round(Db, 4)
res["soc_min"] = float(soc.min()); res["soc_max"] = float(soc.max())
res["soc_chain_break_max"] = float(np.abs(soc[:-1, 1] - soc[1:, 0]).max())
v3 = [ws3.cell(r, 3).value for r in range(2, ws3.max_row + 1)]
res["sheet3_rows"] = len(v3)
res["sheet3_kwh"] = round(float(sum(x or 0 for x in v3)), 4)
# 贪心执行（用附件2 实测）复现紧急购电与 SOC 链
s = float(soc[0, 0]); Htot = 0.0; runs = 0; soc_dev = 0.0
for i in range(len(DAYS)):
    s = float(soc[i, 0])
    prev = False
    for t in range(T):
        gap = L[i, t] * DT - PV[i, t] * DT - G[i, t]
        if gap > 1e-12:
            dd = max(0.0, min(EBAR, ETA * max(0.0, s - SMIN), gap))
            s -= dd / ETA; h = gap - dd
            Htot += h
            if h > 1e-6:
                if not prev:
                    runs += 1
                prev = True
            else:
                prev = False
        else:
            room = max(0.0, min(EBAR, (SMAX - s) / ETA, -gap))
            s += ETA * room; prev = False
    soc_dev = max(soc_dev, abs(s - soc[i, 1]))
res["emg_kwh_greedy"] = round(Htot, 4)
res["emg_segments_greedy"] = runs
res["emg_cost_greedy"] = round(float(sum(5 * price[t] * 0 for t in range(T))) + 0.0, 4)
res["soc_vs_sheet_max_dev"] = soc_dev
# 紧急费用：需要逐区间 H，重新算一次
s = float(soc[0, 0]); emg_cost = 0.0
for i in range(len(DAYS)):
    s = float(soc[i, 0])
    for t in range(T):
        gap = L[i, t] * DT - PV[i, t] * DT - G[i, t]
        if gap > 1e-12:
            dd = max(0.0, min(EBAR, ETA * max(0.0, s - SMIN), gap))
            s -= dd / ETA
            emg_cost += 5 * price[t] * (gap - dd)
        else:
            s += ETA * max(0.0, min(EBAR, (SMAX - s) / ETA, -gap))
res["emg_cost_greedy"] = round(float(emg_cost), 4)
res["J_total_check"] = round(jp + emg_cost, 2)
ok = (abs(jp - 12891818.24) < 0.05 and mx < 1e-3 and abs(Htot - 55801.046) < 0.05
      and runs == 375  # 阈值 1e-6 kWh and res["sheet3_rows"] == 375 and abs(res["sheet3_kwh"] - 55801.046) < 0.05
      and soc_dev < 1e-3 and abs(res["J_total_check"] - 13252341.09) < 0.1)
res["ALL_PASS"] = bool(ok)
json.dump(res, open(r"D:\CMUCU\5对话\output\q2_cp5_verify_causal.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
for k, v in res.items():
    print("  %s: %s" % (k, v))
print("CP5(因果裕度):", "ALL PASS" if ok else "FAIL")
