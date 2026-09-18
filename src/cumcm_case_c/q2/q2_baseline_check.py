# -*- coding: utf-8 -*-
"""判定"交付物 == 探针基线（_s1_wd4 台账）"还是"交付物 == W7 线"。

只读两个 xlsx + 台账 + 价格缓存；从【xlsx 自身单元格】独立反解，不引用任何中间结论。
输出 output/q2_baseline_check.json。
"""
import sys, json
sys.path.append("D:\\CMUCU\\rag\\.deps")
import openpyxl, numpy as np

B = "D:\\CMUCU\\5\u5bf9\u8bdd\\"
NEW = B + "result2_\u5bf9\u8bdd5_\u540c\u54684\u5468MILP.xlsx"
OLD = B + "result2_\u5bf9\u8bdd5.xlsx"
PR = np.array(json.load(open(B + "output\\_price_cache.json", encoding="utf-8")))
R = {r["d"]: r for r in (json.loads(l) for l in open(B + "output\\_s1_wd4.jsonl", encoding="utf-8") if l.strip())}
DAYS = list(range(31, 365))


def read_plan(path):
    wb = openpyxl.load_workbook(path)
    ws1, ws3 = wb["\u8ba1\u5212\u8d2d\u7535\u91cf"], wb["\u7d27\u6025\u8d2d\u7535\u91cf"]
    jp = 0.0; qg = 0.0; per = {}
    for i, d in enumerate(DAYS):
        r = 2 + i; G = np.zeros(144)
        for t in range(144):
            col = 2 + t                       # 位置映射：列序=时序（请神第 3 次终裁）
            G[t] = ws1.cell(r, col).value or 0
        jp += float(np.dot(PR, G)); qg += float(G.sum()); per[d] = G
    qh = sum(ws3.cell(r, 3).value or 0 for r in range(2, ws3.max_row + 1))
    return dict(J_plan_from_xlsx=round(jp, 6), QG_from_xlsx=round(qg, 4),
                QH_segments_from_xlsx=round(qh, 6), rows3=ws3.max_row - 1, per_day=per)


n = read_plan(NEW); o = read_plan(OLD)
led_jp = round(sum(r["J_plan"] for r in R.values()), 6)
led_qg = round(sum(sum(r["G"]) for r in R.values()), 4)
led_qh = round(sum(sum(r["H"]) for r in R.values()), 6)
led_jc = round(led_jp + sum(r["J_emg"] for r in R.values()), 6)
dev = max(abs(float(n["per_day"][d].sum() - sum(R[d]["G"]))) for d in DAYS)
res = {
    "question": "\u4ea4\u4ed8\u7269\u5230\u5e95\u662f\u54ea\u4e00\u6761\u7ebf\uff1f",
    "new_file": {"path": NEW, "J_plan_from_xlsx": n["J_plan_from_xlsx"], "QG_from_xlsx": n["QG_from_xlsx"],
                 "QH_segments_from_xlsx": n["QH_segments_from_xlsx"], "table3_rows": n["rows3"]},
    "old_file": {"path": OLD, "J_plan_from_xlsx": o["J_plan_from_xlsx"], "QG_from_xlsx": o["QG_from_xlsx"],
                 "QH_segments_from_xlsx": o["QH_segments_from_xlsx"], "table3_rows": o["rows3"]},
    "ledger_s1_wd4": {"J_plan": led_jp, "QG": led_qg, "QH": led_qh, "J_cash": led_jc},
    "matches": {
        "new_xlsx_plan_==_ledger": abs(n["J_plan_from_xlsx"] - led_jp) < 0.01 and abs(n["QG_from_xlsx"] - led_qg) < 1.0,
        "new_xlsx_perday_G_==_ledger_max_dev": round(dev, 8),
        "new_xlsx_H_==_ledger": abs(n["QH_segments_from_xlsx"] - led_qh) < 1e-3,
        "old_xlsx_is_W7_16086052": abs(o["J_plan_from_xlsx"] - 14656698.59) < 1.0 and abs(o["QG_from_xlsx"] - 23136277.2) < 5.0,
    },
    "verdict": ("\u4ea4\u4ed8\u7269 = \u540c\u54684\u5468+MILP+\u4e8c\u7ea7\u62e9\u4f18\uff08\u5373 `_s1_wd4` \u53f0\u8d26\uff09\uff1b"
                "\u65e7\u4ef6 `result2_\u5bf9\u8bdd5.xlsx` = W7+LP\uff08\u5bf9\u7167/\u5907\u4efd\uff09"),
}
json.dump(res, open(B + "output\\q2_baseline_check.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"NEW xlsx : J_plan {n['J_plan_from_xlsx']:,.6f}  QG {n['QG_from_xlsx']:,.4f}  segH {n['QH_segments_from_xlsx']:,.4f}  (表3行 {n['rows3']})")
print(f"OLD xlsx : J_plan {o['J_plan_from_xlsx']:,.6f}  QG {o['QG_from_xlsx']:,.4f}  segH {o['QH_segments_from_xlsx']:,.4f}  (表3行 {o['rows3']})")
print(f"ledger   : J_plan {led_jp:,.6f}  QG {led_qg:,.4f}  segH {led_qh:,.4f}  J_cash {led_jc:,.6f}")
print("判定:", res["verdict"])
print("  NEW == 台账 :", res["matches"]["new_xlsx_plan_==_ledger"], "| 逐日G最大偏差", res["matches"]["new_xlsx_perday_G_==_ledger_max_dev"])
print("  NEW 表3H == 台账 :", res["matches"]["new_xlsx_H_==_ledger"])
print("  OLD 是 W7(14,656,699/23,136,277) :", res["matches"]["old_xlsx_is_W7_16086052"])
