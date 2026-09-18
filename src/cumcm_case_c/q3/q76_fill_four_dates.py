# -*- coding: utf-8 -*-
"""从整改后的 result3.xlsx 直取四个指定日期的表1/表2/表3 数字，直出论文素材 md。"""
import datetime as dt
from openpyxl import load_workbook

X = r"D:\CMUCU\7.6对话\交付\Q3交付\01_提交件\result3_v2.xlsx"   # v2（v2b 口径）
OUT = r"D:\CMUCU\7.6对话\交付\Q3交付\03_论文素材\论文表1表2表3_四个指定日期_v2.md"
DAYS = {"2025-03-20": 49, "2025-06-21": 142, "2025-09-23": 236, "2025-12-21": 325}
SLOTS = [("10:00-10:10", 10, 0), ("12:00-12:10", 12, 0), ("14:00-14:10", 14, 0),
         ("16:00-16:10", 16, 0), ("18:00-18:10", 18, 0), ("20:00-20:10", 20, 0)]

wb = load_workbook(X, read_only=True, data_only=True)
plan = list(wb["计划购电量"].iter_rows(min_row=2, values_only=True))
adj = list(wb["调整购电量"].iter_rows(min_row=2, values_only=True))
soc = list(wb["充放电量"].iter_rows(min_row=2, values_only=True))
emg = list(wb["紧急购电量"].iter_rows(min_row=2, values_only=True))

lines = ["# 论文表1/表2/表3：四个指定日期（源：交付件 result3.xlsx，整改后 4 小时段)",
         "",
         "> 列映射 `col = 2 + t`（t=0 → 第 2 列 = [0:00,0:10)）；单位 kWh / 元。",
         "> 证据：`01_提交件\\result3.xlsx`（行 49/142/236/325 = 3-20/6-21/9-23/12-21）。",
         ""]

for date, row in DAYS.items():
    pr, ar = plan[row - 2], adj[row - 2]
    lines += [f"## {date}", "", "**表1 购电量（指定时段）**", "",
              "| 时段 | 计划购电量 | 调整购电量 |", "| --- | ---: | ---: |"]
    for lbl, h, m in SLOTS:
        col = 1 + (h * 6 + m // 10)  # 0-based -> col index in tuple (col=2+t -> idx=1+t)
        lines.append(f"| {lbl} | {pr[col]:.4f} | {ar[col]:.4f} |")
    lines += [f"| **全天购电量** | **{pr[145]:.4f}** | **{ar[145]:.4f}** |",
              f"| **全天购电费（元）** | **{pr[146]:.4f}** | **{ar[146]:.4f}** |", ""]

    base = (row - 2) * 6
    lines += ["**表2 充放电量（四小时段）与 0:00 / 24:00 储电量**", "",
              "| 时间段 | 充电量 | 放电量 |", "| --- | ---: | ---: |"]
    for k in range(6):
        r = soc[base + k]
        lines.append(f"| {r[1]} | {r[2]:.4f} | {r[3]:.4f} |")
    s_vals = [r[5] for r in soc[base:base + 6] if r[5] is not None]
    lines += [f"| 0:00 储电量 | {s_vals[0]:.4f} | |",
              f"| 24:00 储电量 | {s_vals[-1]:.4f} | |",
              "", f"（当日储电量序列，源文件同日内仅写首末两值：{['%.4f' % v for v in s_vals]}）", ""]

    segs = [r for r in emg if isinstance(r[0], dt.datetime) and r[0].date().isoformat() == date]
    lines += ["**表3 紧急购电**", "", "| 日期 | 时间段 | 购电量 |", "| --- | --- | ---: |"]
    if segs:
        first = True
        for r in segs:
            d = date if first else ""
            first = False
            rng = r[1].strftime("%H:%M") if isinstance(r[1], (dt.time, dt.datetime)) else str(r[1])
            lines.append(f"| {d} | {rng} | {float(r[2]):.4f} |")
        lines.append(f"| **当日合计** | | **{sum(float(r[2]) for r in segs):.4f}** |")
    else:
        lines.append("| （当日无紧急购电） | | |")
    lines.append("")

import os
os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT, "w", encoding="utf-8").write("\n".join(lines))
print("OK ->", OUT, len(lines), "lines")
print("\n".join(lines[:26]))
