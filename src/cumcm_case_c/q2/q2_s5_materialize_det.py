# -*- coding: utf-8 -*-
"""物化口径 A 的 result2（提交件）：模板只读，另存副本。
表1 计划购电量：**位置映射 col = 2+t**（请神第 3 次终裁：列序=时序；旧"t=0→第145列"对齐标签的写法作废）；
表2 充放电量（每天 6 块，0:00/24:00 边界）；表3 紧急购电量（每天固定 3 行，全部填 0）。
"""
import sys, json, datetime as dt
sys.path.append("D:\\CMUCU\\rag\\.deps")
import numpy as np, openpyxl

TPL = r"D:\CMUCU\赛题\C题\附件\附件5\result2.xlsx"
DST_SUB = r"D:\CMUCU\5对话\result2.xlsx"
DST_ALT = r"D:\CMUCU\5对话\result2_对话5_确定性A.xlsx"
OUT = r"D:\CMUCU\5对话\output"
T = 144

price = np.array(json.load(open(OUT + r"\_price_cache.json", encoding="utf-8")))
Z = np.load(OUT + r"\_det_seq_plan.npy")
N = Z.shape[1]
DAYS = list(range(31, 365))
assert N == len(DAYS) * T, N
G = Z[0].reshape(len(DAYS), T); C = Z[1].reshape(len(DAYS), T)
D = Z[2].reshape(len(DAYS), T); S = Z[3].reshape(len(DAYS), T)


def date_of(d):
    return dt.date(2025, 1, 1) + dt.timedelta(days=d)


wb = openpyxl.load_workbook(TPL)
ws1, ws2, ws3 = wb["计划购电量"], wb["充放电量"], wb["紧急购电量"]
ck = []

# 表1
for i, d in enumerate(DAYS):
    r = 2 + i
    for t in range(T):
        col = 2 + t                      # 列序=时序：第 2 列 = [0:00,0:10)
        ws1.cell(r, col).value = round(float(G[i][t]), 8)
    ws1.cell(r, 146).value = round(float(G[i].sum()), 6)
    ws1.cell(r, 147).value = round(float(np.dot(price, G[i])), 4)
    ck.append(("t1 row %d date" % r, ws1.cell(r, 1).value is not None
               and ws1.cell(r, 1).value.date() == date_of(d)))

# 表2：每天 6 块；0:00 与 24:00 边界 SOC
BLK = [("0:00-4:00", 0, 24), ("4:00-8:00", 24, 48), ("8:00-12:00", 48, 72),
       ("12:00-16:00", 72, 96), ("16:00-20:00", 96, 120), ("20:00-24:00", 120, 144)]
for i, d in enumerate(DAYS):
    for k, (lab, a, b) in enumerate(BLK):
        r = 2 + 6 * i + k
        ws2.cell(r, 1).value = dt.datetime(date_of(d).year, date_of(d).month, date_of(d).day) if k == 0 else None
        ws2.cell(r, 2).value = lab
        ws2.cell(r, 3).value = round(float(C[i][a:b].sum()), 8)
        ws2.cell(r, 4).value = round(float(D[i][a:b].sum()), 8)
        ws2.cell(r, 5).value = None
        ws2.cell(r, 6).value = None
    s0 = float(S[i][0]); s1 = float(S[i + 1][0]) if i + 1 < len(DAYS) else 6000.0
    ws2.cell(2 + 6 * i, 5).value = dt.time(0, 0); ws2.cell(2 + 6 * i, 6).value = round(s0, 6)
    ws2.cell(3 + 6 * i, 5).value = "24:00";       ws2.cell(3 + 6 * i, 6).value = round(s1, 6)

# 表3：每天固定 3 行，全部 0
for r in range(2, ws3.max_row + 1):
    for c in range(1, 4):
        ws3.cell(r, c).value = None
row = 2
for i, d in enumerate(DAYS):
    for k in range(3):
        ws3.cell(row, 1).value = dt.datetime(date_of(d).year, date_of(d).month, date_of(d).day) if k == 0 else None
        ws3.cell(row, 2).value = None
        ws3.cell(row, 3).value = 0
        row += 1

wb.save(DST_SUB)
import shutil
shutil.copy2(DST_SUB, DST_ALT)
tot_plan = float(sum(np.dot(price, G[i]) for i in range(len(DAYS))))
qg = float(G.sum())
json.dump(dict(total_plan_cost=tot_plan, QG=qg, emergency_kwh=0.0, emergency_cost=0.0,
               days=len(DAYS), rows_sheet3=row - 2,
               check=[list(x) for x in ck if not x[1]]),
          open(OUT + r"\q2_det_materialize.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("written:", DST_SUB)
print(f"全年计划购电费 {tot_plan:,.2f} 元 | 计划电量 {qg:,.2f} kWh | 紧急 0 | 表3 数据行 {row-2}")
print("结构自检失败项:", [x[0] for x in ck if not x[1]] or "无")
