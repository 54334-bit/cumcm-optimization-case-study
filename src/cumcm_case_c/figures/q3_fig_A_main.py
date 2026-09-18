# -*- coding: utf-8 -*-
r"""Q3 Tier A 主结果图（对话6 · v2 交付口径：读法 C + 执行器 v2b）。

数据入口：`q3_data_frozen.py`（提交件按单元格值 + 逐段真值 v2b + 附件1 电价）。
q3_01_day_rollout_chain：指定日四时点滚动全景（计划 G⁰ → 6/12/18 调整 A → 紧急 H → SOC）。

用法：$env:PYTHONPATH="D:\CMUCU\rag\.deps"; $env:PYTHONIOENCODING='utf-8'
      & $py "D:\CMUCU\6对话\code\q3_fig_A_main.py" [--only q3_01]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, r"D:\CMUCU\4对话\code")

import mpl_config as MC          # noqa: E402
import q3_data_frozen as Q       # noqa: E402
from fig_manifest import Manifest  # noqa: E402

FIG_DIR = Path(r"D:\CMUCU\6对话\output\figures\q3")
T, DT = Q.T, Q.DT
UPDATES = (6, 12, 18)


def _load():
    import data_io as D          # 4对话 共享数据层（附件2 负载/光伏）
    sub = Q.load_submission(verbose=False)
    seg = Q.load_seg(Q.SEG_V2B, verbose=False)
    price = Q.load_prices(verbose=False)
    _, load_y = D.load_year_load()
    _, pv_y = D.load_year_pv()
    load = np.asarray(load_y, float)[31:365]
    pv = np.asarray(pv_y, float)[31:365]
    assert load.shape == (Q.N_DAYS, T) and pv.shape == (Q.N_DAYS, T)
    return sub, seg, price, load, pv


def _haxis(ax, *, label: str = "", step: int = 2):
    ax.set_xlim(0, 24)
    ax.set_xticks(list(range(0, 25, step)))
    ax.set_xticklabels(["%d:00" % h for h in range(0, 25, step)], fontsize=7)
    if label:
        ax.set_xlabel(label, fontsize=8.5)


# ---------------------------------------------------------------------------
def fig_q3_01(sub, seg, price, load, pv, *, day: str = "2025-12-21") -> dict:
    i = seg["dates"].index(day)
    g0, a, h_, c, d_, s, rpv, rg = (seg["G0"][i], seg["A"][i], seg["H"][i],
                                    seg["C"][i], seg["D"][i], seg["S"][i],
                                    seg["R_PV"][i], seg["R_G"][i])
    L, P = load[i], pv[i]
    h = np.arange(T) * DT
    hm = h + DT / 2
    cs = Q.cash_split_C(g0[None, :], a[None, :], h_[None, :], price)
    diff = np.abs(a - g0) > 1e-9

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(7.4, 6.2), sharex=True,
                                   gridspec_kw={"height_ratios": [1.15, 1.0], "hspace": 0.16})
    # H 的当日量级可能只有几十 kWh，直接画在 kW 轴上不可见 → 按倍数放大显示，并在图例注明倍数
    hmax_kw = float((h_ / DT).max()) if h_.max() > 0 else 0.0
    ymax_hint = float(max(L.max(), P.max(), (a / DT).max(), hmax_kw)) * 1.32
    factor = 1.0
    if hmax_kw > 0:
        for cand in (1, 2, 5, 10, 20, 50):
            if hmax_kw * cand >= 0.10 * ymax_hint:
                factor = float(cand)
                break
    ax1.bar(hm, a / DT, width=DT * 0.92, color=MC.PALETTE["grid"], alpha=0.45,
            label="调整后购电 $A$（实际取用，kW 等效）")
    ax1.bar(hm, h_ / DT * factor, width=DT * 0.92, color=MC.PALETTE["emer"], alpha=0.95,
            hatch="///", edgecolor="white", lw=0.2,
            label="紧急购电 $H$" + ("（×%g 放大显示）" % factor if factor > 1 else ""))
    ax1.plot(hm, L, "-", color=MC.PALETTE["load"], lw=1.5, label="小区负载 $L$")
    ax1.plot(hm, P, "--", color=MC.PALETTE["pv"], lw=1.4, label="光伏出力 $PV$")
    ax1.fill_between(hm, 0, P, color=MC.PALETTE["pv"], alpha=0.12)
    for hh in UPDATES:
        ax1.axvline(hh, color=MC.PALETTE["baseline"], lw=0.8, ls=":", alpha=0.8)
    for hh, lab in zip(UPDATES, ("6:00 更新", "12:00 更新", "18:00 更新")):
        ax1.text(hh + 0.12, ax1.get_ylim()[1] * 0.97, lab, fontsize=5.8, va="top",
                 color=MC.PALETTE["baseline"])
    ax1.set_ylabel("功率 (kW)", fontsize=8.5)
    ax1.set_title("(a) %s 供需与购电：调整后购电 $A$（柱）+ 紧急购电 $H$（斜纹）" % day,
                  fontsize=9, loc="left", pad=16)
    # 图例移到坐标区**上方**（原先放在坐标区内会压住 0:00–4:00 的柱——本人 2026-09-13 目视发现）
    ax1.legend(loc="lower left", bbox_to_anchor=(0.0, 1.005), fontsize=6.3, ncol=4,
               frameon=False, columnspacing=1.0, handlelength=1.4)
    ax1.set_ylim(0, ymax_hint)
    mc = MC.PALETTE["emer"]
    ax1.text(0.985, 0.965,
             "$\\Sigma G^0$=%.0f kWh（计划）\n$\\Sigma A$=%.0f（调整后，%d 段与计划不同）\n$\\Sigma H$=%.2f kWh（%s；柱为 ×%g）"
             % (g0.sum(), a.sum(), int(diff.sum()), h_.sum(),
                "有" if h_.sum() > 1e-9 else "无", factor),
             transform=ax1.transAxes, ha="right", va="top", fontsize=6.2, bbox=dict(
                 facecolor="white", edgecolor="none", alpha=0.86))

    ax2.bar(hm, -c / DT, width=DT * 0.92, color=MC.PALETTE["charge"], alpha=0.85,
            label="充电 $C$（向下）")
    ax2.bar(hm, d_ / DT, width=DT * 0.92, color=MC.PALETTE["discharge"], alpha=0.85,
            hatch="\\\\\\", edgecolor="white", lw=0.2, label="放电 $D$（向上）")
    ax2.axhline(0, color=MC.PALETTE["bound"], lw=0.8)
    lim = max(np.abs(c / DT).max(), (d_ / DT).max(), 1.0) * 1.9
    ax2.set_ylim(-lim, lim)
    ax2.set_ylabel("充放电功率 (kW)", fontsize=8.5)
    ax2.set_title("(b) 储能行为与 SOC（竖虚线 = 6/12/18 时更新点）", fontsize=9, loc="left")
    ax2.legend(loc="upper left", fontsize=6.3, ncol=2, framealpha=0.9)
    ax2b = ax2.twinx()
    ax2b.plot(np.arange(T + 1) * DT, s, "-", color=MC.PALETTE["soc"], lw=1.5, label="SOC（右轴）")
    ax2b.axhline(1200, color=MC.PALETTE["emer"], lw=0.9, ls="--")
    ax2b.axhline(10800, color=MC.PALETTE["grid"], lw=0.9, ls="--")
    ax2b.set_ylim(0, 12600)
    ax2b.set_ylabel("储电量 SOC (kWh)", color=MC.PALETTE["soc"], fontsize=8.5)
    ax2b.tick_params(axis="y", colors=MC.PALETTE["soc"], labelsize=7)
    bx = dict(facecolor="white", edgecolor="none", alpha=0.85, pad=0.7)
    ax2b.text(0.4, 1200, "下限 1200", fontsize=5.8, va="bottom", color=MC.PALETTE["emer"], bbox=bx)
    ax2b.text(0.4, 10800, "上限 10800", fontsize=5.8, va="bottom", color=MC.PALETTE["grid"], bbox=bx)
    _haxis(ax2, label="时刻 (h)")

    fig.suptitle("Q3 计划—调整—执行全链（%s）：0:00 计划 → 6/12/18 调整 → 结算用实际值" % day,
                 fontsize=9.8, y=0.985)
    fig.tight_layout(rect=(0, 0, 1, 0.955))
    paths = MC.save_fig(fig, "q3_01_day_rollout_chain", str(FIG_DIR))
    return {
        "name": "q3_01_day_rollout_chain",
        "purpose": "Q3 指定日（%s）四时点滚动全景：计划 G⁰ 与调整后 A、紧急购电 H、充放电与 SOC，"
                   "竖虚线标出 6/12/18 三个更新时点" % day,
        "data_source": [str(Q.SEG_V2B), str(Q.XLSX), "B对话/clean（附件2 负载/光伏）",
                        str(VOI_NOTE)],
        "key_values": {
            "day": day, "day_index": i,
            "G0_kWh": round(float(g0.sum()), 4), "A_kWh": round(float(a.sum()), 4),
            "H_kWh": round(float(h_.sum()), 4), "n_adj_segments": int(diff.sum()),
            "C_kWh": round(float(c.sum()), 4), "D_kWh": round(float(d_.sum()), 4),
            "R_PV_kWh": round(float(rpv.sum()), 4), "R_G_kWh": round(float(rg.sum()), 4),
            "s0_kWh": round(float(s[0]), 4), "s1_kWh": round(float(s[-1]), 4),
            "soc_min_kWh": round(float(s[1:].min()), 4), "soc_max_kWh": round(float(s[1:].max()), 4),
            "J_plan_yuan": round(cs["J_plan"], 4), "J_adj_yuan": round(cs["J_adj"], 4),
            "J_emg_yuan": round(cs["J_emg"], 4),
        },
        "script": "q3_fig_A_main.py",
    }, paths


def fig_q3_02(sub, seg, price, load, pv) -> dict:
    """全年费用四段分解（读法 C）＋ v1（E1，已作废）→ v2（v2b）对照。"""
    seg_e1 = Q.load_seg(Q.SEG_E1, verbose=False)
    c2 = Q.cash_split_C(seg["G0"], seg["A"], seg["H"], price)
    c1 = Q.cash_split_C(seg_e1["G0"], seg_e1["A"], seg_e1["H"], price)
    H2, H1 = float(seg["H"].sum()), float(seg_e1["H"].sum())

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(7.4, 3.8),
                                  gridspec_kw={"width_ratios": [1.0, 1.35], "wspace": 0.26})
    # ---- (a) 四段分解（堆叠）----
    # 黑白可分：四段用"深浅 + 图案"双重区分（灰色段改为深灰 net，避免与琥珀段灰度接近）
    parts = [("计划内 $p\\cdot\\min(G^0,A)$", c2["J_plan"], MC.PALETTE["grid"], ""),
             ("取消退款 $0.5p(G^0{-}A)^+$", c2["J_cut"], MC.PALETTE["net"], "///"),
             ("超额调整 $1.5p(A{-}G^0)^+$", c2["J_over"], MC.PALETTE["pv"], "\\\\\\\\"),
             ("紧急购电 $5p\\cdot H$", c2["J_emg"], MC.PALETTE["emer"], "xxxx")]
    bottom = 0.0
    for nm, v, col, ha in parts:
        ax.bar(0, v / 1e6, bottom=bottom / 1e6, width=0.55, color=col, alpha=0.92,
               hatch=ha, edgecolor="white", lw=0.4, label="%s — %.3f" % (nm, v / 1e6))
        if v / 1e6 > 0.5:      # 只在大段内嵌数值，小段数值放进图例，避免与"合计"重叠
            ax.text(0, (bottom + v / 2) / 1e6, "%.2f" % (v / 1e6), ha="center", va="center",
                    fontsize=6.6, color="white")
        bottom += v
    ax.text(0, bottom / 1e6 * 1.020, "合计 %.2f 百万元" % (bottom / 1e6), ha="center",
            va="bottom", fontsize=7.2)
    ax.set_xticks([]); ax.set_ylabel("全年费用（百万元）", fontsize=8.5)
    ax.set_ylim(0, bottom / 1e6 * 1.30)     # 给"合计 + 三段薄带"留头部空间
    ax.set_title("(a) 读法 C 的四段分解", fontsize=8.8, loc="left")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.05), fontsize=5.6, ncol=1,
              frameon=False)
    ax.grid(axis="y", color=MC.PALETTE["bound"], lw=0.4, alpha=0.5)

    # ---- (b) v1(E1, 已作废) vs v2(v2b) ----
    keys = [("计划购电费", c1["J_plan"], c2["J_plan"]),
            ("调整费", c1["J_adj"], c2["J_adj"]),
            ("紧急购电费", c1["J_emg"], c2["J_emg"]),
            ("合计", c1["J_cash"], c2["J_cash"])]
    x = np.arange(len(keys)); w = 0.36
    ax2.bar(x - w / 2, [k[1] / 1e6 for k in keys], width=w, color=MC.PALETTE["baseline"],
            alpha=0.55, hatch="///", edgecolor="white", lw=0.3,
            label="v1：E1 执行器（已作废，仅对照）")
    ax2.bar(x + w / 2, [k[2] / 1e6 for k in keys], width=w, color=MC.PALETTE["grid"],
            alpha=0.9, edgecolor="white", lw=0.3, label="v2：v2b 执行器（现行交付）")
    for i, (nm, a1, a2) in enumerate(keys):
        ax2.text(i - w / 2, a1 / 1e6 * 1.015, "%.2f" % (a1 / 1e6), ha="center", va="bottom",
                 fontsize=5.8)
        ax2.text(i + w / 2, a2 / 1e6 * 1.015, "%.2f" % (a2 / 1e6), ha="center", va="bottom",
                 fontsize=5.8)
        # 注：相对变化 % **不再逐柱标注**（小柱区文字必然互撞——队长与本人 2026-09-13 两次发现），
        # 统一移到坐标区右上的空白处成块列出
    ax2.set_xticks(x); ax2.set_xticklabels([k[0] for k in keys], fontsize=7.2)
    ax2.set_ylabel("金额（百万元）", fontsize=8.5)
    ax2.set_ylim(0, max(k[1] for k in keys) / 1e6 * 1.34)
    # 注：ΣH 注释原先放在坐标区右下角，会与调整费/紧急费柱的数值标签、+5.39% 重叠
    #（队长 2026-09-13 肉眼发现）→ 现并入面板标题，坐标区内零注释
    ax2.set_title("(b) 执行器升级：v1(E1) → v2(v2b)　（$\\Sigma H$ %.0f → %.0f kWh，−%.1f%%）"
                  % (H1, H2, 100 * (H1 - H2) / H1), fontsize=8.6, loc="left")
    ax2.legend(loc="upper left", fontsize=6.0, framealpha=0.9)
    ax2.grid(axis="y", color=MC.PALETTE["bound"], lw=0.4, alpha=0.5)
    rel = "\n".join("%s %+.2f%%" % (k[0], 100 * (k[2] - k[1]) / k[1]) for k in keys if k[1] > 0)
    ax2.text(0.985, 0.985, "v2 相对 v1 的变化\n" + rel, transform=ax2.transAxes,
             ha="right", va="top", fontsize=6.2,
             bbox=dict(facecolor="white", edgecolor=MC.PALETTE["bound"], lw=0.4, alpha=0.92))
    fig.suptitle("Q3 费用结构与执行器升级收益（读法 C；v1 仅作已作废对照）", fontsize=9.6, y=0.99)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    paths = MC.save_fig(fig, "q3_02_cost_decomposition", str(FIG_DIR))
    return {
        "name": "q3_02_cost_decomposition",
        "purpose": "Q3 全年费用四段分解（读法 C：计划内 / 取消退款 0.5p / 超额 1.5p / 紧急 5p）"
                   "＋ 执行器 E1(v1，已作废) → v2b(v2) 的分项对照",
        "data_source": [str(Q.SEG_V2B), str(Q.SEG_E1), str(Q.XLSX), "B对话/clean（附件1 电价）"],
        "key_values": {
            "v2_J_plan": round(c2["J_plan"], 4), "v2_J_cut": round(c2["J_cut"], 4),
            "v2_J_over": round(c2["J_over"], 4), "v2_J_adj": round(c2["J_adj"], 4),
            "v2_J_emg": round(c2["J_emg"], 4), "v2_J_cash": round(c2["J_cash"], 4),
            "v1_J_plan": round(c1["J_plan"], 4), "v1_J_adj": round(c1["J_adj"], 4),
            "v1_J_emg": round(c1["J_emg"], 4), "v1_J_cash": round(c1["J_cash"], 4),
            "v1_sumH_kWh": round(H1, 4), "v2_sumH_kWh": round(H2, 4),
            "drop_pct": round(100 * (c2["J_cash"] - c1["J_cash"]) / c1["J_cash"], 4),
            "note": "v1 = E1 执行器口径，已作废（见 Q3交付\\01_提交件\\作废声明_v0.md），本图仅作对照",
        },
        "script": "q3_fig_A_main.py",
    }, paths


def fig_q3_03(sub, seg, price, load, pv) -> dict:
    """滚动价值 VOI：v2b 口径下 0:00-only 与 6/12/18 更新的四臂对比（回答题面第 7 问）。"""
    import json as _json
    d = _json.loads(Path(VOI_PATH).read_text(encoding="utf-8"))
    arms = sorted(d["arms"], key=lambda a: len(a["epochs"]))
    labels = ["仅 0:00\n（无更新）", "+6:00", "+12:00", "+18:00"]
    cash = [a["totals"]["J_cash"] for a in arms]
    qh = [a["totals"]["QH"] for a in arms]
    selfck = d["self_check"]

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(7.4, 3.9),
                                  gridspec_kw={"width_ratios": [1.12, 1.0], "wspace": 0.42})
    x = np.arange(len(arms))
    ax.bar(x, [c / 1e6 for c in cash], width=0.6, color=MC.PALETTE["grid"], alpha=0.88,
           edgecolor="white", lw=0.4, label="全年费用 $J_{cash}$（左轴）")
    for i, c in enumerate(cash):
        ax.text(i, c / 1e6 * 1.006, "%.3f" % (c / 1e6), ha="center", va="bottom", fontsize=6.4,
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.8, pad=0.4))
    ax.set_ylim(min(cash) / 1e6 * 0.93, max(cash) / 1e6 * 1.06)     # 放大差异（阶梯更清楚）
    for i in range(1, len(cash)):
        dv = cash[i] - cash[i - 1]
        ax.annotate("", xy=(i - 0.32, cash[i] / 1e6), xytext=(i - 0.68, cash[i - 1] / 1e6),
                    arrowprops=dict(arrowstyle="->", color=MC.PALETTE["emer"], lw=1.1))
        ax.text(i - 0.56, (cash[i] + cash[i - 1]) / 2e6 - 0.004,
                "−%.1f 万\n(%.2f%%)" % (-dv / 1e4, 100 * dv / cash[i - 1]),
                ha="center", va="center", fontsize=5.8, color=MC.PALETTE["emer"],
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.85, pad=0.4))
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=7.0)
    ax.set_ylabel("全年费用（百万元）", fontsize=8.5)
    ax.set_title("(a) 更新时点的边际价值（v2b 口径）", fontsize=8.8, loc="left")
    ax.grid(axis="y", color=MC.PALETTE["bound"], lw=0.4, alpha=0.5)
    ax.legend(loc="upper right", fontsize=6.2, framealpha=0.9)
    axh = ax.twinx()
    axh.plot(x, qh, "-o", ms=3.4, lw=1.2, color=MC.PALETTE["emer"],
             label="$\\Sigma H$（右轴，kWh）")
    # 右轴 ylabel 原先与 (b) 的左轴标签在中间相撞（同类错我在 q2_06 已犯过一次）→ 不再写 ylabel，
    # 单位与含义写进图例（"右轴"）
    axh.tick_params(axis="y", colors=MC.PALETTE["emer"], labelsize=7)
    axh.set_ylim(0, max(qh) * 1.25)
    h1, l1 = ax.get_legend_handles_labels(); h2, l2 = axh.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper right", fontsize=6.2, framealpha=0.9)
    ax.text(0.0, -0.16, "注：纵轴自 %.2f 起（放大四臂差异，非零基线）" % (min(cash) / 1e6 * 0.93),
            transform=ax.transAxes, fontsize=6.0, va="top", color="#555555")

    # (b) 分项构成：计划 / 调整 / 紧急
    plan = np.array([a["totals"]["J_plan"] for a in arms]) / 1e6
    adj = np.array([a["totals"]["J_adj"] for a in arms]) / 1e6
    emg = np.array([a["totals"]["J_emg"] for a in arms]) / 1e6
    ax2.bar(x, plan, width=0.6, color=MC.PALETTE["grid"], alpha=0.88, label="计划购电费")
    ax2.bar(x, adj, bottom=plan, width=0.6, color=MC.PALETTE["pv"], alpha=0.9,
            hatch="\\\\\\", edgecolor="white", lw=0.3, label="调整费")
    ax2.bar(x, emg, bottom=plan + adj, width=0.6, color=MC.PALETTE["emer"], alpha=0.92,
            hatch="xxxx", edgecolor="white", lw=0.3, label="紧急购电费")
    for i in range(len(arms)):
        ax2.text(i, plan[i] * 0.5, "%.2f" % plan[i], ha="center", va="center", fontsize=6.0,
                 color="white")
        ax2.text(i, plan[i] + adj[i] + emg[i] + 0.035, "%.2f" % (plan[i] + adj[i] + emg[i]),
                 ha="center", va="bottom", fontsize=6.2,
                 bbox=dict(facecolor="white", edgecolor="none", alpha=0.8, pad=0.4))
    ax2.set_xticks(x); ax2.set_xticklabels(labels, fontsize=7.0)
    ax2.set_ylabel("金额（百万元）", fontsize=8.5)
    ax2.set_ylim(0, float((plan + adj + emg).max()) * 1.12)
    ax2.set_title("(b) 分项构成：计划 ↓、调整 ↑、紧急 ↓", fontsize=8.8, loc="left")
    ax2.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16), fontsize=6.2, ncol=3,
               frameon=False)     # 原先在右上压住最高柱顶的数值标签
    ax2.grid(axis="y", color=MC.PALETTE["bound"], lw=0.4, alpha=0.5)
    fig.suptitle("Q3 引入其他时点预报的价值（v2b 口径；全年可省 %.1f 万元 = %.2f%%）"
                 % ((cash[0] - cash[-1]) / 1e4, 100 * (cash[0] - cash[-1]) / cash[0]),
                 fontsize=9.4, y=0.99)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    paths = MC.save_fig(fig, "q3_03_rolling_value_voi", str(FIG_DIR))
    return {
        "name": "q3_03_rolling_value_voi",
        "purpose": "Q3 滚动价值（题面第 7 问）：v2b 口径下 0:00-only 与逐次加入 6/12/18 更新的四臂对比，"
                   "标出每次更新的边际节省与 ΣH 变化",
        "data_source": [VOI_PATH, "6对话/code/q3_voi_v2b_run.py（隔离重跑，只调 run_arm）"],
        "key_values": {
            "arms_epochs": [list(a["epochs"]) for a in arms],
            "J_cash_yuan": [round(c, 4) for c in cash],
            "sumH_kWh": [round(q_, 4) for q_ in qh],
            "J_plan_yuan": [round(float(a["totals"]["J_plan"]), 4) for a in arms],
            "J_adj_yuan": [round(float(a["totals"]["J_adj"]), 4) for a in arms],
            "J_emg_yuan": [round(float(a["totals"]["J_emg"]), 4) for a in arms],
            "marginal_yuan": [round(cash[i] - cash[i - 1], 4) for i in range(1, len(cash))],
            "total_saving_yuan": round(cash[0] - cash[-1], 4),
            "total_saving_pct": round(100 * (cash[0] - cash[-1]) / cash[0], 4),
            "self_check_full_arm": selfck,
        },
        "script": "q3_fig_A_main.py",
    }, paths


def fig_q3_04(sub, seg, price, load, pv) -> dict:
    """论文表 1/2/3 的四日期图形化（3 行 × 4 列）。"""
    pt = Q.paper_tables(sub, seg)
    dates = Q.PAPER_DATES
    slot_labs = ["10:00", "12:00", "14:00", "16:00", "18:00", "20:00"]
    slot_keys = ["10:00-10:10", "12:00-12:10", "14:00-14:10",
                 "16:00-16:10", "18:00-18:10", "20:00-20:10"]
    blk_labs = ["0-4", "4-8", "8-12", "12-16", "16-20", "20-24"]

    fig, axes = plt.subplots(3, 4, figsize=(7.6, 6.8),
                             gridspec_kw={"hspace": 0.60, "wspace": 0.44})
    emg_all = {}
    for c, ds in enumerate(dates):
        r = pt[ds]
        # --- 行1：表1（6 时段 G0 vs A） ---
        ax = axes[0, c]
        g0 = [r["slots"][k]["G0"] for k in slot_keys]
        a_ = [r["slots"][k]["A"] for k in slot_keys]
        xs = np.arange(6)
        ax.bar(xs - 0.2, g0, width=0.38, color=MC.PALETTE["grid"], alpha=0.85, label="计划 $G^0$")
        ax.bar(xs + 0.2, a_, width=0.38, color=MC.PALETTE["pv"], alpha=0.9, hatch="\\\\\\",
               edgecolor="white", lw=0.3, label="调整后 $A$")
        ax.set_xticks(xs); ax.set_xticklabels(slot_labs, fontsize=5.0, rotation=45, ha="right")
        ax.set_ylim(0, max(g0 + a_ + [1.0]) * 1.30)
        ax.set_title("%s｜表1" % ds, fontsize=7.0, loc="left")
        ax.tick_params(axis="y", labelsize=5.6)
        if c == 0:
            ax.set_ylabel("表1", fontsize=7.5)
            ax.legend(fontsize=5.0, loc="upper left", framealpha=0.9)
        ax.grid(axis="y", color=MC.PALETTE["bound"], lw=0.35, alpha=0.5)
        # --- 行2：表2（6 个 4h 块 充/放） ---
        ax = axes[1, c]
        blk = r["blocks"][:6]
        ch = [b["C"] for b in blk]; dis = [b["D"] for b in blk]
        xs = np.arange(6)
        ax.bar(xs - 0.2, ch, width=0.38, color=MC.PALETTE["charge"], alpha=0.88, label="充电")
        ax.bar(xs + 0.2, dis, width=0.38, color=MC.PALETTE["discharge"], alpha=0.9, hatch="xxx",
               edgecolor="white", lw=0.3, label="放电")
        ax.set_xticks(xs); ax.set_xticklabels(blk_labs, fontsize=4.6, rotation=30, ha="right")
        ax.set_ylim(0, max(ch + dis + [1.0]) * 1.30)
        ax.set_title("表2 充放电 (kWh)", fontsize=7.0, loc="left")
        ax.tick_params(axis="y", labelsize=5.6)
        ax.set_xlabel("时段 (h)", fontsize=6.0)
        if c == 0:
            ax.set_ylabel("表2", fontsize=7.5)
            ax.legend(fontsize=5.0, loc="upper right", framealpha=0.9)
        ax.grid(axis="y", color=MC.PALETTE["bound"], lw=0.35, alpha=0.5)
        # --- 行3：表3（当日紧急段，24h 时间轴） ---
        ax = axes[2, c]
        tot = 0.0
        for s in r["emg"]:
            h0, m0 = (int(x) for x in s["span"].split("-")[0].split(":"))
            h1, m1 = (int(x) for x in s["span"].split("-")[1].split(":"))
            x0, x1 = h0 + m0 / 60, h1 + m1 / 60
            ax.bar((x0 + x1) / 2, s["kWh"], width=max(x1 - x0, 0.14),
                   color=MC.PALETTE["emer"], alpha=0.92, hatch="///", edgecolor="white", lw=0.25)
            tot += s["kWh"]
        ax.set_xlim(0, 24); ax.set_xticks(range(0, 25, 6))
        ax.set_xticklabels(["0", "6", "12", "18", "24"], fontsize=5.4)
        ax.set_ylim(0, max([s["kWh"] for s in r["emg"]] + [1.0]) * 1.35)
        # 标题过长会在相邻子图之间首尾相撞（本人 2026-09-13 目视）→ 只留短标签，段数/合计放图内
        ax.set_title("表3 紧急购电", fontsize=7.0, loc="left")
        ax.text(0.985, 0.97, "%d 段\n%.1f kWh" % (len(r["emg"]), tot), transform=ax.transAxes,
                ha="right", va="top", fontsize=5.8,
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.85, pad=0.5))
        ax.tick_params(axis="y", labelsize=5.6)
        ax.set_xlabel("时刻 (h)", fontsize=6.0)
        if c == 0:
            ax.set_ylabel("表3", fontsize=7.5)
        ax.grid(axis="y", color=MC.PALETTE["bound"], lw=0.35, alpha=0.5)
        emg_all[ds] = {"n": len(r["emg"]), "kWh": round(tot, 4),
                       "day_G0": r["day_G0_kWh"], "day_A": r["day_A_kWh"],
                       "day_fee": r["day_fee_yuan"]}
    fig.suptitle("Q3 论文表 1/2/3 四日期图形化（v2 口径；表3 为全量段，已按提交件前向填充）",
                 fontsize=9.4, y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    paths = MC.save_fig(fig, "q3_04_paper_tables_graph", str(FIG_DIR))
    return {
        "name": "q3_04_paper_tables_graph",
        "purpose": "Q3 论文表 1（6 时段购电量 G⁰/A）、表 2（6 个 4 小时块充放电）、表 3（当日紧急购电全量段）"
                   "在四个指定日期上的图形化对照",
        "data_source": [str(Q.XLSX) + "（按单元格值，列映射 col=2+t）", str(Q.SEG_V2B),
                        "Q3交付/03_论文素材/论文表1表2表3_四个指定日期_v2.md（已勘误）"],
        "key_values": {ds: v for ds, v in emg_all.items()},
        "script": "q3_fig_A_main.py",
    }, paths


def fig_q3_05(sub, seg, price, load, pv) -> dict:
    """全年 SOC：日界轨迹 + 时段内范围 + 边界 + 触顶/触底日历。"""
    S = seg["S"]                     # (334, 145)
    n = S.shape[0]
    s0, s1 = S[:, 0], S[:, -1]
    dmin, dmax = S[:, 1:].min(axis=1), S[:, 1:].max(axis=1)
    lo_days = int((dmin <= 1200 + 1e-6).sum())
    hi_days = int((dmax >= 10800 - 1e-6).sum())
    x = np.arange(n)
    yt, yl = [], []
    for j, ds in enumerate(seg["dates"]):
        if ds[8:10] == "01":
            yt.append(j); yl.append(ds[:7])

    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(7.4, 5.6),
                                  gridspec_kw={"height_ratios": [2.1, 1.0], "hspace": 0.32})
    ax.fill_between(x, dmin, dmax, color=MC.PALETTE["soc"], alpha=0.30, lw=0,
                    label="当日时段内 SOC 范围")
    ax.plot(x, s1, "-", color=MC.PALETTE["soc"], lw=1.3, label="日末 SOC（$s_1$）")
    ax.plot(x, s0, ":", color=MC.PALETTE["net"], lw=1.0, label="日初 SOC（$s_0$）")
    ax.axhline(1200, color=MC.PALETTE["emer"], lw=1.0, ls="--")
    ax.axhline(10800, color=MC.PALETTE["grid"], lw=1.0, ls="--")
    bx = dict(facecolor="white", edgecolor="none", alpha=0.85, pad=0.7)
    ax.text(n - 1, 1200, " 下限 1200 ", ha="right", va="top", fontsize=6.2,
            color=MC.PALETTE["emer"], bbox=bx)
    ax.text(n - 1, 10800, " 上限 10800 ", ha="right", va="bottom", fontsize=6.2,
            color=MC.PALETTE["grid"], bbox=bx)
    ax.set_xticks(yt); ax.set_xticklabels(yl, fontsize=7)
    ax.set_xlim(0, n - 1)
    ax.set_ylim(min(1200.0, float(dmin.min())) - 600, max(10800.0, float(dmax.max())) + 600)
    ax.set_ylabel("储电量 SOC (kWh)", fontsize=8.5)
    ax.set_title("(a) 全年 SOC 与容量边界（时段内：触顶 %d/%d 天、触底 %d 天；日界水平见放大框）"
                 % (hi_days, n, lo_days), fontsize=8.8, loc="left")
    ax.legend(loc="upper left", bbox_to_anchor=(0.0, -0.06), fontsize=6.4, ncol=3,
              framealpha=0.0, borderaxespad=0.0)
    ax.grid(color=MC.PALETTE["bound"], lw=0.4, alpha=0.35)
    # 日界 SOC 全年稳定在 ~7950，被上下限拉开后看不清 → 加放大插图
    axi = ax.inset_axes([0.60, 0.32, 0.36, 0.28])
    axi.plot(x, s1, "-", color=MC.PALETTE["soc"], lw=1.0)
    axi.plot(x, s0, ":", color=MC.PALETTE["net"], lw=0.8)
    axi.set_xlim(0, n - 1)
    lo_z = float(min(s0.min(), s1.min())); hi_z = float(max(s0.max(), s1.max()))
    pad = max(50.0, 0.15 * (hi_z - lo_z))
    axi.set_ylim(lo_z - pad, hi_z + pad)
    axi.set_xticks(yt[::2]); axi.set_xticklabels(yl[::2], fontsize=5.0)
    axi.tick_params(axis="y", labelsize=5.4)
    axi.set_title("日界 SOC 放大（%.0f~%.0f kWh）" % (lo_z, hi_z), fontsize=5.8, loc="left")
    axi.grid(color=MC.PALETTE["bound"], lw=0.3, alpha=0.4)
    axi.set_facecolor("white")

    ax2.bar(x, (dmax >= 10800 - 1e-6).astype(int), width=1.0, color=MC.PALETTE["grid"],
            alpha=0.75, label="当日触顶（≥10800）")
    ax2.bar(x, -(dmin <= 1200 + 1e-6).astype(int), width=1.0, color=MC.PALETTE["emer"],
            alpha=0.9, hatch="///", edgecolor="white", lw=0.2, label="当日触底（≤1200）")
    ax2.axhline(0, color=MC.PALETTE["bound"], lw=0.8)
    ax2.set_xticks(yt); ax2.set_xticklabels(yl, fontsize=7)
    ax2.set_xlim(0, n - 1); ax2.set_ylim(-1.6, 1.6)
    ax2.set_yticks([-1, 0, 1]); ax2.set_yticklabels(["触底", "—", "触顶"], fontsize=7)
    ax2.set_xlabel("2025 年（%d 天：02-01 ~ 12-31）" % n, fontsize=8)
    ax2.set_title("(b) 触顶/触底日历", fontsize=8.8, loc="left")
    ax2.legend(loc="upper left", fontsize=6.2, ncol=2, framealpha=0.9)
    ax2.text(0.995, 0.86, "触顶 %d/%d 天（紫带铺满 = 每日均触及 10800）" % (hi_days, n),
             transform=ax2.transAxes, ha="right", va="center", fontsize=6.2,
             bbox=dict(facecolor="white", edgecolor="none", alpha=0.85, pad=0.6))
    fig.tight_layout(rect=(0, 0, 1, 0.98))
    paths = MC.save_fig(fig, "q3_05_soc_year", str(FIG_DIR))
    return {
        "name": "q3_05_soc_year",
        "purpose": "Q3 全年储能 SOC：日界链与时段内范围、1200/10800 边界、逐日触顶/触底日历（v2b 口径）",
        "data_source": [str(Q.SEG_V2B)],
        "key_values": {"n_days": n, "soc_min_kWh": round(float(dmin.min()), 4),
                       "soc_max_kWh": round(float(dmax.max()), 4),
                       "touch_low_days": lo_days, "touch_high_days": hi_days,
                       "S0_kWh": round(float(s0[0]), 4), "S_end_kWh": round(float(s1[-1]), 4)},
        "script": "q3_fig_A_main.py",
    }, paths


def fig_q3_06(sub, seg, price, load, pv) -> dict:
    """计划↔调整结构：逐日 Δ=(A−G⁰) 的削减/超调，以及 Δ 的时段分布。"""
    G0, A = seg["G0"], seg["A"]
    dlt = A - G0
    day_cut = (-np.minimum(dlt, 0.0)).sum(axis=1)      # 当日削减量 kWh
    day_over = np.maximum(dlt, 0.0).sum(axis=1)        # 当日超调量 kWh
    tot_cut, tot_over = float(day_cut.sum()), float(day_over.sum())
    hour_delta = dlt.sum(axis=0)                       # 每个 10 分钟时段的净调整（全年累计）
    h = np.arange(T) * DT

    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(7.4, 5.4),
                                  gridspec_kw={"height_ratios": [1.25, 1.0], "hspace": 0.34})
    x = np.arange(len(day_cut))
    ax.bar(x, -day_cut, width=1.0, color=MC.PALETTE["curtail"], alpha=0.85, hatch="///",
           edgecolor="white", lw=0.15, label="当日削减 $\\Sigma(G^0-A)^+$（向下）")
    ax.bar(x, day_over, width=1.0, color=MC.PALETTE["pv"], alpha=0.9, hatch="\\\\\\",
           edgecolor="white", lw=0.15, label="当日超调 $\\Sigma(A-G^0)^+$（向上）")
    ax.axhline(0, color=MC.PALETTE["bound"], lw=0.8)
    lim = max(day_cut.max(), day_over.max()) * 1.35
    ax.set_ylim(-lim, lim)
    yt, yl = [], []
    for j, ds in enumerate(seg["dates"]):
        if ds[8:10] == "01":
            yt.append(j); yl.append(ds[:7])
    ax.set_xticks(yt); ax.set_xticklabels(yl, fontsize=7)
    ax.set_xlim(0, len(day_cut) - 1)
    ax.set_ylabel("当日调整量 (kWh)", fontsize=8.5)
    ax.set_title("(a) 逐日调整结构：削减 vs 超调（全年 削减 %.1f 万 / 超调 %.1f 万 kWh）"
                 % (tot_cut / 1e4, tot_over / 1e4), fontsize=8.8, loc="left")
    ax.legend(loc="upper left", fontsize=6.2, ncol=2, framealpha=0.9)
    ax.grid(axis="y", color=MC.PALETTE["bound"], lw=0.4, alpha=0.4)

    ax2.bar(h, hour_delta, width=DT * 0.9,
            color=[MC.PALETTE["pv"] if v >= 0 else MC.PALETTE["curtail"] for v in hour_delta],
            alpha=0.9, edgecolor="white", lw=0.15)
    ax2.axhline(0, color=MC.PALETTE["bound"], lw=0.8)
    ax2.set_xlim(0, 24); ax2.set_xticks(range(0, 25, 2))
    ax2.set_xticklabels(["%d:00" % k for k in range(0, 25, 2)], fontsize=7)
    ax2.set_xlabel("时刻 (h)", fontsize=8.5)
    ax2.set_ylabel("净调整量 (kWh，全年累计)", fontsize=8.0)
    ax2.set_title("(b) 调整的时段分布（正=超调，负=削减）", fontsize=8.8, loc="left")
    ax2.grid(axis="y", color=MC.PALETTE["bound"], lw=0.4, alpha=0.4)
    fig.tight_layout(rect=(0, 0, 1, 0.98))
    paths = MC.save_fig(fig, "q3_06_adj_structure", str(FIG_DIR))
    return {
        "name": "q3_06_adj_structure",
        "purpose": "Q3 计划↔调整结构：逐日削减/超调量与全年时段分布（正=超调、负=削减），"
                   "说明调整主要发生在哪些时段",
        "data_source": [str(Q.SEG_V2B), str(Q.XLSX)],
        "key_values": {"sum_cut_kWh": round(tot_cut, 4), "sum_over_kWh": round(tot_over, 4),
                       "days_with_cut": int((day_cut > 1e-9).sum()),
                       "days_with_over": int((day_over > 1e-9).sum()),
                       "max_day_cut_kWh": round(float(day_cut.max()), 4),
                       "max_day_over_kWh": round(float(day_over.max()), 4)},
        "script": "q3_fig_A_main.py",
    }, paths


def _box(ax, x, y, w, h, title, lines, *, fc="#FFFFFF", ec="#888888", fs=6.6):
    ax.add_patch(plt.Rectangle((x, y), w, h, facecolor=fc, edgecolor=ec, lw=0.8, zorder=1))
    ax.text(x + w / 2, y + h - 0.05 * h, title, ha="center", va="top", fontsize=fs + 0.6,
            zorder=2)
    ax.text(x + w / 2, y + h - 0.30 * h, "\n".join(lines), ha="center", va="top",
            fontsize=fs, zorder=2, linespacing=1.5)


def fig_q3_07(sub, seg, price, load, pv) -> dict:
    """三层价格 + 紧急购电的决策边界示意（系数取自题面，不含口径相关数值）。"""
    fig, ax = plt.subplots(figsize=(7.4, 2.9))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    segs = [(0.03, 0.20, "取用 < 计划", "$0.5p\\,(G^0-A)^+$\n取消部分**净退一半**", "#F2E6DA"),
            (0.24, 0.20, "取用 = 计划", "$p\\cdot\\min(G^0,A)$\n按原价结算", "#EDE7F6"),
            (0.45, 0.20, "取用 > 计划", "$1.5p\\,(A-G^0)^+$\n超出部分 1.5 倍", "#FBE3DA"),
            (0.66, 0.31, "另有缺口（低于负载）", "$5p\\cdot H$\n紧急购电 5 倍", "#FADBD8")]
    for x, w, t1, t2, fc in segs:
        ax.add_patch(plt.Rectangle((x, 0.42), w, 0.34, facecolor=fc, edgecolor="#888888", lw=0.8))
        ax.text(x + w / 2, 0.68, t1, ha="center", va="center", fontsize=7.0)
        ax.text(x + w / 2, 0.54, t2.replace("**", ""), ha="center", va="center", fontsize=6.4)
    ax.annotate("", xy=(0.97, 0.36), xytext=(0.03, 0.36),
                arrowprops=dict(arrowstyle="->", color="#555555", lw=1.0))
    ax.text(0.5, 0.29, "实际取用量 $A$ 相对 计划购电量 $G^0$ 的位置", ha="center", fontsize=7.0)
    ax.text(0.5, 0.14, "读法 C 的四段计价（v2 交付口径）：取消退款 0.5p ｜ 计划内 1p ｜ 超出 1.5p ｜ 缺口 5p",
            ha="center", fontsize=7.0)
    ax.text(0.5, 0.03, "注：系数 1 / 0.5 / 1.5 / 5 均取自题面；本图不含任何口径相关数值",
            ha="center", fontsize=6.0, color="#666666")
    fig.tight_layout()
    paths = MC.save_fig(fig, "q3_07_three_layer_price", str(FIG_DIR))
    return {"name": "q3_07_three_layer_price",
            "purpose": "Q3 三层价格与紧急购电的决策边界示意（取消退款 0.5p / 计划内 1p / 超出 1.5p / 缺口 5p）",
            "data_source": ["赛题 C 题问题 3 原文（系数来源）",
                            "Q3交付/manifest.sha256.json（读法 C 公式）"],
            "key_values": {"coefficients": {"cancel_refund": 0.5, "in_plan": 1.0,
                                            "over_plan": 1.5, "shortfall": 5.0},
                           "note": "纯机制示意，无数值结论"},
            "script": "q3_fig_A_main.py"}, paths


def fig_q3_08(sub, seg, price, load, pv) -> dict:
    """v2b 执行器机制示意 + 与 E1 的执行差异（回退修正的净效应）。"""
    e1 = Q.load_seg(Q.SEG_E1, verbose=False)
    dA = (seg["A"] - e1["A"]).sum(axis=1)     # 逐日取用量差异 kWh
    dD = (seg["D"] - e1["D"]).sum(axis=1)
    dC = (seg["C"] - e1["C"]).sum(axis=1)
    n_days_diff = int((np.abs(dA) > 1e-9).sum())

    fig = plt.figure(figsize=(7.4, 3.6))
    ax = fig.add_axes([0.02, 0.30, 0.42, 0.62]); ax.axis("off")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    _box(ax, 0.02, 0.70, 0.44, 0.28, "计划层（0:00 / 6 / 12 / 18）", ["给出 $G^0$ 与充放电计划"], fs=6.6)
    _box(ax, 0.52, 0.70, 0.46, 0.28, "实测到达（L / PV）", ["与计划发生冲突"], fs=6.6)
    _box(ax, 0.02, 0.06, 0.88, 0.44, "执行器 v2b",
         ["① 实测富余/缺口与计划不一致时，", "   允许执行层回退为计划动作；",
          "② 缺口仍按 5p 紧急购电兜底；", "③ 与 E1 的唯一差别 = 该回退规则"],
         fs=6.4)
    ax.annotate("", xy=(0.5, 0.52), xytext=(0.5, 0.68),
                arrowprops=dict(arrowstyle="-|>", color="#555555", lw=1.2))
    ax2 = fig.add_axes([0.56, 0.10, 0.42, 0.78])
    x = np.arange(len(dA))
    ax2.bar(x, dA, width=1.0,
            color=[MC.PALETTE["pv"] if v >= 0 else MC.PALETTE["curtail"] for v in dA],
            alpha=0.9, edgecolor="white", lw=0.1)
    ax2.axhline(0, color=MC.PALETTE["bound"], lw=0.8)
    ax2.set_xlim(0, len(dA))       # 末柱宽 1.0，原 xlim=len-1 会让最后一根越出可见刻度（豆包 2026-09-13 指出）
    ax2.set_ylabel("逐日 $A_{v2b}-A_{E1}$ (kWh)", fontsize=7.4)
    ax2.set_xlabel("全年序日（0 = 2025-02-01）", fontsize=8)
    ax2.set_title("v2b 与 E1 的执行差异（%d/%d 天不同）" % (n_days_diff, len(dA)),
                  fontsize=8.4, loc="left")
    ax2.grid(axis="y", color=MC.PALETTE["bound"], lw=0.4, alpha=0.45)
    fig.suptitle("Q3 执行器 v2b 的回退机制与净效应（v2b 为现行交付；E1 为已作废对照）",
                 fontsize=8.8, y=0.98)
    paths = MC.save_fig(fig, "q3_08_exec_v2b_mechanism", str(FIG_DIR))
    return {"name": "q3_08_exec_v2b_mechanism",
            "purpose": "Q3 执行器 v2b 机制示意（实测与计划冲突时回退计划动作）+ 与 E1 的逐日取用差异（净效应）",
            "data_source": [str(Q.SEG_V2B), str(Q.SEG_E1),
                            "Q3交付/04_证据/组件哈希与环境指纹.md（执行器 fa1d86f0…）"],
            "key_values": {"days_with_diff": n_days_diff, "n_days": len(dA),
                           "sum_dA_kWh": round(float(dA.sum()), 4),
                           "sum_dC_kWh": round(float(dC.sum()), 4),
                           "sum_dD_kWh": round(float(dD.sum()), 4),
                           "note": "E1 为已作废口径，仅作对照"},
            "script": "q3_fig_A_main.py"}, paths


def fig_q3_09(sub, seg, price, load, pv) -> dict:
    """(q, m) 参数化示意：两根不同的轴，不落单点（按 7.5 四方共验的措辞红线）。"""
    fig, ax = plt.subplots(figsize=(7.4, 3.2))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    _box(ax, 0.04, 0.46, 0.42, 0.44, "$q$：净需求保守度（加性）",
         ["作用于全天净需求分位；", "标定点在 0.5 一侧与 0.8 一侧", "各有其最低费用（网格分辨率 ≈0.04%）"],
         fs=6.4)
    _box(ax, 0.54, 0.46, 0.42, 0.44, "$m$：光伏形状裕度（乘性）",
         ["仅作用于白天光伏的乘性下移；", "与 $q$ 不在同一根轴上，", "二者的费用差不可解释为方法优劣"],
         fs=6.4)
    ax.text(0.5, 0.33, "⇒ 论文写法：「同参数化内的标定结果 + 分辨率 + 区间」，",
            ha="center", fontsize=7.0)
    ax.text(0.5, 0.24, "不得写成「q=0.8 最优」或「q=0.5 更优」（7.5 四方共验一致禁止）",
            ha="center", fontsize=7.0, color=MC.PALETTE["emer"])
    ax.text(0.5, 0.12, "本图为口径与措辞示意，不含任何 E1/v1 口径的数值结论",
            ha="center", fontsize=6.2, color="#666666")
    fig.tight_layout()
    paths = MC.save_fig(fig, "q3_09_qm_parameterization", str(FIG_DIR))
    return {"name": "q3_09_qm_parameterization",
            "purpose": "Q3 计划层 (q, m) 参数化示意：说明 q 与 m 是两根不同的轴、费用差不可归因于方法优劣，"
                       "并给出论文允许的措辞（标定结果 + 分辨率 + 区间）",
            "data_source": ["7.5对话/裁定记录_Q3优化方向_四方共验汇总_20260912.md（措辞裁定）",
                            "7.6对话/禁引清单_Q3_20260912.md（禁引规则）"],
            "key_values": {"forbidden_phrases": ["q=0.8 最优", "q=0.5 更优", "Q3 比 Q2 改进"],
                           "note": "纯示意；不含 E1/v1 口径数值"},
            "script": "q3_fig_A_main.py"}, paths


def fig_q3_10(sub, seg, price, load, pv) -> dict:
    """结算读法 A vs C 的示意（差异只发生在 A ≠ G⁰ 的时段）。"""
    fig, ax = plt.subplots(figsize=(7.4, 3.2))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    _box(ax, 0.04, 0.52, 0.44, 0.40, "读法 A（题面字面）",
         ["$p\\cdot G^0$：按计划购电量全额计费；", "取用不足不退、超出另计"], fs=6.6)
    _box(ax, 0.52, 0.52, 0.44, 0.40, "读法 C（本文交付）",
         ["$p\\min(G^0,A)+0.5p(G^0{-}A)^+$", "$+1.5p(A{-}G^0)^+$（差异仅在 $A\\ne G^0$ 时段）"], fs=6.6)
    ax.text(0.5, 0.40, "两读法的差：$A<G^0$ 时 C 退还一半、A 不退；$A>G^0$ 时 C 按 1.5 倍计",
            ha="center", fontsize=6.8)
    ax.text(0.5, 0.28, "⇒ 论文必须写明：本题取读法 C 的依据 + 与读法 A 的对照；",
            ha="center", fontsize=6.8)
    ax.text(0.5, 0.19, "且「最优裕度/优化方向」类结论须写成读法条件结论（7.5 审计实测）",
            ha="center", fontsize=6.8, color=MC.PALETTE["grid"])
    ax.text(0.5, 0.06, "本图为口径示意；两读法的金额对照见 7.6 证据链（E1 口径，未纳入 v2，故本图不列数）",
            ha="center", fontsize=6.0, color="#666666")
    fig.tight_layout()
    paths = MC.save_fig(fig, "q3_10_settlement_readings", str(FIG_DIR))
    return {"name": "q3_10_settlement_readings",
            "purpose": "Q3 结算读法 A（按计划量全额）与 C（本文交付：退款 0.5p / 超出 1.5p）的差异示意，"
                       "并强调结论须写成读法条件结论",
            "data_source": ["7.5对话/裁定记录_Q75_结算读法_三方共验.md",
                            "Q3交付/manifest.sha256.json（读法 C 公式）"],
            "key_values": {"readings": ["A: p·G0", "C: p·min+0.5p退款+1.5p超出"],
                           "note": "纯示意；A/C 金额对照为 E1 口径，未用于本图"},
            "script": "q3_fig_A_main.py"}, paths


def fig_q3_12(sub, seg, price, load, pv) -> dict:
    """紧急购电费与紧急购电量的尾部集中（v2b 口径）。"""
    day = Q.daily_agg(seg, price)
    J = np.sort(day["J_emg"])[::-1]
    H = np.sort(day["QH"])[::-1]
    n = len(J); tot = float(J.sum())
    cum = np.cumsum(J) / tot * 100
    marks = [5, 10, 17, 34]
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(7.4, 3.5),
                                  gridspec_kw={"width_ratios": [1.0, 1.15], "wspace": 0.32})
    ax.plot(np.arange(1, n + 1) / n * 100, cum, "-", color=MC.PALETTE["emer"], lw=1.5,
            label="累计紧急费占比（降序）")
    ax.plot([0, 100], [0, 100], ":", color=MC.PALETTE["bound"], lw=1.0, label="均等参照线")
    for k in marks:
        ax.plot([k / n * 100], [cum[k - 1]], "o", ms=3.4, color=MC.PALETTE["emer"],
                markeredgecolor="white", markeredgewidth=0.4)
    ax.annotate("前 20%% 天数占 %.1f%% 紧急费" % cum[int(0.2 * n) - 1], xy=(20, cum[int(0.2 * n) - 1]),
                xytext=(34, 52), fontsize=6.4,
                arrowprops=dict(arrowstyle="->", color="#666666", lw=0.7))
    ax.set_xlabel("按日紧急费降序的累计天数占比 (%)", fontsize=8)
    ax.set_ylabel("累计紧急费占比 (%)", fontsize=8)
    ax.set_xlim(0, 100); ax.set_ylim(0, 103)
    ax.set_title("(a) 尾部集中（Lorenz 型）", fontsize=8.8, loc="left")
    ax.legend(loc="lower right", fontsize=6.2, framealpha=0.9)
    ax.grid(color=MC.PALETTE["bound"], lw=0.4, alpha=0.4)
    idx = np.argsort(-day["J_emg"])[:10]
    top_dates = [day["date"][i] for i in idx]
    top_J = [float(day["J_emg"][i]) for i in idx]
    labs = [d[5:] for d in top_dates]
    # 单位从"万元/日"改成"千元/日"：原先 1 位小数把 10 根柱全部四舍五入成 0.3/0.2（本人目视发现）
    ax2.bar(np.arange(10), np.array(top_J) / 1e3, width=0.62, color=MC.PALETTE["emer"],
            alpha=0.92, hatch="///", edgecolor="white", lw=0.3)
    for i, v in enumerate(top_J):
        ax2.text(i, v / 1e3 * 1.02, "%.2f" % (v / 1e3), ha="center", va="bottom", fontsize=5.6)
    ax2.set_xticks(np.arange(10)); ax2.set_xticklabels(labs, fontsize=5.8, rotation=45, ha="right")
    ax2.set_ylabel("当日紧急购电费（千元/日）", fontsize=8)
    ax2.set_title("(b) 最高 10 天（合计占全年 %.1f%%）" % (sum(top_J) / tot * 100),
                  fontsize=8.8, loc="left")
    ax2.grid(axis="y", color=MC.PALETTE["bound"], lw=0.4, alpha=0.5)
    fig.suptitle("Q3 紧急购电的尾部结构（v2b 口径）：Σ=%.2f 万元，%d 天中前 5 天占 %.1f%%"
                 % (tot / 1e4, n, cum[4]), fontsize=9.2, y=0.99)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    paths = MC.save_fig(fig, "q3_12_emergency_tail", str(FIG_DIR))
    return {"name": "q3_12_emergency_tail",
            "purpose": "Q3 紧急购电（费/量）的尾部集中：Lorenz 型累计曲线 + 最高的 10 天，"
                       "说明尾部的量级与集中度（v2b 口径）",
            "data_source": [str(Q.SEG_V2B), str(Q.XLSX)],
            "key_values": {"total_J_emg_yuan": round(tot, 4),
                           "total_QH_kWh": round(float(seg["H"].sum()), 4),
                           "top_shares_pct": {str(k): round(float(cum[k - 1]), 4) for k in marks},
                           "top20pct_days_share_pct": round(float(cum[int(0.2 * n) - 1]), 4),
                           "top10_days": top_dates,
                           "top10_J_emg_yuan": [round(v, 2) for v in top_J]},
            "script": "q3_fig_A_main.py"}, paths


def fig_q3_14(sub, seg, price, load, pv) -> dict:
    """限度汇总（必须披露项）。"""
    items = [
        ("口径与版本", ["现行 = 读法 C + 执行器 v2b（全年 %.2f 百万元）" % (Q.EXPECT["J_cash_yuan"] / 1e6),
                        "v1（E1，13.3697 百万元）**已作废**，仅可出现在对照语境"]),
        ("提交件哈希", ["xlsx 字节 sha 不稳定（zip 时间戳）→ 验收按**单元格值/逐段真值**比对"]),
        ("内部账 vs 交付列", ["$R_G$（弃计划电）**不是交付件任何一列**，只影响内部账与叙述自洽"]),
        ("读法张力", ["题面字面近读法 A（$pG^0$）；本文取读法 C 并须写明依据与对照",
                      "「最优裕度/方向」类结论须写成**读法条件结论**"]),
        ("计划层参数", ["$q$ 与 $m$ 不同轴；不得写「q=0.8 最优 / q=0.5 更优」",
                        "m 网格(E2)为 E1 口径、未重跑 → 本文不引用其数值"]),
        ("预报是自建规则", ["过去 4 天实际均值 × 因果裕度(过去 28 天 Q20，均值≈7%)；参数仅用 d 之前信息"]),
        ("敏感性口径", ["VOI/E3 原为 E1 口径 → 本线已用 **v2b 重跑四臂**（隔离运行，未改交付件）"]),
    ]
    fig, ax = plt.subplots(figsize=(7.4, 4.0))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    y = 0.94
    for title, lines in items:
        ax.text(0.01, y, "• " + title, fontsize=7.4, va="top", color=MC.PALETTE["grid"])
        yy = y - 0.045
        for ln in lines:
            ax.text(0.035, yy, ln.replace("**", ""), fontsize=6.6, va="top", color="#333333")
            yy -= 0.043
        y = yy - 0.018
    ax.set_title("Q3 必须披露的限度（7 项）", fontsize=9.2, loc="left")
    fig.tight_layout()
    paths = MC.save_fig(fig, "q3_14_limits_disclosure", str(FIG_DIR))
    return {"name": "q3_14_limits_disclosure",
            "purpose": "Q3 必须披露的限度汇总：版本口径、哈希稳定性、R_G 非交付列、A/C 读法张力、"
                       "(q,m) 措辞、预报规则、敏感性口径",
            "data_source": ["Q3交付/01_提交件/作废声明_v0.md", "Q3交付/manifest.sha256.json",
                            "Q3交付/04_证据/组件哈希与环境指纹.md",
                            "7.5对话/裁定记录_Q3优化方向_四方共验汇总_20260912.md",
                            "7.6对话/禁引清单_Q3_20260912.md"],
            "key_values": {"n_items": len(items),
                           "v2_J_cash_yuan": Q.EXPECT["J_cash_yuan"],
                           "v1_J_cash_yuan": Q.EXPECT["v1_J_cash_yuan"]},
            "script": "q3_fig_A_main.py"}, paths


def fig_q3_15(sub, seg, price, load, pv) -> dict:
    """Q3 全流程示意。"""
    fig, ax = plt.subplots(figsize=(7.4, 3.0))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    boxes = [(0.01, "数据", ["附件1 电价（典型日）", "附件2 实际负载/光伏"]),
             (0.21, "预报构造", ["过去 4 天实际均值", "× (1 − 因果裕度 ≈7%)"]),
             (0.41, "计划层", ["0:00 全天计划 $G^0$", "情景/分位参数化 (q, m)"]),
             (0.61, "调整层", ["6/12/18 时更新 $A$", "只用该时点之后的信息"]),
             (0.81, "执行器 v2b", ["实测冲突→回退计划动作", "缺口 5p 紧急购电"])]
    for x, t, ls in boxes:
        _box(ax, x, 0.42, 0.17, 0.46, t, ls, fs=6.0)
    for x in (0.185, 0.385, 0.585, 0.785):
        ax.annotate("", xy=(x + 0.025, 0.65), xytext=(x, 0.65),
                    arrowprops=dict(arrowstyle="-|>", color="#555555", lw=1.0))
    _box(ax, 0.21, 0.06, 0.58, 0.26, "物化与验证",
         ["result3_v2.xlsx（表1/表2/表3）→ 物理轨（平衡/容量/互斥）+ 经济轨（费用恒等式）"],
         fs=6.2, fc="#F7F7F7")
    # 箭头应体现「执行器产物 → 物化」，原先画在计划层下方，语义易误读（本人 2026-09-13 目视）
    ax.annotate("", xy=(0.895, 0.33), xytext=(0.895, 0.41),
                arrowprops=dict(arrowstyle="-|>", color="#555555", lw=1.0))
    fig.tight_layout()
    paths = MC.save_fig(fig, "q3_15_flow", str(FIG_DIR))
    return {"name": "q3_15_flow", "purpose": "Q3 全流程示意：数据 → 预报构造 → 计划层 → 调整层 → 执行器 v2b → 物化与双轨验证",
            "data_source": ["Q3交付/manifest.sha256.json（口径）", "Q3交付/04_证据/组件哈希与环境指纹.md"],
            "key_values": {"stages": [b[1] for b in boxes] + ["物化与验证"], "note": "概念示意"},
            "script": "q3_fig_A_main.py"}, paths


def fig_q3_16(sub, seg, price, load, pv) -> dict:
    """0/6/12/18 决策时序示意。"""
    fig, ax = plt.subplots(figsize=(7.4, 2.9))
    ax.set_xlim(-0.7, 24.6); ax.set_ylim(0, 1); ax.axis("off")
    ax.annotate("", xy=(24.0, 0.30), xytext=(0.0, 0.30),
                arrowprops=dict(arrowstyle="-|>", color="#555555", lw=1.0))
    for h in (0, 6, 12, 18):
        ax.plot([h], [0.30], "o", ms=6, color=MC.PALETTE["grid"])
        ax.text(h, 0.22, "%d:00" % h, ha="center", fontsize=7.5)
    ax.text(24.0, 0.22, "24:00", ha="center", fontsize=7.5)
    ax.text(0, 0.72, "0:00 制定全天计划 $G^0$（用当时可得信息）", fontsize=6.8)
    ax.text(6, 0.60, "6:00 更新：只能改 6:00 之后", fontsize=6.8, ha="left")
    ax.text(12, 0.48, "12:00 更新：只能改 12:00 之后", fontsize=6.8, ha="left")
    ax.text(18, 0.36, "18:00 更新：只能改 18:00 之后", fontsize=6.8, ha="left")
    ax.text(0.4, 0.08, "红线：时间不可回溯——每个更新时点不得修改该时刻之前已执行的计划/取用",
            fontsize=6.6, color=MC.PALETTE["emer"])
    fig.tight_layout()
    paths = MC.save_fig(fig, "q3_16_rollout_timeline", str(FIG_DIR))
    return {"name": "q3_16_rollout_timeline",
            "purpose": "Q3 决策时序示意：0:00 计划 + 6/12/18 三个更新时点，且每次更新不得回溯修改此前已执行部分",
            "data_source": ["赛题 C 题问题 3 原文（0/6/12/18 预报时刻）"],
            "key_values": {"update_hours": [0, 6, 12, 18], "note": "概念示意"},
            "script": "q3_fig_A_main.py"}, paths


VOI_PATH = str(Path(r"D:\CMUCU\6对话\output\q3_voi_v2b\voi_v2b.json"))
VOI_NOTE = "6对话/output/q3_voi_v2b/voi_v2b.json（v2b 口径四臂，本线隔离重跑）"
FIGS = {"q3_01": fig_q3_01, "q3_02": fig_q3_02, "q3_03": fig_q3_03, "q3_04": fig_q3_04,
        "q3_05": fig_q3_05, "q3_06": fig_q3_06, "q3_07": fig_q3_07, "q3_08": fig_q3_08,
        "q3_09": fig_q3_09, "q3_10": fig_q3_10, "q3_12": fig_q3_12, "q3_14": fig_q3_14,
        "q3_15": fig_q3_15, "q3_16": fig_q3_16}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=None)
    a = ap.parse_args()
    MC.apply_style()
    if MC.verify_fonts().get("serif"):
        print("缺字闸门未过")
        return 2
    sub, seg, price, load, pv = _load()
    man = Manifest(root=str(FIG_DIR.parent), group=FIG_DIR.name)
    for nm in (a.only or list(FIGS)):
        e, paths = FIGS[nm](sub, seg, price, load, pv)
        man.add(name=e["name"], purpose=e["purpose"], data_source=e["data_source"],
                key_values=e["key_values"], script=e["script"])
        print("[%s] 出图 OK -> %s" % (nm, paths["png"]))
    print("manifest ->", man.write())
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
