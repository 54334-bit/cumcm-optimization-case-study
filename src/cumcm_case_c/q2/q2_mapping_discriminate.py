# -*- coding: utf-8 -*-
"""判别性检验：同一份提交件，按两种列映射读出来的方案，哪一种在附件2 实测数据下物理可行。
位置映射：col 2+t = 时段 t（请神终裁）；标签对齐：col 145 = t=0、col t+1 = t≥1（旧写法）。
"""
import sys, json
sys.path.append("D:\\CMUCU\\rag\\.deps")
import numpy as np, openpyxl

XLSX = r"D:\CMUCU\5对话\result2.xlsx"
A2 = r"D:\CMUCU\赛题\C题\附件\附件2.xlsx"
T, DT = 144, 1 / 6
EBAR, SMIN, SMAX, ETA = 5000 * DT, 1200.0, 10800.0, 0.9
DAYS = list(range(31, 365))
w2 = openpyxl.load_workbook(A2)
L = np.array([[w2["小区负载"].cell(d + 2, c).value for c in range(2, 146)] for d in DAYS], float)
PV = np.array([[w2["光伏发电实际功率"].cell(d + 2, c).value for c in range(2, 146)] for d in DAYS], float)
wb = openpyxl.load_workbook(XLSX); ws1, ws2 = wb["计划购电量"], wb["充放电量"]


def read(mode):
    G = np.zeros((len(DAYS), T))
    for i in range(len(DAYS)):
        r = 2 + i
        for t in range(T):
            col = (2 + t) if mode == "positional" else (145 if t == 0 else t + 1)
            G[i, t] = ws1.cell(r, col).value or 0
    return G


res = {}
for mode in ["positional", "label_aligned"]:
    G = read(mode)
    s = float(ws2.cell(2, 6).value or 6000); emg = 0.0; short_days = 0; worst = 0.0
    for i, d in enumerate(DAYS):
        for t in range(T):
            gap = L[i, t] * DT - PV[i, t] * DT - G[i, t]
            if gap > 0:
                dd = max(0.0, min(EBAR, ETA * max(0.0, s - SMIN), gap))
                s -= dd / ETA
                short = gap - dd
                if short > 1e-6:
                    emg += short
                    if short > 1e-3:
                        short_days += 1
                    worst = max(worst, short)
            else:
                s += ETA * max(0.0, min(EBAR, (SMAX - s) / ETA, -gap))
    res[mode] = dict(total_emergency_kwh=round(emg, 3), days_with_shortage=short_days,
                     worst_shortage_kwh=round(worst, 3), s_end=round(s, 2))
    print(f"{mode:14s} 全年紧急购电 {emg:13,.2f} kWh | 有缺口天数 {short_days:3d} | 单区间最大缺口 {worst:9.2f} kWh")
json.dump(res, open(r"D:\CMUCU\5对话\output\q2_mapping_discriminate.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("\n判别结论:", "位置映射可行（0 紧急）→ 修复方向正确" if res["positional"]["total_emergency_kwh"] < 1e-3 else "异常：位置映射不可行")
