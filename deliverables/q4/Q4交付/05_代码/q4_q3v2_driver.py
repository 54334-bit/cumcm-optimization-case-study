# -*- coding: utf-8 -*-
"""
Q4-3 驱动（**按 Q3 v2 整体重跑，只换价格**）
  · 只读 import 7.5/7.6 的 v2 管线（q76_v2b_full / q3_exec_v2b / q3_data_io ...），不复制、不改写他人目录
  · 唯一改动：把逐日价格由"附件1 常数向量"换成"附件4 的当日 144 段向量"
  · 闸门：不换价先跑一遍 v2b，必须复现 13,120,194.06（Q3 v2 交付）
用法：
  python q4_q3v2_driver.py --gate        # 只跑闸门
  python q4_q3v2_driver.py --run         # 跑 Q4-3（附件4）并落盘证据
"""
import sys, os, json, argparse, time
import numpy as np
import pandas as pd

sys.path.append("D:\\CMUCU\\rag\\.deps")
sys.path.insert(0, r"D:\CMUCU\7.6对话\code")
import q76_v2b_full as V

OUT = r"D:\CMUCU\8对话\output"
os.makedirs(OUT, exist_ok=True)
P4 = pd.read_csv(r"D:\CMUCU\B对话\clean\attachment4_clean.csv").iloc[:, 1:].to_numpy(float)


def gate(v):
    L, P, price, fc, days = V.load_data()
    t0 = time.time()
    r = V.run_arm("v2b", L, P, price, fc, days)
    tot = r["totals"]["J_cash"] if "totals" in r else None
    exp = 13120194.06
    d = None if tot is None else tot - exp
    print("[闸门] v2b + 附件1 价：J_cash = %s（期望 %s，差 %s）耗时 %.0fs"
          % (format(tot, ",.2f") if tot else "None", format(exp, ",.2f"),
             format(d, "+.2f") if d is not None else "n/a", time.time() - t0), flush=True)
    for k in ("J_plan", "J_adj", "J_emg", "QH", "QG0"):
        if "totals" in r and k in r["totals"]:
            print("        %-8s %s" % (k, format(r["totals"][k], ",.4f")), flush=True)
    json.dump({"gate": "v2b+att1", "J_cash": tot, "expected": exp, "diff": d,
               "totals": r.get("totals"), "s_end": r.get("S_end")},
              open(os.path.join(OUT, "q4_q3v2_gate.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    return r


def run_q43():
    L, P, price, fc, days = V.load_data()
    orig = V._one_day

    def patched(arm, L_, P_, price_, fc_, days_, d, s):
        return orig(arm, L_, P_, P4[d], fc_, days_, d, s)

    V._one_day = patched
    t0 = time.time()
    r = V.run_arm("v2b", L, P, price, fc, days)
    V._one_day = orig
    print("[Q4-3] v2b + 附件4 价：J_cash = %s  耗时 %.0fs"
          % (format(r["totals"]["J_cash"], ",.2f"), time.time() - t0), flush=True)
    for k in ("J_plan", "J_adj", "J_emg", "QH", "QG0", "QA"):
        if k in r["totals"]:
            print("        %-8s %s" % (k, format(r["totals"][k], ",.4f")), flush=True)
    seg_path = os.path.join(OUT, "q4_q3v2_seg.jsonl")
    V.write_seg_jsonl(seg_path, r["seg"])
    sol_path = os.path.join(OUT, "q4_q3v2_solution.json")
    json.dump({"arm": "v2b", "price": "attachment4", "totals": r["totals"],
               "S_first": r.get("S_first"), "S_end": r.get("S_end"),
               "rows": r["rows"]}, open(sol_path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    return r, seg_path, sol_path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--mat", action="store_true")
    a = ap.parse_args()
    if a.gate:
        gate(None)
    if a.run:
        r, sp, sl = run_q43()
        print("已落盘 %s / %s" % (sp, sl), flush=True)
    if a.mat:
        sp = os.path.join(OUT, "q4_q3v2_seg.jsonl")
        sl = os.path.join(OUT, "q4_q3v2_solution.json")
        out_xlsx = os.path.join(OUT, "result4-3.xlsx")
        # ⚠️ 保护：他们的 materialize() 会把报告写回 7.6 自己的目录（MAT_REPORT）。
        # 先备份、调用后恢复，确保**不污染他人证据**（2026-09-13 01:16 曾因此覆盖一次，已恢复）。
        guard = V.MAT_REPORT
        bak = None
        if os.path.exists(guard):
            bak = open(guard, "rb").read()
        rep = V.materialize(sp, sl, out_xlsx)
        if bak is not None:
            open(guard, "wb").write(bak)
            print("[保护] 已恢复他人证据文件 %s" % guard, flush=True)
        print("[物化] -> %s" % out_xlsx, flush=True)
        print(json.dumps(rep, ensure_ascii=False, indent=1)[:1200], flush=True)
