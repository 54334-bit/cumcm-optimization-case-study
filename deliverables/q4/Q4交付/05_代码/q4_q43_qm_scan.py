# -*- coding: utf-8 -*-
"""Q4-3 计划层标定 (q,m) 在**附件4 波动价**下的复核（只读 import；只写 8对话\output）
问题：Q3 v2 的标定点 (q=0.8, m=0) 是在**附件1 固定价**下定出来的；
      而 Q4-3 的代价结构不同（价格波动 + 调整罚则），最优点未必相同。
做法：在同一 v2 管线上，把逐日价格换成附件4，扫 (q,m) 的小网格：
      q ∈ {0.5, 0.8, 0.95}、m ∈ {0.0, 0.04}，各跑全年 334 天。
预注册止损：相对 (0.8,0) 降幅 ≤0.5% 即维持标定点、不做优化。
"""
import sys, os, json, time
import numpy as np
import pandas as pd

sys.path.append("D:\\CMUCU\\rag\\.deps")
sys.path.insert(0, r"D:\CMUCU\7.6对话\code")
import q76_v2b_full as V
import q3_exec_v2b as X
from q3_data_io import ETA, LAM_T, S0, load_forecast, load_load_pv, load_prices  # noqa

OUT = r"D:\CMUCU\8对话\output"
P4 = pd.read_csv(r"D:\CMUCU\B对话\clean\attachment4_clean.csv").iloc[:, 1:].to_numpy(float)
L, P, price, fc, days = V.load_data()
D0, D1 = 31, 364
EPOCHS = (0, 6, 12, 18)


def run_variant(q, margin, tag):
    s = float(S0)
    tot = {"J_plan": 0.0, "J_adj": 0.0, "J_emg": 0.0, "J_cash": 0.0, "QH": 0.0, "QG0": 0.0}
    t0 = time.time()
    for d in range(D0, D1 + 1):
        r = X.run_day(L, P, P4[d], fc, days, d, X.EXECUTORS["v2b"], billing="C",
                      demand="quantile_v3", q=q, q_block="segment",
                      margin=margin, s_init=s, epochs=EPOCHS, lam=LAM_T, convention="slot_end")
        if not r.get("ok"):
            print("  %-22s d=%d FAIL %s" % (tag, d, r.get("reason")), flush=True)
            return None
        for k in tot:
            tot[k] += float(r.get(k, 0.0) or 0.0)
        s = float(r["S_end"])
    print("  %-24s J_cash %s | 计划 %s | 调整 %s | 紧急 %s | SigmaH %s | %.0fs"
          % (tag, format(tot["J_cash"], ",.2f"), format(tot["J_plan"], ",.2f"),
             format(tot["J_adj"], ",.2f"), format(tot["J_emg"], ",.2f"),
             format(tot["QH"], ",.1f"), time.time() - t0), flush=True)
    return tot


print("=== Q4-3 (附件4 价) 计划层 (q,m) 复核 ===", flush=True)
res = {}
for q, m in ((0.8, 0.0), (0.5, 0.0), (0.95, 0.0), (0.8, 0.04)):
    key = "q%.2f_m%.2f" % (q, m)
    res[key] = run_variant(q, m, "q=%.2f m=%.2f" % (q, m))

base = res["q0.80_m0.00"]["J_cash"] if res["q0.80_m0.00"] else None
print("", flush=True)
print("=== 相对标定点 (q=0.8, m=0) 的差异（止损：≤0.5% 即不做优化）===", flush=True)
for k, v in res.items():
    if v and base:
        print("  %-14s %s 元  (%s%%)" % (k, format(v["J_cash"], ",.2f"),
              format(100 * (v["J_cash"] - base) / base, "+.3f")), flush=True)
json.dump(res, open(os.path.join(OUT, "q4_q43_qm_scan.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("已落盘 q4_q43_qm_scan.json", flush=True)
