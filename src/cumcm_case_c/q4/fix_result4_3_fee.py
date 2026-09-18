# -*- coding: utf-8 -*-
"""修复 result4-3.xlsx 的「全天购电费」列：改用**附件4** 价格（本问自身口径）
成因：调用他人物化器时其 price_csv 硬编码为附件1 ⇒ 该列按附件1 生成，列和 13,225,150.38
证据：两份监理（q4_site_guard / q4_cross_consistency）独立发现
做法：用逐段真值 q4_q3v2_seg.jsonl（G0/A/H）× 附件4 重算日总额，写回【我自己的】xlsx
"""
import json
import numpy as np
import pandas as pd
import openpyxl

XLSX = r"D:\CMUCU\8对话\output\result4-3.xlsx"
SEG = r"D:\CMUCU\8对话\output\q4_q3v2_seg.jsonl"
P4 = pd.read_csv(r"D:\CMUCU\B对话\clean\attachment4_clean.csv").iloc[:, 1:].to_numpy(float)

recs = [json.loads(l) for l in open(SEG, encoding="utf-8") if l.strip()]
print("逐段记录 %d 天" % len(recs), flush=True)

fees, old = [], []
wb = openpyxl.load_workbook(XLSX)
ws = wb["计划购电量"]
for i, r in enumerate(recs):
    d = int(r["d"])
    G0 = np.asarray(r["G0"], float)
    A = np.asarray(r["A"], float)
    H = np.asarray(r["H"], float)
    p = P4[d]
    jp = float((p * np.minimum(G0, A)).sum())
    ja = float((0.5 * p * np.maximum(G0 - A, 0) + 1.5 * p * np.maximum(A - G0, 0)).sum())
    je = float((5.0 * p * H).sum())
    row = i + 2
    old.append(ws.cell(row=row, column=147).value)
    ws.cell(row=row, column=147, value=jp + ja + je)
    fees.append(jp + ja + je)

old = [float(x or 0) for x in old]
print("旧列和（附件1 生成）= %s" % format(sum(old), ",.6f"), flush=True)
print("新列和（附件4 重算）= %s" % format(sum(fees), ",.6f"), flush=True)
print("期望头条             = 13,727,033.660000", flush=True)
assert abs(sum(fees) - 13727033.66) < 0.05, "列和不等于头条数字！"
wb.save(XLSX)
wb.close()
print("已写回 %s" % XLSX, flush=True)

# ---- 第二张表：调整购电量（同名列同样按附件1 生成，需同改）----
wb = openpyxl.load_workbook(XLSX)
if "调整购电量" in wb.sheetnames:
    ws2 = wb["调整购电量"]
    old2 = []
    for i in range(len(recs)):
        row = i + 2
        old2.append(float(ws2.cell(row=row, column=147).value or 0))
        ws2.cell(row=row, column=147, value=fees[i])
    print("调整表 旧列和 = %s -> 新列和 = %s"
          % (format(sum(old2), ",.6f"), format(sum(fees), ",.6f")), flush=True)
    wb.save(XLSX)
wb.close()

wb = openpyxl.load_workbook(XLSX, read_only=True)
tot = sum(float(r[146] or 0) for r in wb["计划购电量"].iter_rows(min_row=2, max_row=335, values_only=True))
tot2 = 0.0
if "调整购电量" in wb.sheetnames:
    tot2 = sum(float(r[146] or 0) for r in wb["调整购电量"].iter_rows(min_row=2, max_row=335, values_only=True))
wb.close()
print("复核：计划购电量表 第147列和 = %s" % format(tot, ",.6f"), flush=True)
print("参考：调整购电量表 第147列和 = %s（口径待与 Q3 对齐，须在交付说明写明）" % format(tot2, ",.6f"), flush=True)
