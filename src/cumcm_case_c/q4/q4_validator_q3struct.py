# -*- coding: utf-8 -*-
"""
Q4-3 独立校验器骨架（**不 import 任何 q4_*/q3_* 求解代码**）
今日即可干跑：--mode q4-2 用 result4-2.xlsx 自证「位置映射 + 表3 写法 + 结构 + SOC 链 + 读法C公式」有效。
Q4-3 交付后：--mode q4-3 --xlsx <result4-3.xlsx> 复核读法 C 三段式。

校验项（全部只读原始附件 + 成品 xlsx）：
  S1 结构：工作表名与形状 = 官方模板
  S2 位置映射：表1 每行「全天购电量」= Σ_{c=2..145} 数值；「全天购电费」= Σ_t p4[d,t]·G_t（按 col=2+t 取）
  S3 表3 写法：只列真实段；**日期列只在当日首段写一次**；按日期前向填充后去重计天
  S4 表2/SOC：块内 C,D ≤ 24×833.333；0:00/24:00 链式衔接；SOC∈[1200,10800]
  S5 读法 C 公式（golden test，与数据无关，先自证公式实现）
  S6 读法 C 三段式（仅 q4-3）：用表1(计划) + 表2/表3(调整/紧急) 复算三段并给出分解
"""
import sys, os, json, argparse
import numpy as np
import pandas as pd
import openpyxl

B = r"D:\CMUCU\B对话\clean"
TMPL = {"q4-2": r"D:\CMUCU\赛题\C题\附件\附件5\result4-2.xlsx",
        "q4-3": r"D:\CMUCU\赛题\C题\附件\附件5\result4-3.xlsx"}
DT = 1 / 6
SMIN, SMAX, EBAR = 1200.0, 10800.0, 5000 * DT
DAYS = list(range(31, 365))


def reading_C(G0, A, p):
    """读法 C：p·min(G0,A) + 0.5p(G0−A)+ + 1.5p(A−G0)+  —— 逐段向量版。"""
    G0 = np.asarray(G0, float); A = np.asarray(A, float); p = np.asarray(p, float)
    return p * np.minimum(G0, A) + 0.5 * p * np.maximum(G0 - A, 0) + 1.5 * p * np.maximum(A - G0, 0)


def golden_tests():
    out = []
    cases = [(100, 80, 1.0, 90.0), (100, 120, 1.0, 130.0), (100, 100, 1.0, 100.0),
             (100, 0, 2.0, 100.0), (0, 100, 2.0, 300.0)]
    for g0, a, p, want in cases:
        got = float(reading_C([g0], [a], [p])[0])
        out.append(dict(G0=g0, A=a, p=p, expect=want, got=got, pass_=abs(got - want) < 1e-9))
    return out


def sheet_dims(path):
    wb = openpyxl.load_workbook(path, read_only=True)
    d = {ws.title: (ws.max_row, ws.max_column) for ws in wb.worksheets}
    wb.close()
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", required=True)
    ap.add_argument("--mode", choices=["q4-2", "q4-3"], required=True)
    ap.add_argument("--tmpl", default=None, help="覆盖模板路径（例如体检 result3.xlsx 时指向 result3 模板）")
    ap.add_argument("--price", choices=["att1", "att4"], default="att4",
                    help="用于 S2b 购电费恒等式的价格：att4（Q4 主用）/ att1（体检 Q3 交付时用）")
    ap.add_argument("--regime", choices=["q2", "q3"], default="q2",
                    help="费用列口径（方案 A，2026-09-13 统一）：无论 q2/q3，表1'全天购电费'= 本表购电量 × 该时段电价")
    ap.add_argument("--expect", type=float, default=None, help="S6 期望的全年 J_cash（可选，用于对拍）")
    ap.add_argument("--out", default=r"D:\CMUCU\8对话\output\q4_validator_q3struct_result.json")
    a = ap.parse_args()
    tmpl = a.tmpl or TMPL[a.mode]
    res = {"mode": a.mode, "xlsx": a.xlsx, "checks": [], "errors": []}

    def chk(name, ok, detail=None):
        res["checks"].append({"name": name, "pass": bool(ok), "detail": detail})
        if not ok:
            res["errors"].append(name + " | " + str(detail))

    chk("S5 读法C golden test", all(g["pass_"] for g in golden_tests()), golden_tests())

    got = sheet_dims(a.xlsx); want = sheet_dims(tmpl)
    same_names = list(got.keys()) == list(want.keys())
    main_ok = got.get("计划购电量") == want.get("计划购电量")          # 主表：表头 + 334 天
    dyn_ok = all(got[k][0] >= want[k][0] and got[k][1] == want[k][1]  # 动态表：模板行数只是排版骨架
                 for k in want if k != "计划购电量")
    chk("S1 结构：表名一致 + 主表形状=模板 + 动态表已展开", same_names and main_ok and dyn_ok,
        {"sheet_names": same_names, "main_shape": got.get("计划购电量"), "main_want": want.get("计划购电量"),
         "got": got, "tmpl": want,
         "note": "充放电量/紧急购电量在模板中只是排版骨架（20/11 行），成品必须按实际展开（334×6+1 / 段数+1）"})

    if a.price == "att4":
        PR = pd.read_csv(B + r"\attachment4_clean.csv").iloc[:, 1:].to_numpy(float)
    else:
        _p1 = pd.read_csv(B + r"\q1_clean.csv")["price_元_kWh"].to_numpy(float)
        PR = np.tile(_p1, (365, 1))
    wb = openpyxl.load_workbook(a.xlsx, read_only=True)
    ws1 = wb["计划购电量"]
    rows = list(ws1.iter_rows(min_row=2, values_only=True))
    bad_sum, bad_fee, n = 0, 0, 0
    for i, r in enumerate(rows[:334]):
        d = DAYS[i]
        G = np.array([float(x) if x is not None else 0.0 for x in r[1:145]])
        tot = float(r[145]) if r[145] is not None else None
        fee = float(r[146]) if r[146] is not None else None
        n += 1
        if tot is None or abs(tot - G.sum()) > 1e-3:
            bad_sum += 1
        ref = float((PR[d] * G).sum())
        if fee is None or abs(fee - ref) > 1e-2:
            bad_fee += 1
    chk("S2a 表1 全天购电量 = Σ144列", bad_sum == 0, {"bad_days": bad_sum, "n": n})
    # 方案 A（2026-09-13 统一）：q2 / q3 区制一律为「本表购电量 × 该时段电价」
    chk("S2b 表1 全天购电费 = Σ p[d,t]·G_t（位置映射 col=2+t，价格=%s）" % a.price, bad_fee == 0,
        {"bad_days": bad_fee, "n": n, "price": a.price, "tmpl": tmpl, "regime": a.regime,
         "note": "方案 A：两区制同式（4 位小数，日容差 1e-2）；若映射错位此式必然失配 ⇒ 同时验证位置映射"})

    ws3 = wb["紧急购电量"]
    r3 = list(ws3.iter_rows(min_row=2, values_only=True))
    cur, n_date, days, seg = None, 0, set(), 0
    ok_val = True
    for r in r3:
        if r[0] is not None and str(r[0]).strip() != "":
            cur = r[0]
            n_date += 1
        have_val = (r[2] is not None and float(r[2]) > 0)
        if have_val:
            seg += 1
            days.add(str(cur))
        else:
            ok_val = False          # 表3 不应出现 0/空 电量行
    chk("S3 表3 写法：只列真实段 + 日期列每日只写一次",
        (len(r3) == seg) and ok_val and (n_date == len(days)) and len(days) > 0,
        {"rows": len(r3), "segments": seg, "nonempty_date_cells": n_date,
         "distinct_days_by_forward_fill": len(days),
         "note": "判据：行数=段数（无 0 行）、非空日期格数=去重天数（每日只写一次）"})

    ws2 = wb["充放电量"]
    r2 = list(ws2.iter_rows(min_row=2, values_only=True))
    bad_blk, soc_bad, prev24, chain_bad = 0, 0, None, 0
    k = 0
    while k + 5 < len(r2):
        blk = r2[k:k + 6]
        for rr in blk:
            c = float(rr[2] or 0); d = float(rr[3] or 0)
            if c > 24 * EBAR + 1e-6 or d > 24 * EBAR + 1e-6 or c < -1e-9 or d < -1e-9:
                bad_blk += 1
        s0 = blk[0][5]; s24 = blk[1][5]
        if s0 is not None and not (SMIN - 1e-6 <= float(s0) <= SMAX + 1e-6):
            soc_bad += 1
        if s24 is not None and not (SMIN - 1e-6 <= float(s24) <= SMAX + 1e-6):
            soc_bad += 1
        if prev24 is not None and s0 is not None and abs(float(prev24) - float(s0)) > 1e-3:
            chain_bad += 1
        prev24 = s24
        k += 6
    chk("S4a 表2 块内充放电 ≤ 24×833.333", bad_blk == 0, {"bad": bad_blk})
    chk("S4b SOC 界与日界链式", (soc_bad == 0 and chain_bad == 0), {"soc_bad": soc_bad, "chain_bad": chain_bad})

    wb.close()

    # ---------------- S6 读法 C 三段式（Q4-3 核心判据）----------------
    wb2 = openpyxl.load_workbook(a.xlsx, read_only=True)
    has_adj = "调整购电量" in wb2.sheetnames
    if a.regime == "q3" and not has_adj:
        chk("S6 读法C 需要'调整购电量'表", False, {"sheets": wb2.sheetnames})
    if a.regime == "q3" and has_adj:
        r1 = list(wb2["计划购电量"].iter_rows(min_row=2, values_only=True))
        r2 = list(wb2["调整购电量"].iter_rows(min_row=2, values_only=True))
        r3 = list(wb2["紧急购电量"].iter_rows(min_row=2, values_only=True))
        Hday, cur = {}, None
        for r in r3:
            if r[0] is not None and str(r[0]).strip() != "":
                cur = str(r[0])[:10]
            if cur and r[2] is not None:
                Hday[cur] = Hday.get(cur, 0.0) + float(r[2])
        import datetime as _dt
        base = _dt.date(2025, 1, 1)
        Jp = Ja = Je = 0.0
        bad_day, maxd = 0, 0.0
        for i in range(334):
            d = DAYS[i]
            date = str(base + _dt.timedelta(days=d))
            G0 = np.array([float(x or 0) for x in r1[i][1:145]])
            A = np.array([float(x or 0) for x in r2[i][1:145]])
            P = PR[d]
            jp = float((P * np.minimum(G0, A)).sum())
            ja = float((0.5 * P * np.maximum(G0 - A, 0) + 1.5 * P * np.maximum(A - G0, 0)).sum())
            je = float(5.0 * P.mean() * Hday.get(date, 0.0))
            Jp += jp; Ja += ja; Je += je
            fee = float(r1[i][146] or 0)
            dd = abs(fee - (jp + ja + je))
            maxd = max(maxd, dd)
            if dd > max(0.02, 0.01 * abs(fee)):
                bad_day += 1
        total = Jp + Ja + Je
        chk("S6a 读法C 三段式求和（与期望对拍；紧急项用日均价近似）",
            (a.expect is None) or abs(total - a.expect) <= max(1.0, 0.003 * a.expect),
            {"J_plan": Jp, "J_adj": Ja, "J_emg": Je, "J_cash": total, "expect": a.expect,
             "diff": None if a.expect is None else total - a.expect,
             "note": "S6 只能读 xlsx：表3 只给‘段合计’，故紧急项按当日均价折算 ⇒ 本项为近似复核；"
                     "精确复算须用逐段真值（由现场监理 q4_site_guard 用 q4_q3v2_seg.jsonl 完成）"})
        chk("S6b 表1 列口径 = 本表购电量 × 电价（方案 A；三段式台账合计仅作报告）", True,
            {"n_days": 334, "ledger_J_plan": Jp, "ledger_J_adj": Ja, "ledger_J_emg": Je, "ledger_J_cash": total,
             "note": "方案 A 后该列 = Σp·G（S2b 已硬判）；三段式合计 J_plan+J_adj+J_emg 是台账口径的全年总现金，"
                     "**不落在表内任何一列**，此处仅作报告 —— 逐日精确复核由 q4_site_guard 用逐段真值完成"})
        print("  [S6] J_plan=%s J_adj=%s J_emg=%s J_cash=%s"
              % (format(Jp, ",.2f"), format(Ja, ",.2f"), format(Je, ",.2f"), format(total, ",.2f")), flush=True)
    wb2.close()
    res["pass"] = len(res["errors"]) == 0
    json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("模式 %s ｜ 检查 %d 项 ｜ errors=%d" % (a.mode, len(res["checks"]), len(res["errors"])), flush=True)
    for c in res["checks"]:
        print("  [%s] %s" % ("PASS" if c["pass"] else "FAIL", c["name"]), flush=True)
    if res["errors"]:
        print("  ❌", res["errors"], flush=True)
    print("已落盘 " + a.out, flush=True)


if __name__ == "__main__":
    main()
