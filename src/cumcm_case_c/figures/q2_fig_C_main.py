# -*- coding: utf-8 -*-
r"""Q2 Tier C 限度与稳健图（对话6 · 主口径）。

q2_11_forecast_caliber  ：预报/计划口径灵敏度（`Q2交付\04_证据\q2_forecast_scan*.json` + 裁决书对照表）
q2_12_irreducible_cost  ：费用的三段分解 —— 口径改进收益 vs 预报误差的**不可消除代价**（★ 与 ② 之差）
q2_13_pv_shortfall_vs_emergency：机制 —— 当日"实际低于预报的光伏缺额"↔ 当日紧急购电量（先验证相关再画）
q2_14_emergency_tail    ：紧急购电费的尾部集中（Lorenz + 前 N 天占比）

数据入口：`q2_data_causal.py`（凭证 sha256 先验后用）。所有数字现算或取自裁决书，禁旧口径。
"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import mpl_config as MC          # noqa: E402
import q2_data_causal as F       # noqa: E402
from fig_manifest import Manifest  # noqa: E402

FIG_DIR = Path(r"D:\CMUCU\6对话\output\figures\q2")
T, DT = F.T, F.DT
SCAN_DIR = F.DELIV / "04_证据"


def scan_map() -> dict[str, dict]:
    """把 9 份 `q2_forecast_scan*.json` 归一成 tag -> 记录。"""
    out: dict[str, dict] = {}
    for p in sorted(glob.glob(str(SCAN_DIR / "q2_forecast_scan*.json"))):
        d = json.loads(Path(p).read_text(encoding="utf-8"))
        for r in (d if isinstance(d, list) else [d]):
            if isinstance(r, dict) and r.get("tag") and r.get("total"):
                out[r["tag"]] = r
    return out


def nice_ylim(ax, vmax: float, *, head: float = 0.10) -> float:
    """纵轴取"漂亮"上限并显式给刻度，保证最高柱落在最后一个可见刻度之下。"""
    import math

    vmax = float(max(vmax, 0.0))
    if vmax <= 0:
        ax.set_ylim(0, 1.0); ax.set_yticks([0, 0.5, 1.0]); return 1.0
    mag = 10 ** math.floor(math.log10(vmax))
    top = mag
    for mult in (1, 1.25, 1.5, 2, 2.5, 3, 4, 5, 7.5, 10):
        top = mult * mag
        if top >= vmax * (1 + head):
            break
    ax.set_ylim(0, top)
    ticks = [0, top / 2, top]
    ax.set_yticks(ticks)
    ax.set_yticklabels([("%.1f" % v if top < 10 else "%.0f" % v) for v in ticks])
    return top


def pv_shortfall(led, inp) -> tuple[np.ndarray, np.ndarray]:
    """逐日（缺额光伏 kWh，当日紧急购电 kWh）。缺额 = 当日逐时段 max(预报−实际,0)·dt 之和。"""
    pv = inp["pv_kW"]
    n = len(pv)
    short = np.full(n, np.nan)
    for i in range(4, n):
        f = pv[i - 4:i].mean(axis=0)
        short[i] = float(np.sum(np.maximum(f - pv[i], 0.0)) * DT)
    return short, led["H"].sum(axis=1)


# ---------------------------------------------------------------------------
def fig_q2_11(led, inp) -> dict:
    sm = scan_map()
    items = [
        ("★ 主口径：过去4天均值×因果裕度", 13252341.09, "ours", None),
        ("① 均值点预报·裕度=0（同对象）", 14178004.00, "cmp", None),
        ("② 完全信息下界（不可执行）", 12254696.55, "bound", "\\\\\\\\"),
        ("④ 附件1 典型日曲线（题面口径）", 19043406.75, "cmp", None),
        ("过去 8 天同星期均值", sm["past-8-same-weekday MEAN"]["total"], "scan", None),
        ("过去 12 天同星期均值", sm["past-12-same-weekday MEAN"]["total"], "scan", None),
        ("最近 7 天均值", sm["last-7-days MEAN"]["total"], "scan", None),
        ("SAA K=12 情景（最近12天）", sm["SAA K=12 recent days (load known)"]["total"], "scan", None),
        ("SAA K=16 情景（最近16天）", sm["SAA K=16 recent days (load known)"]["total"], "scan", None),
        ("附件3 0:00 官方预报（Q3 输入）", sm["ATT3 0:00 official forecast (Q3 input!)"]["total"], "scan", None),
    ]
    items.sort(key=lambda x: x[1])
    y = np.arange(len(items))
    base = 13252341.09
    colors = {"ours": MC.PALETTE["grid"], "cmp": MC.PALETTE["baseline"],
              "bound": MC.PALETTE["curtail"], "scan": MC.PALETTE["pv"]}
    hatches = {"ours": "", "cmp": "////", "bound": "\\\\\\\\", "scan": "...."}
    fig, ax = plt.subplots(figsize=(7.4, 3.9))
    for i, (nm, v, kind, h) in enumerate(items):
        # 黑白可分：把 ③/对照 类改成"浅底 + 图案"，避免与主口径紫条在灰度上撞车
        col = colors[kind] if kind in ("ours", "scan") else "white"
        ax.barh(i, v / 1e6, height=0.62, color=col, alpha=0.95,
                hatch=hatches[kind] or (h or ""), edgecolor="#555555", lw=0.6)
        ax.text(v / 1e6 + 0.12, i, "%.2f（%+.1f%%）" % (v / 1e6, 100 * (v - base) / base),
                va="center", fontsize=6.2,
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.72, pad=0.4))
    ax.set_yticks(y); ax.set_yticklabels([it[0] for it in items], fontsize=6.4)
    ax.set_xlabel("全年购电费用（百万元）", fontsize=8.5)
    ax.set_xlim(0, max(it[1] for it in items) / 1e6 * 1.22)
    ax.axvline(base / 1e6, color=MC.PALETTE["grid"], lw=0.9, ls="--", alpha=0.7)
    ax.set_title("Q2 计划口径灵敏度（同数据、同储能参数、同结算规则；仅改计划阶段信息）",
                 fontsize=9, loc="left")
    ax.grid(axis="x", color=MC.PALETTE["bound"], lw=0.4, alpha=0.5)
    ax.text(0.995, 0.02, "斜纹 = 不可执行下界；虚线 = 主口径 13.25 百万元",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=6.0, color="#555555")
    fig.tight_layout()
    paths = MC.save_fig(fig, "q2_11_forecast_caliber", str(FIG_DIR))
    return {
        "name": "q2_11_forecast_caliber",
        "purpose": "Q2 计划口径灵敏度：在相同数据/储能参数/结算规则下，仅改变计划阶段可得信息（预报口径），"
                   "比较全年费用；含完全信息不可执行下界与题面典型日口径",
        "data_source": ["Q2交付/04_证据/q2_forecast_scan*.json（9 份扫描）",
                        "6对话/Q2最终裁决与可用数字_对话5到6对话.md §一（★①②④）"],
        "key_values": {nm: round(v, 2) for nm, v, _k, _h in items},
        "key_values_rel_pct": {nm: round(100 * (v - base) / base, 4) for nm, v, _k, _h in items},
        "script": "q2_fig_C_main.py",
    }, paths


# ---------------------------------------------------------------------------
def fig_q2_12(led, inp) -> dict:
    base, nomargin, bound, typical = 13252341.09, 14178004.00, 12254696.55, 19043406.75
    steps = [("附件1\n典型日口径", typical, None),
             ("→ 改用\n过去4天均值", nomargin, None),
             ("→ 加因果裕度\n（本文主口径）", base, None),
             ("（参考）\n完全信息下界", bound, None)]
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(7.4, 3.4),
                                  gridspec_kw={"width_ratios": [1.45, 1.0], "wspace": 0.30})
    x = np.arange(len(steps))
    # 标准"下降瀑布"：每段从上一步水平**悬垂**到本步水平
    # （此前底边位置算错：把 (本步−上一步) 当高度、又以本步为底，导致着色区间错位——豆包 2026-09-12 指出）
    ax.bar(0, typical / 1e6, width=0.62, color=MC.PALETTE["baseline"], alpha=0.85, hatch="//",
           edgecolor="white", lw=0.3)
    for i in (1, 2):
        prev_v, cur_v = steps[i - 1][1] / 1e6, steps[i][1] / 1e6
        ax.bar(i, prev_v - cur_v, bottom=cur_v, width=0.62,
               color=MC.PALETTE["grid"] if i == 2 else MC.PALETTE["pv"], alpha=0.9,
               edgecolor="white", lw=0.3)
        ax.plot([i - 1 + 0.31, i - 0.31], [prev_v] * 2, color=MC.PALETTE["bound"], lw=0.8, ls=":")
    ax.bar(3, bound / 1e6, width=0.62, color=MC.PALETTE["curtail"], alpha=0.7, hatch="\\\\")
    for i, (nm, v, _d) in enumerate(steps):
        ax.text(i, v / 1e6 * 1.01, "%.2f" % (v / 1e6), ha="center", va="bottom", fontsize=6.6)
    ax.set_xticks(x); ax.set_xticklabels([s[0] for s in steps], fontsize=5.8)
    ax.set_ylabel("全年购电费用（百万元）", fontsize=8.5)
    ax.set_ylim(0, typical / 1e6 * 1.18)
    ax.set_title("(a) 费用阶梯：口径改进的收益分两段", fontsize=8.8, loc="left")
    ax.grid(axis="y", color=MC.PALETTE["bound"], lw=0.4, alpha=0.5)

    # 标签过长会压住柱/越出画幅（本人 + 豆包 2026-09-13）→ 缩短标签，长解释移到面板标题
    gaps = [("典型日 → 4天均值", typical - nomargin),
            ("加因果裕度", nomargin - base),
            ("预报误差代价", base - bound)]
    yy = np.arange(len(gaps))[::-1]
    ax2.barh(yy, [g[1] / 1e4 for g in gaps], height=0.55,
             color=[MC.PALETTE["emer"], MC.PALETTE["grid"], MC.PALETTE["curtail"]],
             alpha=0.88, hatch=["", "", "\\\\"])
    for i, g in zip(yy, gaps):
        ax2.text(g[1] / 1e4 + 3, i, "%.0f 万元（%.2f%%）" % (g[1] / 1e4, 100 * g[1] / base),
                 va="center", fontsize=6.2,
                 bbox=dict(facecolor="white", edgecolor="none", alpha=0.72, pad=0.4))
    ax2.set_yticks(yy); ax2.set_yticklabels([g[0] for g in gaps], fontsize=6.0)
    ax2.set_xlabel("金额（万元；均为相对主口径的改善或代价）", fontsize=8.2)
    ax2.set_xlim(0, max(g[1] for g in gaps) / 1e4 * 1.5)
    ax2.set_title("(b) 三段分解（正数=相对主口径的金额）；末项=★ 与完全信息下界之差（下界不可执行）",
                  fontsize=7.8, loc="left")
    ax2.grid(axis="x", color=MC.PALETTE["bound"], lw=0.4, alpha=0.5)
    fig.tight_layout()
    paths = MC.save_fig(fig, "q2_12_irreducible_cost", str(FIG_DIR))
    return {
        "name": "q2_12_irreducible_cost",
        "purpose": "Q2 费用三段分解：改用过去 4 天均值口径的收益、加因果保守裕度的收益，以及★与完全信息"
                   "下界之差（预报误差的不可消除代价，下界不可执行）",
        "data_source": ["6对话/Q2最终裁决与可用数字_对话5到6对话.md §一", str(F.ART)],
        "key_values": {"typical_day_yuan": typical, "no_margin_yuan": nomargin,
                       "main_yuan": base, "perfect_info_bound_yuan": bound,
                       "gain_vs_typical_yuan": round(typical - nomargin, 2),
                       "gain_of_margin_yuan": round(nomargin - base, 2),
                       "irreducible_gap_yuan": round(base - bound, 2),
                       "irreducible_gap_pct": round(100 * (base - bound) / base, 4)},
        "script": "q2_fig_C_main.py",
    }, paths


# ---------------------------------------------------------------------------
def fig_q2_13(led, inp) -> dict:
    from scipy.stats import pearsonr, spearmanr

    short, Hd = pv_shortfall(led, inp)
    ok = ~np.isnan(short)
    x, y = short[ok], Hd[ok]
    rho = float(spearmanr(x, y).statistic)
    r = float(pearsonr(x, y).statistic)
    # 十分位分箱均值（仅在 x>0 的日子上做分箱，避免 0 堆积主导）
    qs = np.quantile(x, np.linspace(0, 1, 11))
    bx, by = [], []
    for a, b in zip(qs[:-1], qs[1:]):
        m = (x >= a) & (x <= b)
        if m.sum() >= 3:
            bx.append(float(x[m].mean())); by.append(float(y[m].mean()))

    fig, ax = plt.subplots(figsize=(7.4, 3.6))
    ax.scatter(x, y, s=6, color=MC.PALETTE["pv"], alpha=0.55, edgecolors="none",
               label="逐日（%d 天）" % len(x))
    ax.plot(bx, by, "-o", ms=3.6, lw=1.4, color=MC.PALETTE["emer"], label="十分位分箱均值")
    ax.set_xlabel("当日光伏缺额（实际低于预报的部分，kWh/日）", fontsize=8.5)
    ax.set_ylabel("当日紧急购电量（kWh/日）", fontsize=8.5)
    ax.set_title("Q2 机制：预报偏低造成的当日光伏缺额 ↔ 紧急购电（Spearman ρ=%.3f，Pearson r=%.3f）"
                 % (rho, r), fontsize=9, loc="left")
    ax.legend(loc="upper left", fontsize=6.6, framealpha=0.9)
    ax.grid(color=MC.PALETTE["bound"], lw=0.4, alpha=0.4)
    ax.text(0.995, 0.03, "缺额 = Σ max(预报−实际, 0)·(1/6 h)；紧急购电为结算口径（5 倍价）",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=6.0, color="#555555")
    fig.tight_layout()
    paths = MC.save_fig(fig, "q2_13_pv_shortfall_vs_emergency", str(FIG_DIR))
    return {
        "name": "q2_13_pv_shortfall_vs_emergency",
        "purpose": "Q2 机制验证：当日'实际低于预报'的光伏缺额越大，当日紧急购电越多（散点 + 十分位分箱均值）",
        "data_source": [str(F.ART), "B对话/clean/attachment2_pv.csv（实际光伏）",
                        "5对话/交付说明_Q2_因果裕度非预见.md §1（预报构造）"],
        "key_values": {"n_days": int(len(x)), "spearman_rho": round(rho, 4), "pearson_r": round(r, 4),
                       "shortfall_kWh_sum": round(float(x.sum()), 4),
                       "H_kWh_sum": round(float(y.sum()), 4),
                       "bin_x": [round(v, 1) for v in bx], "bin_y": [round(v, 2) for v in by]},
        "script": "q2_fig_C_main.py",
    }, paths


# ---------------------------------------------------------------------------
def fig_q2_14(led, inp) -> dict:
    J = np.sort(led["J_emg_day"])[::-1]
    tot = float(J.sum())
    n = len(J)
    cum = np.cumsum(J) / tot
    marks = [5, 10, 17, 34, 50]
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(7.4, 3.4),
                                  gridspec_kw={"width_ratios": [1.0, 1.15], "wspace": 0.30})
    ax.plot(np.arange(1, n + 1) / n * 100, cum * 100, "-", color=MC.PALETTE["emer"], lw=1.5)
    ax.plot([0, 100], [0, 100], ":", color=MC.PALETTE["bound"], lw=1.0)
    for k in marks:
        ax.plot([k / n * 100], [cum[k - 1] * 100], "o", ms=3.6, color=MC.PALETTE["emer"],
                markeredgecolor="white", markeredgewidth=0.4)
    ax.annotate("前 20%% 天数\n占 %.1f%% 紧急费" % (cum[int(0.2 * n) - 1] * 100),
                xy=(20, cum[int(0.2 * n) - 1] * 100), xytext=(35, 55), fontsize=6.4,
                arrowprops=dict(arrowstyle="->", color="#666666", lw=0.7))
    ax.set_xlabel("按日紧急费降序排列的累计天数占比 (%)", fontsize=8.5)
    ax.set_ylabel("累计紧急费占比 (%)", fontsize=8.5)
    ax.set_xlim(0, 100); ax.set_ylim(0, 103)
    ax.set_title("(a) 尾部集中（Lorenz 型）", fontsize=8.8, loc="left")
    ax.grid(color=MC.PALETTE["bound"], lw=0.4, alpha=0.4)

    t = F.top_days(led, k=10)
    labels = [d[5:] for d in t["dates"]]
    ax2.bar(np.arange(len(labels)), np.array(t["J_emg"]) / 1e4, width=0.62,
            color=MC.PALETTE["emer"], alpha=0.9)
    for i, v in enumerate(t["J_emg"]):
        ax2.text(i, v / 1e4 * 1.02, "%.1f" % (v / 1e4), ha="center", va="bottom", fontsize=5.8)
    ax2.set_xticks(np.arange(len(labels)))
    ax2.set_xticklabels(labels, fontsize=6.0, rotation=45, ha="right")
    ax2.set_ylabel("当日紧急购电费（万元/日）", fontsize=8.5)
    nice_ylim(ax2, float(max(t["J_emg"]) / 1e4))     # 避免最高柱超出可见刻度（豆包 2026-09-12 指出）
    ax2.set_title("(b) 紧急费最高的 10 天（合计占全年 %.1f%%）" % (sum(t["J_emg"]) / tot * 100),
                  fontsize=8.8, loc="left")
    ax2.grid(axis="y", color=MC.PALETTE["bound"], lw=0.4, alpha=0.5)
    fig.suptitle("Q2 紧急购电费的尾部结构：Σ=%.2f 万元，%d 天中前 %d 天占 %.1f%%"
                 % (tot / 1e4, n, 5, cum[4] * 100), fontsize=9.4, y=0.99)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    paths = MC.save_fig(fig, "q2_14_emergency_tail", str(FIG_DIR))
    return {
        "name": "q2_14_emergency_tail",
        "purpose": "Q2 紧急购电费的尾部集中：Lorenz 型累计曲线 + 最高的 10 天（含前 5/10/17/34/50 天占比）",
        "data_source": [str(F.ART) + "（J_emg_day）"],
        "key_values": {"total_yuan": round(tot, 4), "n_days": n,
                       "top_shares_pct": {str(k): round(float(cum[k - 1] * 100), 4) for k in marks},
                       "top20pct_days_share_pct": round(float(cum[int(0.2 * n) - 1] * 100), 4),
                       "top10_days": t["dates"], "top10_J_emg_yuan": [round(v, 2) for v in t["J_emg"]]},
        "script": "q2_fig_C_main.py",
    }, paths


FIGS = {"q2_11": fig_q2_11, "q2_12": fig_q2_12, "q2_13": fig_q2_13, "q2_14": fig_q2_14}


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=None)
    a = ap.parse_args()
    MC.apply_style()
    if MC.verify_fonts().get("serif"):
        print("缺字闸门未过"); return 2
    led = F.load_main()
    inp = F.load_inputs(led, verbose=False)
    man = Manifest(root=str(FIG_DIR.parent), group=FIG_DIR.name)
    for nm in (a.only or list(FIGS)):
        e, paths = FIGS[nm](led, inp)
        man.add(name=e["name"], purpose=e["purpose"], data_source=e["data_source"],
                key_values=e["key_values"], script=e["script"])
        print("[%s] 出图 OK -> %s" % (nm, paths["png"]))
    print("manifest ->", man.write())
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
