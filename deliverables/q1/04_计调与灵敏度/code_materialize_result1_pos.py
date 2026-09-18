"""Q1 result1 物化（**位置对齐**口径，2026-09-12 口径修订版）。

为什么改口径
------------
原物化脚本 `materialize_result1.py` 用「标签对齐 + 循环回卷」：把 `G[i]` 填到
标签为 `t_{i}–t_{i+1}` 的行，导致首时段 `[0:00,0:10)` 的 `G[0]` 被塞进末行
`0:00+1-0:10+1`。该口径已由四条独立证据推翻：

1. 模板标签整体后移一格：`result1.xlsx`/`result2.xlsx` 的 144 个数据行标签为
   `0:10-0:20 … 23:50-0:00+1`、末行 `0:00+1-0:10+1`，而实际一天是 `0:00–24:00`；
   公开实现 `li2396803/cumcm2026-c-microgrid-dispatch` 的
   `work/src/write_results.py` 开头即写明「模板标签整体后移一格」，
   并用 `slot_labels()` 生成正确的 `0:00-0:10 …` 标签。
2. 附件 1/2 的 144 个值本身就是同日时间序（附件 2 末列 `0:00+1` 是 24:00 的右端点
   记法，不是次日首列）。
3. 判别性实测（对话 5）：同一份调度按位置读 → 全年紧急购电 0 kWh、缺口 0 天；
   按标签读 → 紧急购电 257,989.97 kWh、缺口 1,819 天。
4. 本机自查：`G[0]=1406.6411` 是 `[0:00,0:10)` 的购电，旧文件却把它放在最后一行。

本口径下：
    B[r+2] = G[r]        （r = 0..143）
    第 2 行 = `[0:00,0:10)`，第 145 行 = `[23:50,24:00)`
**模板原有标签文字一律不动**（只改「值与位置的对应关系」）。

红线：不改 `result*.xlsx` 模板、不改 `q1_checkpoint.json` 的数值、不重新优化
（最优解本身不变：`J_actual = 35126.948624416575`、`Q_G = 59482.698915258756`）。
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from typing import Dict, List

import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)

TEMPLATE = r"D:\CMUCU\赛题\C题\附件\附件5\result1.xlsx"
CHECKPOINT = os.path.join(BASE, "output", "q1_checkpoint.json")
OUT_XLSX = os.path.join(BASE, "output", "result1.xlsx")
OUT_REPORT = os.path.join(BASE, "output", "q1_materialize_report_pos.json")

# 论文表 1 点名时段 → 时段索引 t（口径 R：附件标签为区间右端点）
TABLE1_NAMED = {
    "10:00-10:10": 60,
    "12:00-12:10": 72,
    "14:00-14:10": 84,
    "16:00-16:10": 96,
    "18:00-18:10": 108,
    "20:00-20:10": 120,
}


def main() -> int:
    ck = json.load(open(CHECKPOINT, encoding="utf-8"))
    G = ck["G"]
    if len(G) != 144:
        raise SystemExit(f"G 长度异常：{len(G)}")

    shutil.copyfile(TEMPLATE, OUT_XLSX)
    wb = openpyxl.load_workbook(OUT_XLSX)

    ws = wb["计划购电量"]
    labels_before = [ws.cell(r, 1).value for r in range(2, 146)]
    for i, v in enumerate(G):
        ws.cell(2 + i, 2).value = round(float(v), 8)
    labels_after = [ws.cell(r, 1).value for r in range(2, 146)]
    if labels_before != labels_after:
        raise SystemExit("模板标签被改动，违反红线")

    # 充放电量：6 个四小时块，口径无歧义，沿用 checkpoint 的 block_C / block_D
    ws2 = wb["充放电量"]
    block_C, block_D = ck["block_C"], ck["block_D"]
    for i in range(6):
        ws2.cell(2 + i, 2).value = round(float(block_C[i]), 8)
        ws2.cell(2 + i, 3).value = round(float(block_D[i]), 8)
    ws2.cell(2, 4).value = "0:00"
    ws2.cell(3, 4).value = "24:00"
    ws2.cell(2, 5).value = 6000
    ws2.cell(3, 5).value = 6000

    wb.save(OUT_XLSX)

    # 回读校验
    rb = openpyxl.load_workbook(OUT_XLSX)
    ws_rb = rb["计划购电量"]
    read = [ws_rb.cell(r, 2).value for r in range(2, 146)]
    errs: List[str] = []
    for i in range(144):
        if abs(float(read[i]) - round(float(G[i]), 8)) > 1e-9:
            errs.append(f"row {2+i}: 回读 {read[i]} != G[{i}] {G[i]}")
    if abs(sum(read) - ck["Q_G"]) > 1e-5:
        errs.append(f"全天购电量合计 {sum(read)} != Q_G {ck['Q_G']}")
    cost = float(sum(p * g for p, g in zip(ck_price(ck), read)))
    # 注意：表 1 的购电费以 checkpoint 的全精度为准，此处仅做量级校验
    if abs(cost - ck["J_actual"]) > 1e-3:
        errs.append(f"按行重算购电费 {cost} != J_actual {ck['J_actual']}")

    table1 = {name: float(G[t]) for name, t in TABLE1_NAMED.items()}
    report = {
        "task": "materialize_result1_positional",
        "mapping": "B[r+2] = G[r]  (r=0..143)；第2行=[0:00,0:10)，第145行=[23:50,24:00)",
        "template": TEMPLATE,
        "out_xlsx": OUT_XLSX,
        "labels_unchanged": labels_before == labels_after,
        "rows_written": 144,
        "first_row_value_G0": read[0],
        "last_row_value_G143": read[-1],
        "daily_purchase_kWh": float(sum(read)),
        "daily_cost_yuan": ck["J_actual"],
        "table1_named_intervals": table1,
        "errors": errs,
        "note": (
            "位置对齐口径；全天购电量/购电费为聚合量，不受落位影响，"
            "仍以 q1_checkpoint.json 全精度为准。"
        ),
    }
    with open(OUT_REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("out:", OUT_XLSX)
    print("labels_unchanged =", report["labels_unchanged"])
    print("R2   <- G[0]   =", read[0])
    print("R3   <- G[1]   =", read[1])
    print("R145 <- G[143] =", read[-1])
    print("table1 六时段:", table1)
    print("errors =", errs if errs else "[]")
    return 0 if not errs else 1


def ck_price(ck: Dict) -> List[float]:
    """从 q1_clean.csv 读当日电价（与 checkpoint 同源）。"""
    import csv

    path = r"D:\CMUCU\B对话\clean\q1_clean.csv"
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    return [float(r["price_元_kWh"]) for r in rows]


if __name__ == "__main__":
    raise SystemExit(main())
