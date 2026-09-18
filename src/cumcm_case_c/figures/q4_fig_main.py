# -*- coding: utf-8 -*-
r"""Q4 图件（对话6 · 交付口径：附件4 波动电价）。

清单见 `Q4交付\Q4_最终产物清单与交接.md` §六：
  q4_01_price_caliber  附件1 典型日 vs 附件4 全年波动（折线 + 5/50/95 分位带）
  q4_02_plan_heatmap   Q4-2 计划购电量热力图（334×144）
  q4_03_soc_price_7d   代表 7 天：SOC（逐段重建）+ 附件4 价格双轴
  q4_04_price_four     四种价格口径费用对比（I/II/III/IV）
  q4_05_cf_2x2         2×2 反事实（Q4-2 与 Q4-3 两问并列）
  q4_06_effect_split   价格效应 vs 重优化（分块）

用法：$env:PYTHONPATH="D:\CMUCU\rag\.deps"; $env:PYTHONIOENCODING='utf-8'
      & $py "D:\CMUCU\6对话\code\q4_fig_main.py" [--only q4_01 ...]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import mpl_config as MC          # noqa: E402
import q4_data_frozen as Q       # noqa: E402
from fig_manifest import Manifest  # noqa: E402

FIG_DIR = Path(r"D:\CMUCU\6对话\output\figures\q4")
T, DT = Q.T, Q.DT
DAYS7 = ["2025-03-20", "2025-05-15", "2025-06-21", "2025-07-15",
         "2025-09-23", "2025-10-15", "2025-12-21"]


def _load():
    ck = Q.load_checkpoint(verbose=False)
    a4 = Q.load_attachment4(verbose=False)
    a1 = Q.load_attachment1(verbose=False)
    cf2 = Q.load_evidence_json(Q.CF2, verbose=False)
    cf3 = Q.load_evidence_json(Q.CF3, verbose=False)
    blk = Q.load_evidence_json(Q.BLK, verbose=False)
    cal = Q.load_evidence_json(Q.CAL, verbose=False)
    return ck, a4, a1, cf2, cf3, blk, cal


def _haxis(ax, *, label: str = "时刻 (h)", step: int = 2):
    ax.set_xlim(0, 24)
    ax.set_xticks(list(range(0, 25, step)))
    ax.set_xticklabels(["%d:00" % h for h in range(0, 25, step)], fontsize=7)
    if label:
        ax.set_xlabel(label, fontsize=8.5)


def _nice_ylim(ax, vmax, *, head=0.12):
    import math
    vmax = float(max(vmax, 0.0))
    if vmax <= 0:
        ax.set_ylim(0, 1.0); ax.set_yticks([0, .5, 1.]); return
    mag = 10 ** math.floor(math.log10(vmax))
    top = mag
    for m in (1, 1.25, 1.5, 2, 2.5, 3, 4, 5, 7.5, 10):
        top = m * mag
        if top >= vmax * (1 + head):
            break
    ax.set_ylim(0, top)
    ax.set_yticks([0, top / 2, top])
    ax.set_yticklabels([("%.1f" % v if top < 10 else "%.0f" % v) for v in (0, top / 2, top)])


# ---------------------------------------------------------------- Q4-1
def fig_q4_01(ck, a4, a1, cf2, cf3, blk, cal) -> dict:
    h = np.arange(T) * DT
    q05, q50, q95 = a4["quantiles"][0], a4["quantiles"][1], a4["quantiles"][2]
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(7.4, 3.5),
                                  gridspec_kw={"width_ratios": [1.0, 1.15], "wspace": 0.28})
    ax.fill_between(h, q05, q95, color=MC.PALETTE["price"], alpha=0.16, lw=0,
                    label="附件4：5–95% 分位带（365 天）")
    ax.plot(h, q50, "-", color=MC.PALETTE["price"], lw=1.4, label="附件4：中位（P50）")
    ax.plot(h, a1["price"], "--", color=MC.PALETTE["net"], lw=1.5, label="附件1：典型日曲线")
    # 窄面板里 13 个刻度会挤成一团（本人 2026-09-13 目视）→ 改为 4 小时一档
    _haxis(ax, step=4, label="时刻")     # 刻度是 0:00…24:00，故不再写单位 (h)
    ax.set_ylabel("电价 (元/kWh)", fontsize=8.5)
    ax.set_title("(a) 典型日 vs 波动电价（按时刻聚合）", fontsize=8.8, loc="left")
    ax.legend(loc="upper left", fontsize=6.2, framealpha=0.9)
    ax.grid(color=MC.PALETTE["bound"], lw=0.4, alpha=0.4)
    # (b) 逐日均价 + min~max 带（只看 Q4 窗口 334 天）
    price = a4["window"]
    n = price.shape[0]
    mean_d, min_d, max_d = price.mean(axis=1), price.min(axis=1), price.max(axis=1)
    x = np.arange(n)
    ax2.fill_between(x, min_d, max_d, color=MC.PALETTE["load"], alpha=0.16, lw=0,
                     label="附件4：日 min–max")
    ax2.plot(x, mean_d, "-", color=MC.PALETTE["load"], lw=1.0, label="附件4：日均价")
    ax2.axhline(float(a1["price"].mean()), ls="--", color=MC.PALETTE["net"], lw=1.2,
                label="附件1：日均 %.3f 元/kWh" % a1["price"].mean())
    ax2.set_xlim(0, n - 1)
    ax2.set_ylabel("电价 (元/kWh)", fontsize=8.5)
    ax2.set_xlabel("Q4 评估期（2025-02-01 ~ 12-31，共 %d 天）" % n, fontsize=8)
    ax2.set_title("(b) 波动电价的日尺度波动", fontsize=8.8, loc="left")
    ax2.legend(loc="upper left", fontsize=6.2, framealpha=0.9)
    ax2.grid(color=MC.PALETTE["bound"], lw=0.4, alpha=0.4)
    fig.tight_layout()
    paths = MC.save_fig(fig, "q4_01_price_caliber", str(FIG_DIR))
    return {"name": "q4_01_price_caliber",
            "purpose": "Q4 价格口径：附件1 典型日曲线 vs 附件4 逐日逐时段波动电价（5/50/95 分位带 + 日尺度波动）",
            "data_source": [str(Q.A1), str(Q.A4)],
            "key_values": {"att1_mean": round(float(a1["price"].mean()), 6),
                           "att1_max": round(float(a1["price"].max()), 6),
                           # 附件4 全量与分位按 365 天算；费用与面板(b) 才是 334 天窗口（审计 R10 发现 3）
                           "att4_mean_365d": round(float(a4["price"].mean()), 6),
                           "att4_max_365d": round(float(a4["price"].max()), 6),
                           "att4_min_365d": round(float(a4["price"].min()), 6),
                           "p05_p50_p95_at_20h_365d": [round(float(v), 6) for v in
                                                       (q05[120], q50[120], q95[120])],
                           "n_days_window": int(n)},
            "script": "q4_fig_main.py"}, paths


# ---------------------------------------------------------------- Q4-2
def fig_q4_02(ck, a4, a1, cf2, cf3, blk, cal) -> dict:
    G = ck["G"]
    pos = G[G > 0]
    # 色标上限取整百（豆包 2026-09-13 指出：自动刻度最大 1400 与标题写的
    # "≥1440 最深色" 不一致）→ 上限圆整到 100，并显式给出等分刻度，末刻度 = 上限。
    vmax = float(np.ceil((min(np.percentile(pos, 97) if pos.size else 1.0, 1500.0)) / 100.0) * 100.0)
    vmax = max(vmax, 100.0)
    fig, (ax, axd) = plt.subplots(2, 1, figsize=(7.4, 6.0),
                                  gridspec_kw={"height_ratios": [3.0, 1.0], "hspace": 0.22})
    mesh = ax.imshow(G, aspect="auto", cmap="Blues", vmin=0, vmax=vmax,
                     interpolation="nearest", extent=[0, 24, len(ck["d"]), 0])
    ax.set_xlim(0, 24); ax.set_ylim(len(ck["d"]), 0)
    ax.set_ylabel("日期（2025-02-01 → 12-31，%d 天）" % len(ck["d"]), fontsize=8.5)
    ax.set_title("(a) Q4-2 计划购电量 $G$ 热力图（附件4 价下；色标上限 %.0f，超出按最深色）" % vmax,
                 fontsize=9, loc="left")
    yt = [i for i, ds in enumerate(ck["date"]) if ds[8:10] == "01"]
    ax.set_yticks(yt); ax.set_yticklabels([ck["date"][i][:7] for i in yt], fontsize=6.6)
    ax.tick_params(axis="y", length=0)
    _haxis(ax, label="")
    cb = fig.colorbar(mesh, ax=ax, pad=0.012, fraction=0.032)
    cb.set_label("计划购电量 (kWh / 10 min)", fontsize=6.8)
    cb.ax.tick_params(labelsize=6.4)
    ticks = np.linspace(0.0, vmax, 5)
    cb.set_ticks(ticks)
    cb.set_ticklabels(["%.0f" % t for t in ticks])
    qd = G.sum(axis=1)
    x = np.arange(len(qd))
    axd.fill_between(x, 0, qd, color=MC.PALETTE["grid"], alpha=0.55, lw=0)
    axd.plot(x, qd, "-", color=MC.PALETTE["grid"], lw=0.7)
    axd.set_xlim(0, len(qd) - 1)
    axd.set_ylabel("日计划购电量\n(kWh/日)", fontsize=7.5)
    axd.set_xlabel("全年序日（0 = 2025-02-01）", fontsize=8)
    axd.set_title("(b) 逐日计划购电量（Σ={:,.0f} kWh）".format(qd.sum()), fontsize=9, loc="left")
    axd.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda v, _p: "{:,.0f}".format(v)))
    # 红线 B6：最高柱须低于最大可见刻度（峰值 100,038 > 100,000 的旧刻度会看似截断）
    axd.set_ylim(0, 120000)
    axd.set_yticks([0, 40000, 80000, 120000])
    axd.grid(axis="y", color=MC.PALETTE["bound"], lw=0.4, alpha=0.5)
    fig.tight_layout(rect=(0, 0, 1, 0.985))
    paths = MC.save_fig(fig, "q4_02_plan_heatmap", str(FIG_DIR))
    return {"name": "q4_02_plan_heatmap",
            "purpose": "Q4-2 计划购电量结构：334 天 × 144 区间热力图 + 逐日合计（附件4 波动价下的计划层输出）",
            "data_source": [str(Q.CKPT) + "（days[i].G）"],
            "key_values": {"n_days": int(G.shape[0]), "QG_kWh": round(float(G.sum()), 4),
                           "max_day_QG_kWh": round(float(qd.max()), 4),
                           "argmax_date": ck["date"][int(np.argmax(qd))],
                           "vmax_display": round(vmax, 2)},
            "script": "q4_fig_main.py"}, paths


# ---------------------------------------------------------------- Q4-3
def fig_q4_03(ck, a4, a1, cf2, cf3, blk, cal) -> dict:
    idx = [ck["date"].index(d) for d in DAYS7]
    fig = plt.figure(figsize=(7.6, 4.6))
    gs = fig.add_gridspec(2, 4, hspace=0.66, wspace=0.58)
    axes = [fig.add_subplot(gs[0, j]) for j in range(4)] + \
           [fig.add_subplot(gs[1, j]) for j in range(3)]
    ax_note = fig.add_subplot(gs[1, 3])      # 右下空位改成读图说明（豆包 2026-09-13 提示留白失衡）
    ax_note.axis("off")
    key = {}
    for k, (ax, i) in enumerate(zip(axes, idx)):
        ds = ck["date"][i]
        s = Q.soc_path_1day(ck, i)
        price = a4["window"][i]
        ax.plot(np.arange(T + 1) * DT, s, "-", color=MC.PALETTE["soc"], lw=1.2)
        ax.axhline(1200, color=MC.PALETTE["emer"], lw=0.8, ls="--")
        ax.axhline(10800, color=MC.PALETTE["grid"], lw=0.8, ls="--")
        ax.set_ylim(0, 12600)
        ax.set_xlim(0, 24); ax.set_xticks([0, 6, 12, 18, 24])
        ax.set_xticklabels(["0", "6", "12", "18", "24"], fontsize=5.6)
        if k >= 4:                            # 底行统一给横轴名称与单位
            ax.set_xlabel("时刻 (h)", fontsize=6.6)
        ax.tick_params(axis="y", labelsize=5.6)
        ax.set_title(ds, fontsize=6.8, loc="left")
        ax.grid(color=MC.PALETTE["bound"], lw=0.3, alpha=0.4)
        axb = ax.twinx()
        axb.plot(np.arange(T) * DT + DT / 2, price, ":", color=MC.PALETTE["price"], lw=0.9)
        axb.set_ylim(0, float(price.max()) * 2.2)
        axb.tick_params(axis="y", labelsize=5.4, colors=MC.PALETTE["price"])
        if k % 4 == 0:
            ax.set_ylabel("SOC (kWh)", fontsize=6.4)
        # 右轴刻度/标签只在"每行最后一个面板"显示：第一行是 k=3，第二行只剩 3 个面板故为 k=6
        # （豆包 2026-09-13 指出底行原本完全没有右轴刻度数字）
        if k in (3, 6):
            axb.set_ylabel("电价 (元/kWh)", fontsize=6.2, color=MC.PALETTE["price"])
        else:
            axb.tick_params(labelright=False)
        key[ds] = {"S0": round(float(ck["S0"][i]), 3), "S1": round(float(ck["S1"][i]), 3),
                   "soc_min": round(float(s[1:].min()), 3), "soc_max": round(float(s[1:].max()), 3),
                   "price_max": round(float(price.max()), 4), "price_min": round(float(price.min()), 4),
                   "H_kWh": round(float(ck["H"][i].sum()), 3)}
    ax_note.text(0.0, 0.86, "读图说明", fontsize=6.6, weight="bold", va="top")
    ax_note.text(0.0, 0.70,
                 "实线：SOC（左轴，kWh）\n"
                 "点线：电价（右轴，元/kWh）\n"
                 "虚线：SOC 上下限\n"
                 "　　　1200 / 10800 kWh\n"
                 "SOC 由 C/D 与 η=0.9 重建，\n"
                 "日界取自 checkpoint，\n"
                 "重建残差 ≤1e-6 kWh",
                 fontsize=5.3, va="top", linespacing=1.55, color="#444444")
    fig.suptitle("Q4-2 代表 7 天：SOC 轨迹（实线，左轴；由 C/D 与 η=0.9 重建）与附件4 实时电价（点线，右轴）",
                 fontsize=9.0, y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.945))
    paths = MC.save_fig(fig, "q4_03_soc_price_7d", str(FIG_DIR))
    return {"name": "q4_03_soc_price_7d",
            "purpose": "Q4-2 代表 7 天的 SOC 轨迹与当日实时电价（双轴）；SOC 逐段由 C/D 与 η=0.9 重建，"
                       "日界两端取自 checkpoint，重建残差 ≤1e-6 kWh",
            "data_source": [str(Q.CKPT), str(Q.A4)],
            "key_values": key,
            "script": "q4_fig_main.py"}, paths


def fig_q4_04(ck, a4, a1, cf2, cf3, blk, cal) -> dict:
    """四种"计划价格口径"的费用对比（I 主口径 / II 上周同日 / III 典型日 / IV 同周4周）。"""
    labels = ["I 主口径\n当日附件4 价", "II 上周\n同日价", "III 典型日价\n（附件1）", "IV 同周\n4 周价"]
    vals = [float(cal["I"]), float(cal["II"]), float(cal["III"]), float(cal["IV"])]
    base = vals[0]
    ref = float(cal["C_att1"])          # Q2 基线：附件1 计划 + 附件1 结算（价格水平不同）
    cols = [MC.PALETTE["grid"], MC.PALETTE["pv"], MC.PALETTE["curtail"], MC.PALETTE["net"]]
    hat = ["", "////", "\\\\\\\\", "...."]
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.5),
                             gridspec_kw={"width_ratios": [1.55, 1.0], "wspace": 0.40})

    # (a) 绝对费用（零基，不截断纵轴）
    ax = axes[0]
    x = np.arange(len(vals))
    ax.bar(x, [v / 1e6 for v in vals], width=0.62, color=cols, alpha=0.92, hatch=hat,
           edgecolor="white", lw=0.5)
    for i, v in enumerate(vals):
        ax.text(i, v / 1e6 + 0.10, "%.3f" % (v / 1e6), ha="center", va="bottom", fontsize=6.4)
    ax.axhline(ref / 1e6, ls="--", lw=1.1, color=MC.PALETTE["emer"])
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=6.6)
    ax.set_ylabel("全年费用（百万元）", fontsize=8.2)
    top = max(vals) / 1e6 * 1.18
    ax.set_ylim(0, top)
    # 参考线说明改放柱顶留白区（豆包 2026-09-13：原位置压住 I、II 号柱体上部）
    ax.text(-0.48, top * 0.975, "红色虚线 = Q2 基线 %.3f 百万元（附件1 价结算，仅参考）" % (ref / 1e6),
            ha="left", va="top", fontsize=5.8, color=MC.PALETTE["emer"],
            bbox=dict(facecolor="white", edgecolor="none", alpha=0.92, pad=0.5))
    ax.set_title("(a) 全年费用（纵轴零基）", fontsize=8.6, loc="left")
    ax.grid(axis="y", color=MC.PALETTE["bound"], lw=0.4, alpha=0.5)

    # (b) 相对主口径 I 的偏差（%，放大差异）
    axb = axes[1]
    xx = np.arange(3)
    dv = [100.0 * (vals[i] - base) / base for i in (1, 2, 3)]
    axb.bar(xx, dv, width=0.56, color=cols[1:], alpha=0.92, hatch=hat[1:],
            edgecolor="white", lw=0.5)
    for i, v in enumerate(dv):
        axb.text(i, v + 0.05, "%+.3f%%" % v, ha="center", va="bottom", fontsize=6.2)
    axb.axhline(0.0, color=MC.PALETTE["bound"], lw=0.8)
    dref = 100.0 * (ref - base) / base
    axb.axhspan(dref, 0.0, color=MC.PALETTE["emer"], alpha=0.055, lw=0)   # 淡底色带代替长文字
    axb.axhline(dref, ls="--", lw=1.1, color=MC.PALETTE["emer"])
    axb.text(-0.62, dref + 0.14, "Q2 基线 %.2f%%" % dref,
             ha="left", va="bottom", fontsize=5.7, color=MC.PALETTE["emer"],
             bbox=dict(facecolor="white", edgecolor="none", alpha=0.92, pad=0.5))
    axb.set_xticks(xx); axb.set_xticklabels(["II", "III", "IV"], fontsize=7.0)
    axb.set_ylabel("相对主口径 I 的偏差（%）", fontsize=8.2)
    axb.set_xlim(-0.68, 2.70)
    # 红线 B6：+1.057% 的柱不得越过最大可见刻度（原 ylim 顶端仅 1.6，刻度到 1 为止）
    axb.set_ylim(min(dref * 1.12, -0.4), 2.0)
    axb.set_yticks([-4, -3, -2, -1, 0, 1, 2])
    axb.set_title("(b) 价格信息价值（相对 I）", fontsize=8.6, loc="left")
    axb.grid(axis="y", color=MC.PALETTE["bound"], lw=0.4, alpha=0.5)

    fig.suptitle("Q4-2 四种计划价格口径（结算一律用附件4 当日实际价）", fontsize=9.2, y=0.99)
    fig.text(0.5, 0.015, "II/III/IV 为「用错价格排计划、按真价结算」的价格信息价值；"
                         "红色虚线＝Q2 基线（附件1 价结算，比 I 低 %.2f%%，价格水平效应），两者不可相互替代。"
                         % abs(dref),
             ha="center", fontsize=5.8, color="#555555")
    fig.tight_layout(rect=(0, 0.045, 1, 0.955))
    paths = MC.save_fig(fig, "q4_04_price_four", str(FIG_DIR))
    return {"name": "q4_04_price_four",
            "purpose": "Q4-2 四种计划价格口径的费用对比（I 主口径当日价 / II 上周同日价 / III 典型日价 / IV 同周4周价），"
                       "并标出 Q2 基线（价格区制不同，仅参考）",
            "data_source": [str(Q.CAL), "Q4交付/03_论文素材/三方共验_Q4交付件_裁定.md（口径定义）"],
            "key_values": {"I_yuan": round(float(cal["I"]), 4), "II_yuan": round(float(cal["II"]), 4),
                           "III_yuan": round(float(cal["III"]), 4), "IV_yuan": round(float(cal["IV"]), 4),
                           "dII_pct": round(float(cal["dII"]), 6), "dIII_pct": round(float(cal["dIII"]), 6),
                           "dIV_pct": round(float(cal["dIV"]), 6),
                           "C_att1_reference_yuan": round(float(cal["C_att1"]), 4),
                           "note": "I/II/III/IV 定义取自三方共验裁定的第 34 行"},
            "script": "q4_fig_main.py"}, paths


def fig_q4_05(ck, a4, a1, cf2, cf3, blk, cal) -> dict:
    """2×2 反事实：两问并列（Q4-2 与 Q4-3）。"""
    def cells(c, keys):
        return [[c[keys[0]]["total" if "total" in c[keys[0]] else "J_cash"],
                 c[keys[1]]["total" if "total" in c[keys[1]] else "J_cash"]],
                [c[keys[2]]["total" if "total" in c[keys[2]] else "J_cash"],
                 c[keys[3]]["total" if "total" in c[keys[3]] else "J_cash"]]]
    M2 = cells(cf2["cells"], ["G1P1", "G1P4", "G4P1", "G4P4"])
    M3 = cells(cf3["cells"], ["plan1_settle1", "plan1_settle4", "plan4_settle1", "plan4_settle4"])
    fig, axes = plt.subplots(1, 2, figsize=(7.6, 4.0))
    fig.subplots_adjust(left=0.085, right=0.975, top=0.795, bottom=0.165, wspace=0.34)
    for ax, M, tag, pe, re_ in (
            (axes[0], M2, "(a) Q4-2（E1 执行器）", cf2["price_effect"], cf2["reopt_effect"]),
            (axes[1], M3, "(b) Q4-3（v2b 执行器）", cf3["price_effect"], cf3["reopt_effect"])):
        base = M[0][0]
        ax.set_xlim(0, 2); ax.set_ylim(0, 2)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.set_xticks([0.5, 1.5])
        ax.set_xticklabels(["结算价\n附件1", "结算价\n附件4"], fontsize=6.8)
        ax.set_yticks([1.5, 0.5])
        ax.set_yticklabels(["计划价\n附件1", "计划价\n附件4"], fontsize=6.8)
        ax.tick_params(length=0)
        ax.set_title("%s\n价格效应 %+.1f 万｜重优化 %+.1f 万" % (tag, pe / 1e4, re_ / 1e4),
                     fontsize=7.6, linespacing=1.6, pad=6)
        for i in range(2):
            for j in range(2):
                v = M[i][j]
                fc = "#EDE7F6" if (i == 0 and j == 0) else ("#FBE3DA" if (i == 1 and j == 1) else "#F5F5F5")
                ax.add_patch(plt.Rectangle((j, 1 - i), 1, 1, facecolor=fc, edgecolor="#888888", lw=0.8))
                ax.text(j + 0.5, 1 - i + 0.68, "%.4f 百万元" % (v / 1e6), ha="center", fontsize=7.2)
                ax.text(j + 0.5, 1 - i + 0.44, "%+.3f%%（相对左上）" % (100 * (v - base) / base),
                        ha="center", fontsize=6.2, color="#555555")
                if (i == 0 and j == 0) or (i == 1 and j == 1):
                    ax.text(j + 0.5, 1 - i + 0.19,
                            "本问基线" if i == 0 else "本问交付值",
                            ha="center", fontsize=6.0,
                            color=("#4A3B8F" if i == 0 else "#B4553A"))
    fig.suptitle("Q4 价格区制反事实 2×2：左上＝本问基线，右下＝本问交付值", fontsize=9.2, y=0.985)
    fig.text(0.5, 0.075, "附件1＝典型日价（全年常数），附件4＝当日实际价",
             ha="center", fontsize=5.9, color="#555555")
    fig.text(0.5, 0.028, "两组基线分属不同问：(a) Q2 主口径 13,252,341.09 元，(b) Q3 v2 13,120,194.06 元；"
                         "组内可比，格值不可跨组横向比较。",
             ha="center", fontsize=5.9, color="#555555")
    paths = MC.save_fig(fig, "q4_05_cf_2x2", str(FIG_DIR))
    return {"name": "q4_05_cf_2x2",
            "purpose": "Q4 价格区制 2×2 反事实（Q4-2 与 Q4-3 并列）：左上=基线、右下=交付值，"
                       "并给出价格环境效应与重优化效应",
            "data_source": [str(Q.CF2), str(Q.CF3)],
            "key_values": {"Q4_2_cells_yuan": {"G1P1": round(M2[0][0], 4), "G1P4": round(M2[0][1], 4),
                                              "G4P1": round(M2[1][0], 4), "G4P4": round(M2[1][1], 4)},
                           "Q4_3_cells_yuan": {"plan1_settle1": round(M3[0][0], 4),
                                              "plan1_settle4": round(M3[0][1], 4),
                                              "plan4_settle1": round(M3[1][0], 4),
                                              "plan4_settle4": round(M3[1][1], 4)},
                           "Q4_2_price_effect": round(float(cf2["price_effect"]), 4),
                           "Q4_2_reopt_effect": round(float(cf2["reopt_effect"]), 4),
                           "Q4_3_price_effect": round(float(cf3["price_effect"]), 4),
                           "Q4_3_reopt_effect": round(float(cf3["reopt_effect"]), 4)},
            "script": "q4_fig_main.py"}, paths


def fig_q4_06(ck, a4, a1, cf2, cf3, blk, cal) -> dict:
    """价格效应 vs 重优化（按 4 个时段块）。"""
    blocks, ep, er = blk["blocks"], blk["eff_price"], blk["eff_reopt"]
    x = np.arange(len(blocks))
    fig, ax = plt.subplots(figsize=(7.4, 3.4))
    ax.bar(x - 0.19, np.array(ep) / 1e4, width=0.36, color=MC.PALETTE["price"], alpha=0.9,
           label="① 价格环境效应（同计划换价）")
    ax.bar(x + 0.19, np.array(er) / 1e4, width=0.36, color=MC.PALETTE["grid"], alpha=0.9,
           hatch="////", edgecolor="white", lw=0.3, label="② 重优化效应（同价换计划）")
    for i in range(len(blocks)):
        ax.text(i - 0.19, ep[i] / 1e4 + (1.2 if ep[i] >= 0 else -1.2), "%.1f" % (ep[i] / 1e4),
                ha="center", va="bottom" if ep[i] >= 0 else "top", fontsize=6.0)
        ax.text(i + 0.19, er[i] / 1e4 + (1.2 if er[i] >= 0 else -1.2), "%.1f" % (er[i] / 1e4),
                ha="center", va="bottom" if er[i] >= 0 else "top", fontsize=6.0)
    ax.axhline(0, color=MC.PALETTE["bound"], lw=0.8)
    ax.set_xticks(x); ax.set_xticklabels(blocks, fontsize=7.2)
    ax.set_xlabel("时段块 (h)", fontsize=8.5)
    ax.set_ylabel("相对 Q2 基线的增量（万元）", fontsize=8.5)
    ax.set_title("Q4-2 价格效应与重优化的时段分解（合计：价格 %+.1f 万 / 重优化 %+.1f 万）"
                 % (sum(ep) / 1e4, sum(er) / 1e4), fontsize=8.8, loc="left")
    # 红线 B6：最高柱 +30.4 万与最低柱 −30.7 万都要落在可见刻度内（±40 万）
    ax.set_ylim(-40.0, 40.0)
    ax.set_yticks([-40, -30, -20, -10, 0, 10, 20, 30, 40])
    ax.text(0.015, 0.975, "①+② = +59.81 万 = Q4-2 相对 Q2 基线的总差",
            transform=ax.transAxes, ha="left", va="top", fontsize=5.8, color="#555555",
            bbox=dict(facecolor="white", edgecolor="none", alpha=0.90, pad=0.5))
    ax.legend(loc="lower left", fontsize=6.2, framealpha=0.92)
    ax.grid(axis="y", color=MC.PALETTE["bound"], lw=0.4, alpha=0.5)
    fig.tight_layout()
    paths = MC.save_fig(fig, "q4_06_effect_split", str(FIG_DIR))
    return {"name": "q4_06_effect_split",
            "purpose": "Q4-2 价格环境效应与重优化效应的时段分解（00-06 / 06-12 / 12-18 / 18-24）",
            "data_source": [str(Q.BLK)],
            "key_values": {"blocks": blocks,
                           "eff_price_yuan": [round(float(v), 4) for v in ep],
                           "eff_reopt_yuan": [round(float(v), 4) for v in er],
                           "total_price_yuan": round(float(sum(ep)), 4),
                           "total_reopt_yuan": round(float(sum(er)), 4)},
            "script": "q4_fig_main.py"}, paths


FIGS = {"q4_01": fig_q4_01, "q4_02": fig_q4_02, "q4_03": fig_q4_03,
        "q4_04": fig_q4_04, "q4_05": fig_q4_05, "q4_06": fig_q4_06}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--out", default=None,
                    help="输出目录（非破坏性复现用；默认写交付源目录 output\\figures\\q4）")
    a = ap.parse_args()
    global FIG_DIR
    if a.out:
        FIG_DIR = Path(a.out)
        FIG_DIR.mkdir(parents=True, exist_ok=True)
    MC.apply_style()
    if MC.verify_fonts().get("serif"):
        print("缺字闸门未过"); return 2
    data = _load()
    man = Manifest(root=str(FIG_DIR.parent), group=FIG_DIR.name,
                   key_values_source="q4_data_frozen.py（锚点闸门 ANCHORS: PASS，"
                                     "与 Q4交付\\manifest.sha256.json 逐文件对表；图内数值由脚本现算）")
    for nm in (a.only or list(FIGS)):
        e, paths = FIGS[nm](*data)
        man.add(name=e["name"], purpose=e["purpose"], data_source=e["data_source"],
                key_values=e["key_values"], script=e["script"])
        print("[%s] 出图 OK -> %s" % (nm, paths["png"]))
    print("manifest ->", man.write())
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
