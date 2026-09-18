# -*- coding: utf-8 -*-
"""Q4-3 的两项收口证据（只读 import；只写 8对话\output）
 A) 2×2 反事实：计划来源（附件1 价 / 附件4 价）× 结算价格（附件1 / 附件4）
    —— 在**逐段真值**层面重结算，不需要改动他人代码。
 B) "价格不可预知"臂：计划用**上周同日价格**（p4[d-7]）生成，再用**附件4** 结算。
输出：q4_q43_2x2.json / q4_q43_pricearm.json
"""
import sys, os, json, time
import numpy as np
import pandas as pd

sys.path.append("D:\\CMUCU\\rag\\.deps")
sys.path.insert(0, r"D:\CMUCU\7.5对话\code")
sys.path.insert(0, r"D:\CMUCU\7.6对话\code")
import q3_exec_v2b as X
import q76_v2b_full as V
from q3_data_io import LAM_T, S0, load_prices  # noqa

OUT = r"D:\CMUCU\8对话\output"
P4 = pd.read_csv(r"D:\CMUCU\B对话\clean\attachment4_clean.csv").iloc[:, 1:].to_numpy(float)
PR1 = load_prices()                      # 附件1 的 144 段典型日曲线
L, P, price, fc, days = V.load_data()
D0, D1 = 31, 364
EPOCHS = (0, 6, 12, 18)


def run(price_of_day, tag):
    """按给定逐日价格跑 v2b 管线，回收逐段 G0/A/H。"""
    s = float(S0)
    rec = []
    t0 = time.time()
    for d in range(D0, D1 + 1):
        r = X.run_day(L, P, price_of_day(d), fc, days, d, X.EXECUTORS["v2b"], billing="C",
                      demand="quantile_v3", q=0.8, q_block="segment", margin=0.0,
                      s_init=s, epochs=EPOCHS, lam=LAM_T, convention="slot_end")
        if not r.get("ok"):
            raise RuntimeError("d=%d fail %s" % (d, r.get("reason")))
        rec.append((d, np.asarray(r["G0"], float), np.asarray(r["A"], float), np.asarray(r["H"], float)))
        s = float(r["S_end"])
    print("  %-26s 完成（%.0fs）" % (tag, time.time() - t0), flush=True)
    return rec


def settle(rec, price_of_day):
    jp = ja = je = 0.0
    for d, G0, A, H in rec:
        p = price_of_day(d)
        jp += float((p * np.minimum(G0, A)).sum())
        ja += float((0.5 * p * np.maximum(G0 - A, 0) + 1.5 * p * np.maximum(A - G0, 0)).sum())
        je += float((5.0 * p * H).sum())
    return dict(J_plan=jp, J_adj=ja, J_emg=je, J_cash=jp + ja + je)


p1 = lambda d: PR1
p4 = lambda d: P4[d]
pl7 = lambda d: P4[d - 7]

print("=== 三套计划（v2b、q=0.8、m=0）===", flush=True)
rec1 = run(p1, "计划@附件1价（=Q3 v2）")
rec4 = run(p4, "计划@附件4价（=Q4-3 主线）")
recL = run(pl7, "计划@上周同日价")

c11, c14 = settle(rec1, p1), settle(rec1, p4)
c41, c44 = settle(rec4, p1), settle(rec4, p4)
cL4 = settle(recL, p4)

print("", flush=True)
print("=== A) 2×2 反事实（逐段真值重结算）===", flush=True)
print("| 计划来源 | 结算价格 | J_plan | J_adj | J_emg | 总成本 |", flush=True)
for tag, c, sname in (("附件1 价下优化", c11, "附件1"), ("附件1 价下优化", c14, "附件4"),
                      ("附件4 价下优化", c41, "附件1"), ("附件4 价下优化", c44, "附件4")):
    print("| %s | %s | %s | %s | %s | **%s** |" % (tag, sname, format(c["J_plan"], ",.2f"),
          format(c["J_adj"], ",.2f"), format(c["J_emg"], ",.2f"), format(c["J_cash"], ",.2f")), flush=True)
print("  ①价格环境效应 = %s 元" % format(c14["J_cash"] - c11["J_cash"], ",.2f"), flush=True)
print("  ②重优化效应   = %s 元" % format(c44["J_cash"] - c14["J_cash"], ",.2f"), flush=True)
print("  ①+② = %s 元（= Q4-3 相对 Q3 v2 的差）" % format(c44["J_cash"] - c11["J_cash"], ",.2f"), flush=True)

print("", flush=True)
print("=== B) 价格不可预知臂（计划用上周同日价，结算用附件4）===", flush=True)
print("  已知价（主线） %s 元" % format(c44["J_cash"], ",.2f"), flush=True)
print("  上周同日价     %s 元  (%s%%)" % (format(cL4["J_cash"], ",.2f"),
       format(100 * (cL4["J_cash"] - c44["J_cash"]) / c44["J_cash"], "+.3f")), flush=True)

json.dump({"cells": {"plan1_settle1": c11, "plan1_settle4": c14, "plan4_settle1": c41, "plan4_settle4": c44},
           "price_effect": c14["J_cash"] - c11["J_cash"],
           "reopt_effect": c44["J_cash"] - c14["J_cash"],
           "price_unaware": {"lag7_settle4": cL4,
                             "delta_pct_vs_known": 100 * (cL4["J_cash"] - c44["J_cash"]) / c44["J_cash"]}},
          open(os.path.join(OUT, "q4_q43_2x2.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("已落盘 q4_q43_2x2.json", flush=True)
