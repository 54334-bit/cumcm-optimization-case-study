# -*- coding: utf-8 -*-
"""按【因果裕度非预见口径】物化 result2.xlsx：
 表1 计划购电量（位置映射 col = 2+t，第 2 列 = [0:00,0:10)）
 表2 充放电量（执行层 E1 实际充放电 + 每块首行 0:00 / 次行 24:00 储电量）
 表3 紧急购电量（**只写真实发生时段**，同日相邻正 H 合并，跨日不合并 —— 按模板示例格式）
"""
import sys, json, datetime as dt
sys.path.append("D:\\CMUCU\\rag\\.deps")
import numpy as np, openpyxl, shutil

TPL = r"D:\CMUCU\赛题\C题\附件\附件5\result2.xlsx"
SRC = r"D:\CMUCU\5对话\output\q2_emg_detail.json"
DSUB = r"D:\CMUCU\5对话\result2.xlsx"
DALT = r"D:\CMUCU\5对话\result2_对话5_因果裕度非预见.xlsx"
T = 144
price = np.array(json.load(open(r"D:\CMUCU\5对话\output\_price_cache.json", encoding="utf-8")), float)
J = json.load(open(SRC, encoding="utf-8"))
rows = {int(r["d"]): r for r in J["rows"]}
DAYS = sorted(rows)
assert len(DAYS) == 334


def date_of(d):
    return dt.date(2025, 1, 1) + dt.timedelta(days=d)


def hhmm(minutes):
    return "24:00" if minutes >= 1440 else "%d:%02d" % (minutes // 60, minutes % 60)


wb = openpyxl.load_workbook(TPL)
ws1, ws2, ws3 = wb["计划购电量"], wb["充放电量"], wb["紧急购电量"]
ck = []
for i, d in enumerate(DAYS):
    r = 2 + i
    G = rows[d]["G"]
    for t in range(T):
        ws1.cell(r, 2 + t).value = round(float(G[t]), 8)          # 位置映射
    ws1.cell(r, 146).value = round(float(np.sum(G)), 6)
    ws1.cell(r, 147).value = round(float(np.dot(price, np.array(G))), 4)
    ck.append(("t1 row %d date" % r, ws1.cell(r, 1).value is not None
               and ws1.cell(r, 1).value.date() == date_of(d)))
BLK = [("0:00-4:00", 0, 24), ("4:00-8:00", 24, 48), ("8:00-12:00", 48, 72),
       ("12:00-16:00", 72, 96), ("16:00-20:00", 96, 120), ("20:00-24:00", 120, 144)]
for i, d in enumerate(DAYS):
    C = rows[d]["C"]; D = rows[d]["D"]
    for k, (lab, a, b) in enumerate(BLK):
        r = 2 + 6 * i + k
        ws2.cell(r, 1).value = dt.datetime(date_of(d).year, date_of(d).month, date_of(d).day) if k == 0 else None
        ws2.cell(r, 2).value = lab
        ws2.cell(r, 3).value = round(float(np.sum(C[a:b])), 8)
        ws2.cell(r, 4).value = round(float(np.sum(D[a:b])), 8)
        ws2.cell(r, 5).value = None
        ws2.cell(r, 6).value = None
    ws2.cell(2 + 6 * i, 5).value = dt.time(0, 0); ws2.cell(2 + 6 * i, 6).value = round(float(rows[d]["s0"]), 6)
    ws2.cell(3 + 6 * i, 5).value = "24:00";       ws2.cell(3 + 6 * i, 6).value = round(float(rows[d]["s1"]), 6)
for r in range(2, ws3.max_row + 1):
    for c in range(1, 4):
        ws3.cell(r, c).value = None
row = 2; nseg = 0
for d in DAYS:
    H = np.array(rows[d]["H"], float)
    a = None
    segs = []
    for t in range(T):
        pos = H[t] > 1e-9
        if pos and a is None:
            a = t
        if (not pos or t == T - 1) and a is not None:
            b = (t - 1) if not pos else t
            segs.append((a, b)); a = None
    for j, (a, b) in enumerate(segs):
        if j == 0:
            ws3.cell(row, 1).value = dt.datetime(date_of(d).year, date_of(d).month, date_of(d).day)
        ws3.cell(row, 2).value = "%s-%s" % (hhmm(a * 10), hhmm((b + 1) * 10))
        ws3.cell(row, 3).value = round(float(np.sum(H[a:b + 1])), 6)
        row += 1; nseg += 1
wb.save(DSUB); shutil.copy2(DSUB, DALT)
json.dump(dict(rows_written_sheet3=nseg, sheet3_last_row=row, struct_check_fail=[x[0] for x in ck if not x[1]]),
          open(r"D:\CMUCU\5对话\output\q2_cp4_materialize_causal.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("written:", DSUB)
print("表3 写入真实紧急段数 =", nseg, "| 结构自检失败:", [x[0] for x in ck if not x[1]] or "无")
