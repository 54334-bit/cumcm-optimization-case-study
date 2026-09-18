# -*- coding: utf-8 -*-
r"""Q2 Tier A 主结果图（对话6 · 冻结口径 2026-09-12）。

数据唯一来源：`q2_data_frozen.py`（冻结台账 `_s1_wd4.jsonl` + 交付 xlsx + 附件1/2）。
口径：同周4周情景集 + e–C 互斥 MILP（e≡0）+ 执行层 E1 + λ=0.4720；
      QG/QH/J_plan/J_emg 等一律**现算**，禁止手填。

用法：
    $env:PYTHONPATH="D:\CMUCU\rag\.deps"; $env:PYTHONIOENCODING='utf-8'
    & $py "D:\CMUCU\6对话\code\q2_fig_A_main.py" --only q2_01 q2_02
    & $py "D:\CMUCU\6对话\code\q2_fig_A_main.py"            # 全部 A 档
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import mpl_config as MC          # noqa: E402
import q2_data_causal as F       # noqa: E402  ← 主口径（非预见+因果裕度，2026-09-12 13:48 封包）
from fig_manifest import Manifest  # noqa: E402

FIG_DIR = Path(r"D:\CMUCU\6对话\output\figures\q2")
GROUP = "q2"
T, DT = F.T, F.DT


def _load():
    led = F.load_main()
    inp = F.load_inputs(led, verbose=False)
    return led, inp


def _m(**kw):
    return kw


def _haxis(ax, *, label: str = "时刻 (h)", tick_step: int = 2) -> None:
    """小时制横轴：数据单位是**小时**（0–24），不是 0–144 区间号。

    注意：`mpl_config.hour_axis()` 是按"区间号 0–144"设计的（set_xlim(0,144)、
    刻度 `h*6`）。直接用它会把 0–24 h 的数据压到绘图区左侧 1/6（参考人 2026-09-12 发现），
    故此处自带小时制轴。
    """
    ax.set_xlim(0, 24)
    ax.set_xticks(list(range(0, 25, tick_step)))
    ax.set_xticklabels(["%d:00" % h for h in range(0, 25, tick_step)])
    ax.set_xlabel(label, fontsize=8.5)


def _nice_ylim(ax, vmax: float, *, head: float = 0.12) -> float:
    """给柱子选一个"漂亮"纵轴上限，并**显式给刻度**（保证最高柱在最后一个刻度之下）。

    背景：自动刻度会在小坐标区里省略中间刻度（如 09-23 面板只剩 0/20），
    使 26.07 这类值落在最后可见刻度之上——豆包 2026-09-12 提出，已复核属实。
    """
    import math

    vmax = float(max(vmax, 0.0))
    if vmax <= 0:
        ax.set_ylim(0, 1.0)
        ax.set_yticks([0, 0.5, 1.0])
        ax.set_yticklabels(["0", "0.5", "1"])
        return 1.0
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


# ---------------------------------------------------------------------------
# q2_01 指定日「计划—执行」全链
# ---------------------------------------------------------------------------
def fig_q2_01(led, inp, day: str = "2025-06-01") -> dict:
    i = [j for j, d in enumerate(led["dates"]) if str(d) == day][0]
    price = inp["price"]
    load = inp["load_kW"][i]
    pv = inp["pv_kW"][i]
    G, H, C, D = led["G"][i], led["H"][i], led["C"][i], led["D"][i]
    soc = F.soc_path(led, i)
    h = np.arange(T) * DT          # 区间起点（h）
    hm = h + DT / 2                # 区间中点（画柱/点用）
    Gkw, Hkw, Ckw, Dkw = G / DT, H / DT, C / DT, D / DT
    nseg = len(F.merge_spans(H))
    mg = float(led["margin"][i])

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(7.4, 6.2), sharex=True,
                                   gridspec_kw={"height_ratios": [1.15, 1.0], "hspace": 0.16})
    # ---- (a) 供给/需求视图 ----
    ax1b = ax1.twinx()
    ax1b.step(h, price, where="post", color=MC.PALETTE["price"], lw=1.1, alpha=0.75,
              label="附件1 电价（右轴）")
    ax1b.set_ylabel("电价 (元/kWh)", color=MC.PALETTE["price"], fontsize=8)
    ax1b.tick_params(axis="y", colors=MC.PALETTE["price"], labelsize=7)
    ax1b.set_ylim(0, max(price) * 2.1)

    ax1.bar(hm, Gkw, width=DT * 0.9, color=MC.PALETTE["grid"], alpha=0.50,
            label="计划购电 $G_{plan}$（按全额计费）")
    ax1.bar(hm, Hkw, width=DT * 0.9, color=MC.PALETTE["emer"], alpha=0.95, hatch="///",
            edgecolor="white", lw=0.2, label="紧急购电 $H$（$5p_t$）")
    ax1.plot(hm, load, "-", color=MC.PALETTE["load"], lw=1.6, label="小区负载 $L$")
    ax1.plot(hm, pv, "--", color=MC.PALETTE["pv"], lw=1.5, label="光伏出力 $PV$")
    ax1.fill_between(hm, 0, pv, color=MC.PALETTE["pv"], alpha=0.13)
    _haxis(ax1, label="")
    ax1.set_ylabel("功率 (kW)", fontsize=8.5)
    ax1.set_title("(a) 供给与需求：计划购电形态 + 紧急补口位置", fontsize=9, loc="left")
    ax1.legend(loc="upper left", fontsize=6.4, ncol=2, framealpha=0.9)
    ax1.set_ylim(0, max(load.max(), pv.max(), Gkw.max(), Hkw.max()) * 1.35)
    ax1.text(0.985, 0.96,
             "该日 $\\Sigma G_{plan}$ = %.0f kWh\n$\\Sigma H$ = %.2f kWh（%d 段）\n因果裕度 = %.2f%%"
             % (G.sum(), H.sum(), nseg, 100 * mg),
             transform=ax1.transAxes, ha="right", va="top", fontsize=6.6,
             bbox=dict(facecolor="white", edgecolor="none", alpha=0.85))

    # ---- (b) 储能行为 + SOC ----
    ax2.bar(hm, -Ckw, width=DT * 0.9, color=MC.PALETTE["charge"], alpha=0.85,
            label="充电 $C$（向下）")
    ax2.bar(hm, Dkw, width=DT * 0.9, color=MC.PALETTE["discharge"], alpha=0.85, hatch="\\\\\\",
            edgecolor="white", lw=0.2, label="放电 $D$（向上）")
    ax2.axhline(0, color=MC.PALETTE["bound"], lw=0.8)
    ax2.set_ylabel("充放电功率 (kW)", fontsize=8.5)
    ax2.set_xlabel("时刻 (h)", fontsize=8.5)
    ax2.set_title("(b) 储能行为与 SOC 轨迹（单程效率 90%，SOC ∈ [1200, 10800] kWh）", fontsize=9, loc="left")
    ax2.legend(loc="upper left", fontsize=6.4, ncol=2, framealpha=0.9)
    lim = max(np.abs(-Ckw).max(), Dkw.max(), 1.0) * 1.9
    ax2.set_ylim(-lim, lim)

    ax2b = ax2.twinx()
    ax2b.plot(np.arange(T + 1) * DT, soc, "-", color=MC.PALETTE["soc"], lw=1.6, label="SOC（右轴）")
    ax2b.axhline(1200, color=MC.PALETTE["bound"], lw=0.9, ls="--")
    ax2b.axhline(10800, color=MC.PALETTE["bound"], lw=0.9, ls="--")
    ax2b.set_ylabel("储电量 SOC (kWh)", color=MC.PALETTE["soc"], fontsize=8)
    ax2b.tick_params(axis="y", colors=MC.PALETTE["soc"], labelsize=7)
    ax2b.set_ylim(0, 12600)
    # 上下限标注用与各自虚线一致的颜色，且贴在右端（原先用 SOC 同色、压在下限虚线上）
    ax2b.text(0.6, 10800, "上限 10800 kWh", ha="left", va="bottom", fontsize=5.8,
              color=MC.PALETTE["soc"])
    ax2b.text(0.6, 1200, "下限 1200 kWh", ha="left", va="bottom", fontsize=5.8,
              color=MC.PALETTE["soc"])

    fig.suptitle("%s · Q2「计划—执行」全链（主口径：非预见 + 因果保守裕度；结算用实际值）" % day,
                 fontsize=10.2, y=0.985)
    fig.tight_layout(rect=(0, 0, 1, 0.955))
    paths = MC.save_fig(fig, "q2_01_day_plan_exec", str(FIG_DIR))

    return _m(
        name="q2_01_day_plan_exec",
        purpose="指定日 %s 的 Q2「计划—执行」全链：负载/光伏、计划购电 G_plan（全额计费）、"
                "紧急购电 H（5p）、充放电与 SOC 轨迹（含上下限）" % day,
        data_source=[str(F.ART), str(F.XLSX), "B对话/clean/attachment2_*.csv",
                     "4对话/code/data_io.py::load_q1_day(附件1 电价)"],
        key_values={
            "day": day, "day_index": i, "n_emg_span": nseg,
            "G_plan_kWh": round(float(G.sum()), 4), "H_kWh": round(float(H.sum()), 4),
            "C_kWh": round(float(C.sum()), 4), "D_kWh": round(float(D.sum()), 4),
            "R_PV_kWh": round(float(led["R_PV"][i].sum()), 4),
            "R_G_kWh": round(float(led["R_G"][i].sum()), 4),
            "causal_margin": round(mg, 6),
            "s0_kWh": round(float(led["s0"][i]), 4), "s1_kWh": round(float(led["s1"][i]), 4),
            "soc_min_kWh": round(float(soc[1:].min()), 4), "soc_max_kWh": round(float(soc[1:].max()), 4),
            "J_plan_yuan": round(float(led["J_plan_day"][i]), 4),
            "J_emg_yuan": round(float(led["J_emg_day"][i]), 4),
            "price_min": round(float(price.min()), 4), "price_max": round(float(price.max()), 4),
        },
        script="q2_fig_A_main.py",
    ), paths


# ---------------------------------------------------------------------------
# q2_02 全年紧急购电日历（334×144 热力图 + 逐日合计）
# ---------------------------------------------------------------------------
def fig_q2_02(led, inp) -> dict:
    H = led["H"]
    dates = [str(d) for d in led["dates"]]
    day_qh = H.sum(axis=1)
    segs = sum(len(F.merge_spans(row)) for row in H)
    t5 = F.top_days(led)
    paper = ["2025-03-20", "2025-06-21", "2025-09-23", "2025-12-21"]
    maxq = float(day_qh.max())

    fig, (ax, axd) = plt.subplots(2, 1, figsize=(7.4, 6.4), sharex=False,
                                  gridspec_kw={"height_ratios": [3.0, 1.0], "hspace": 0.22})
    h = np.arange(T + 1) * DT
    # 用 imshow（单张位图元素）而不是 pcolormesh：图形一致，但 SVG 从 ~9 MB 降到几百 KB。
    # vmax 用正值 97 分位并封顶 ≤200 kWh：否则 833 kWh/10min 的量程会把绝大多数小格压成近白，
    # 视觉上低估"242 天有紧急购电"（检查大师 2026-09-12 指出）——超出 vmax 的格按最深色显示并在色标注明。
    pos = H[H > 0]
    vmax = float(min(np.percentile(pos, 97) if pos.size else 1.0, 200.0))
    vmax = max(vmax, 1.0)
    mesh = ax.imshow(H, aspect="auto", cmap="Reds", vmin=0, vmax=vmax, interpolation="nearest",
                     extent=[0, 24, len(dates), 0])
    ax.set_xlim(0, 24); ax.set_ylim(len(dates), 0)
    ax.set_ylabel("日期（2025-02-01 → 12-31）", fontsize=8.5)
    ax.set_title("(a) 全年紧急购电日历：%d 天有紧急购电、共 %d 段，Σ = %.0f kWh"
                 % (int((day_qh > 1e-9).sum()), segs, H.sum()), fontsize=9, loc="left")
    # 月界 + 论文四日期
    yt, yl = [], []
    for j, ds in enumerate(dates):
        if ds[8:10] == "01":
            yt.append(j); yl.append(ds[:7])
    ax.set_yticks(yt); ax.set_yticklabels(yl, fontsize=6.6)
    ax.tick_params(axis="y", length=0)
    for d in paper:
        if d in dates:
            j = dates.index(d)
            ax.axhline(j + 0.5, color="white", lw=1.0, ls="--")
            ax.axhline(j + 0.5, color=MC.PALETTE["grid"], lw=0.6, ls=":")
            ax.text(0.15, j + 1.6, "论文表3：%s" % d, fontsize=5.8, color=MC.PALETTE["grid"])
    for j, d in zip(t5["idx"], t5["dates"]):
        ax.plot([23.6], [j + 0.5], marker="v", ms=4.6, color=MC.PALETTE["emer"],
                markeredgecolor="white", markeredgewidth=0.5)
    ax.text(0.998, 1.02, "▼ 紧急费前 5 天（占全年 %.1f%%）" % t5["share_pct"],
            transform=ax.transAxes, ha="right", va="bottom", fontsize=6.2, color=MC.PALETTE["emer"])
    _haxis(ax, label="")          # (a) 面板不再重复 x 轴标题，避免与 (b) 标题相撞
    cb = fig.colorbar(mesh, ax=ax, pad=0.012, fraction=0.032)
    cb.set_label("紧急购电量 (kWh / 10 min)；≥%.0f 按最深色" % vmax, fontsize=6.6)
    cb.ax.tick_params(labelsize=6.6)

    axd.fill_between(np.arange(len(dates)), 0, day_qh, color=MC.PALETTE["emer"], alpha=0.55, lw=0)
    axd.plot(np.arange(len(dates)), day_qh, "-", color=MC.PALETTE["emer"], lw=0.7)
    for j in t5["idx"]:
        axd.plot([j], [day_qh[j]], marker="v", ms=4.2, color=MC.PALETTE["emer"],
                 markeredgecolor="white", markeredgewidth=0.4)
    axd.set_ylabel("日紧急购电量\n(kWh/日)", fontsize=7.5)
    axd.set_xlabel("全年序日（0 = 2025-02-01；共 %d 天）" % len(dates), fontsize=8)
    axd.set_xlim(0, len(dates) - 1)
    axd.set_title("(b) 逐日紧急购电量（峰值 %.0f kWh/日，出现于 %s）"
                  % (maxq, dates[int(np.argmax(day_qh))]), fontsize=9, loc="left")
    axd.grid(axis="y", color=MC.PALETTE["bound"], lw=0.4, alpha=0.5)
    fig.tight_layout(rect=(0, 0, 1, 0.985))
    paths = MC.save_fig(fig, "q2_02_emergency_calendar", str(FIG_DIR))

    return _m(
        name="q2_02_emergency_calendar",
        purpose="Q2 全年紧急购电结构：334 天 × 144 区间热力图 + 逐日合计，标注论文表 3 四日期与紧急费前 5 天",
        data_source=[str(F.ART), str(F.XLSX)],
        key_values={
            "QH_kWh": round(float(H.sum()), 4),
            "emg_days": int((day_qh > 1e-9).sum()), "emg_spans": int(segs),
            "max_day_QH_kWh": round(maxq, 4),
            "argmax_day": dates[int(np.argmax(day_qh))],
            "top5_dates": t5["dates"], "top5_share_pct": round(t5["share_pct"], 4),
            "table3_dates": paper,
            "table3_spans": [len(F.merge_spans(led["H"][dates.index(d)])) if d in dates else 0
                             for d in paper],
        },
        script="q2_fig_A_main.py",
    ), paths


# ---------------------------------------------------------------------------
# q2_03 论文表 3 图形化（四个指定日期的紧急购电段）
# ---------------------------------------------------------------------------
def fig_q2_03(led, inp) -> dict:
    t3 = F.table3(led)                       # 主口径：只写真实发生紧急购电的时段
    dates = list(t3)
    fig, axes = plt.subplots(len(dates), 1, figsize=(7.4, 6.0), sharex=True,
                             gridspec_kw={"hspace": 0.55})
    tot = 0.0
    for k, (ax, ds) in enumerate(zip(axes, dates)):
        segs = t3[ds]
        items = segs["segs"]
        tot += sum(s["kWh"] for s in items)
        for s in items:
            h0, m0 = (int(x) for x in s["t"].split("-")[0].split(":"))
            h1, m1 = (int(x) for x in s["t"].split("-")[1].split(":"))
            x0, x1 = h0 + m0 / 60, h1 + m1 / 60
            ax.bar((x0 + x1) / 2, s["kWh"], width=max(x1 - x0, 0.12),
                   color=MC.PALETTE["emer"], alpha=0.9, hatch="///", edgecolor="white", lw=0.3)
            ax.text((x0 + x1) / 2, s["kWh"] * 1.06, "%.2f" % s["kWh"], ha="center", va="bottom",
                    fontsize=5.8, color=MC.PALETTE["emer"])
        ymax = max([s["kWh"] for s in items] + [0.0])
        _nice_ylim(ax, ymax)          # 显式刻度：最高柱一定落在最后一个刻度之下
        ax.set_xlim(0, 24)
        ax.set_ylabel("紧急购电量\n(kWh/段)", fontsize=7)
        if items:
            txt = "%d 段：%s" % (len(items), "；".join(
                "%s %.2f kWh" % (s["t"], s["kWh"]) for s in items))
        else:
            txt = "无紧急购电"
        ax.set_title("%s —— %s（合计 %.2f kWh）" % (ds, txt, sum(s["kWh"] for s in items)),
                     fontsize=7.6, loc="left")
        ax.grid(axis="y", color=MC.PALETTE["bound"], lw=0.4, alpha=0.5)
        _haxis(ax, label="")
    axes[-1].set_xlabel("时刻 (h)", fontsize=8.5)
    fig.suptitle("论文表 3 图形化：四个指定日期的紧急购电段（主口径：非预见 + 因果保守裕度）",
                 fontsize=10, y=0.99)
    fig.tight_layout(rect=(0, 0, 1, 0.955))
    paths = MC.save_fig(fig, "q2_03_paper_table3", str(FIG_DIR))

    return _m(
        name="q2_03_paper_table3",
        purpose="论文表 3 的图形化：2025-03-20 / 06-21 / 09-23 / 12-21 四个指定日期的紧急购电段"
                "（时间段与段电量，无紧急购电的日期明确标注）",
        data_source=[str(F.ART), str(F.XLSX) + "::紧急购电量(表3 交查)",
                     "5对话/交付说明_Q2_因果裕度非预见.md §2（表3 四日期）"],
        key_values={
            "segments": {d: [{"span": s["t"], "kWh": round(s["kWh"], 4)} for s in v["segs"]]
                         for d, v in t3.items()},
            "span_counts": {d: len(v["segs"]) for d, v in t3.items()},
            "kwh_totals": {d: round(sum(s["kWh"] for s in v["segs"]), 4) for d, v in t3.items()},
            "ledger_span_n": {d: v["ledger_n"] for d, v in t3.items()},
            "ledger_kWh": {d: v["ledger_kWh"] for d, v in t3.items()},
            "grand_total_kWh": round(tot, 4),
            "caliber": "主口径：0:00 计划（负荷已知、光伏=过去4天均值×(1−因果裕度)）→ 结算用实际，5 倍紧急购电；段=同日连续区间合并",
        },
        script="q2_fig_A_main.py",
    ), paths


# ---------------------------------------------------------------------------
# q2_04 费用结构（主口径 + 同数据多口径对照 + 交付档内部分解）
# 对照出处：`5对话\附录_Q2口径对照.md`（同数据/同参数/同结算规则，仅改计划阶段信息 → 可并列；
# ② 为不可执行下界，必须显式标注，不得当作可提交结果）。
# ---------------------------------------------------------------------------
def fig_q2_04(led, inp) -> dict:
    J_plan = float(led["J_plan_day"].sum())
    J_emg = float(led["J_emg_day"].sum())
    J_cash = J_plan + J_emg
    # 出处：对话5 的**最终裁决**（`6对话\Q2最终裁决与可用数字_对话5到6对话.md` §一）：
    # 基准统一为主口径；② 仅下界；③ 旧灵敏度**只允许出现在对照图并显式标注**（本图即对照图）。
    CMP = [(nm, (J_cash if i == 0 else v), MC.PALETTE[c], h, tag)
           for i, (nm, v, c, h, tag) in enumerate(F.CMP_RULING)]
    assert abs(CMP[0][1] - 13252341.09) < 0.01, "主口径值必须与交付说明一致"

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(7.4, 3.5),
                                  gridspec_kw={"width_ratios": [1.55, 1.0], "wspace": 0.30})
    xs = np.arange(len(CMP))
    ax.bar(xs[0], J_plan / 1e6, width=0.62, color=MC.PALETTE["grid"], alpha=0.85,
           label="计划购电费 $J_{plan}$（按 $G_{plan}$ 全额计费）")
    ax.bar(xs[0], J_emg / 1e6, bottom=J_plan / 1e6, width=0.62, color=MC.PALETTE["emer"],
           alpha=0.9, hatch="///", edgecolor="white", lw=0.3, label="紧急购电费 $J_{emg}$（$5p_t$）")
    for i in range(1, len(CMP)):
        ax.bar(xs[i], CMP[i][1] / 1e6, width=0.62, color=CMP[i][2], alpha=0.78,
               hatch=CMP[i][3], edgecolor="white", lw=0.3)
    _lbb = dict(facecolor="white", edgecolor="none", alpha=0.88, pad=0.5)
    for i, (nm, v, _c, _h, tag) in enumerate(CMP):
        ax.text(xs[i], v / 1e6 * 1.012, "%.2f" % (v / 1e6), ha="center", va="bottom", fontsize=6.4)
        if i:
            # 白字压在斜纹/浅色柱上对比度不足（本人 + 豆包 2026-09-13 复核）→ 改深字 + 白底
            ax.text(xs[i], v / 1e6 * 0.5, tag, ha="center", va="center", fontsize=6.0,
                    color="#222222", bbox=_lbb)
    ax.set_xticks(xs)
    ax.set_xticklabels([c[0] for c in CMP], fontsize=5.4)
    ax.set_ylabel("年度现金费用 (百万元)", fontsize=8.5)
    ax.set_ylim(0, max(c[1] for c in CMP) / 1e6 * 1.22)
    ax.set_title("(a) 同数据、同规则下的多口径对照（相对值一律以主口径为基准）", fontsize=8.4, loc="left")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16), fontsize=6.2, ncol=2,
              frameon=False)          # 图例移到坐标区外（原先压柱）
    ax.grid(axis="y", color=MC.PALETTE["bound"], lw=0.4, alpha=0.5)

    shares = np.array([J_plan, J_emg]) / J_cash * 100
    ax2.barh([1], [shares[1]], color=MC.PALETTE["emer"], alpha=0.9, hatch="///",
             edgecolor="white", lw=0.4)
    ax2.barh([1], [shares[0]], left=[shares[1]], color=MC.PALETTE["grid"], alpha=0.85)
    ax2.set_yticks([]); ax2.set_xlim(0, 100)
    ax2.set_xlabel("占全年费用比例 (%)", fontsize=8)
    ax2.set_title("(b) 主口径费用构成", fontsize=9, loc="left")
    # 紧急段很窄（2.7%），文字压在上面会被斜纹切开 → 用引线标到条外
    ax2.annotate("紧急 %.2f%%" % shares[1], xy=(shares[1] / 2, 0.93), xytext=(10, 0.62),
                 fontsize=6.4, color=MC.PALETTE["emer"],
                 arrowprops=dict(arrowstyle="->", color=MC.PALETTE["emer"], lw=0.7))
    ax2.text(shares[1] + shares[0] / 2, 1, "计划 %.2f%%" % shares[0], ha="center", va="center",
             fontsize=7.0, color="white")
    ax2.set_ylim(0.4, 1.6)
    ax2.text(0.0, 0.14, "注：②不可执行（紧急 0、机制退化）；③旧灵敏度仅作对照。",
             fontsize=5.8, va="bottom", color="#444444")
    fig.suptitle("Q2 费用结构：计划购电费 + 紧急购电费（take-or-pay；主口径=非预见+因果裕度）",
                 fontsize=9.6, y=0.99)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    paths = MC.save_fig(fig, "q2_04_cost_structure", str(FIG_DIR))

    return _m(
        name="q2_04_cost_structure",
        purpose="Q2 年度费用结构与多口径对照：主口径的 J_plan/J_emg 分解 + 同数据下 ①无裕度 / "
                "②完全信息下界（不可执行）/ ③旧灵敏度（仅对照）/ ④附件1 典型日 / ⑤无储能 的对照，"
                "相对值一律以主口径 13,252,341.09 元为基准",
        data_source=[str(F.ART), "5对话/附录_Q2口径对照.md（对照数字）",
                     "5对话/交付说明_Q2_因果裕度非预见.md §2"],
        key_values={
            "J_plan_yuan": round(J_plan, 4), "J_emg_yuan": round(J_emg, 4),
            "total_yuan": round(J_cash, 4),
            "J_emg_share_pct": round(float(shares[1]), 4),
            "cmp_total_yuan": {c[0].replace("\n", " "): c[1] for c in CMP},
            "cmp_rel_pct": {c[0].replace("\n", " "): round(100 * (c[1] - J_cash) / J_cash, 4)
                            for c in CMP},
            "note": "②完全信息下界不可执行（紧急 0、5 倍机制与表3退化）；旧同周4周口径已按队长指令从图中剔除，不再引用",
        },
        script="q2_fig_A_main.py",
    ), paths


# ---------------------------------------------------------------------------
# q2_05 全年 SOC：日界轨迹 + 容量边界 + 贴顶/贴底统计
# ---------------------------------------------------------------------------
def fig_q2_05(led, inp) -> dict:
    n = len(led["dates"])
    s0, s1 = led["s0"], led["s1"]
    lo_days = hi_days = 0
    dmin, dmax = np.zeros(n), np.zeros(n)
    for i in range(n):
        s = F.soc_path(led, i)[1:]
        dmin[i], dmax[i] = s.min(), s.max()
        lo_days += int(dmin[i] <= 1200 + 1e-6)
        hi_days += int(dmax[i] >= 10800 - 1e-6)
    x = np.arange(n)
    dates = [str(d) for d in led["dates"]]
    yt, yl = [], []
    for j, ds in enumerate(dates):
        if ds[8:10] == "01":
            yt.append(j); yl.append(ds[:7])

    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(7.4, 5.4),
                                  gridspec_kw={"height_ratios": [2.2, 1.0], "hspace": 0.30})
    # 不铺"允许区间"底色（两层半透明填充叠加会造成视觉上的不规则留白——豆包 2026-09-12 提出，已复核）
    ax.fill_between(x, dmin, dmax, color=MC.PALETTE["soc"], alpha=0.30, lw=0,
                    label="当日时段内 SOC 范围")
    ax.plot(x, s1, "-", color=MC.PALETTE["soc"], lw=1.3, label="日末 SOC（$s_1$）")
    ax.plot(x, s0, ":", color=MC.PALETTE["net"], lw=1.0, label="日初 SOC（$s_0$）")
    ax.axhline(1200, color=MC.PALETTE["emer"], lw=1.0, ls="--")
    ax.axhline(10800, color=MC.PALETTE["grid"], lw=1.0, ls="--")
    _bx = dict(facecolor="white", edgecolor="none", alpha=0.85, pad=0.8)
    ax.text(n - 1, 1200, " 下限 1200 kWh", ha="right", va="top", fontsize=6.2,
            color=MC.PALETTE["emer"], bbox=_bx)
    ax.text(n - 1, 10800, " 上限 10800 kWh", ha="right", va="bottom", fontsize=6.2,
            color=MC.PALETTE["grid"], bbox=_bx)
    ax.set_xticks(yt); ax.set_xticklabels(yl, fontsize=7)
    ax.set_xlim(0, n - 1)
    ax.set_ylim(min(1200.0, float(dmin.min())) - 600, max(10800.0, float(dmax.max())) + 600)
    ax.set_ylabel("储电量 SOC (kWh)", fontsize=8.5)
    ax.set_title("(a) 全年 SOC：日界轨迹与容量边界（触底 %d 天 / 触顶 %d 天）" % (lo_days, hi_days),
                 fontsize=9, loc="left")
    # 图例放到坐标区外（原先置于左下会压住 1200 下限线与 s0 轨迹）
    ax.legend(loc="upper left", bbox_to_anchor=(0.0, -0.06), fontsize=6.4, ncol=3,
              framealpha=0.0, borderaxespad=0.0)
    ax.grid(color=MC.PALETTE["bound"], lw=0.4, alpha=0.35)

    ax2.bar(x, (dmax >= 10800 - 1e-6).astype(int), width=1.0, color=MC.PALETTE["grid"],
            alpha=0.75, label="当日触顶（≥10800）")
    ax2.bar(x, -(dmin <= 1200 + 1e-6).astype(int), width=1.0, color=MC.PALETTE["emer"],
            alpha=0.9, hatch="///", edgecolor="white", lw=0.2, label="当日触底（≤1200）")
    ax2.axhline(0, color=MC.PALETTE["bound"], lw=0.8)
    ax2.set_xticks(yt); ax2.set_xticklabels(yl, fontsize=7)
    ax2.set_xlim(0, n - 1); ax2.set_ylim(-1.6, 1.6)
    ax2.set_yticks([-1, 0, 1]); ax2.set_yticklabels(["触底", "—", "触顶"], fontsize=7)
    ax2.set_xlabel("2025 年（%d 天：02-01 ~ 12-31）" % n, fontsize=8)
    ax2.set_title("(b) 触顶/触底日历：容量边界被频繁占用", fontsize=9, loc="left")
    ax2.legend(loc="upper left", fontsize=6.2, ncol=2, framealpha=0.9)
    fig.tight_layout(rect=(0, 0, 1, 0.975))
    paths = MC.save_fig(fig, "q2_05_soc_year", str(FIG_DIR))

    return _m(
        name="q2_05_soc_year",
        purpose="Q2 全年储能 SOC：日界轨迹 + 时段内范围 + 1200/10800 边界，逐日触顶/触底日历",
        data_source=[str(F.ART) + "（s0/s1 + C/D 按 η=0.9 重放时段内轨迹）"],
        key_values={
            "n_days": n, "soc_min_kWh": round(float(dmin.min()), 4),
            "soc_max_kWh": round(float(dmax.max()), 4),
            "touch_low_days": int(lo_days), "touch_high_days": int(hi_days),
            "s0_first_kWh": round(float(s0[0]), 4), "s_end_kWh": round(float(s1[-1]), 4),
            "recursion_eta": F.ETA,
            "boundary_closure_max_abs_kWh": round(float(max(
                abs(F.soc_path(led, i)[-1] - s1[i]) for i in range(n))), 8),
        },
        script="q2_fig_A_main.py",
    ), paths


# ---------------------------------------------------------------------------
# q2_06 弃电拆分（R_PV 弃光伏 vs R_G 弃计划电）
# ---------------------------------------------------------------------------
def fig_q2_06(led, inp) -> dict:
    mo = F.monthly(led, inp)
    r_pv = led["R_PV"].sum(axis=1)          # 主口径：R_PV/R_G 为逐区间数组，按日汇总
    r_g = led["R_G"].sum(axis=1)
    qg = float(led["G"].sum())
    n_rg_days = int((r_g > 1e-9).sum())
    x = np.arange(len(mo["keys"]))

    # 重画（绘图大师 2026-09-12：原堆叠把 R_G 完全盖住、月标签挤成一片）
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(7.4, 3.7),
                                  gridspec_kw={"width_ratios": [1.45, 1.0], "wspace": 0.46})
    ax.bar(x, mo["R_PV_kWh"] / 1e3, width=0.62, color=MC.PALETTE["pv"], alpha=0.9,
           label="弃光伏 $R_{PV}$（左轴）")
    for i in range(len(x)):
        ax.text(i, mo["R_PV_kWh"][i] / 1e3 * 1.02, "%.0f" % (mo["R_PV_kWh"][i] / 1e3),
                ha="center", va="bottom", fontsize=5.8)
    ax.set_xticks(x)
    ax.set_xticklabels(mo["keys"], fontsize=6.2, rotation=45, ha="right")
    ax.set_ylabel("弃光伏 $R_{PV}$ (千 kWh/月)", fontsize=8.5)
    ax.set_ylim(0, float(mo["R_PV_kWh"].max()) / 1e3 * 1.25)
    ax.set_title("(a) 月度弃电：光伏富余（柱）与已付费未取用（线，右轴）", fontsize=8.6, loc="left")
    ax.grid(axis="y", color=MC.PALETTE["bound"], lw=0.4, alpha=0.5)

    axg = ax.twinx()      # R_G 量级只有 R_PV 的 0.75%，必须单独一根轴才看得见
    axg.plot(x, mo["R_G_kWh"], "-o", ms=3.0, lw=1.2, color=MC.PALETTE["curtail"],
             label="弃计划电 $R_G$（右轴）")
    # 右轴标签原先与 (b) 的左轴标签在中间相撞 → 去掉（图例已写"（右轴）"，刻度仍为本色）
    axg.tick_params(axis="y", colors=MC.PALETTE["curtail"], labelsize=6.6)
    axg.set_ylim(0, max(float(mo["R_G_kWh"].max()) * 1.35, 1.0))
    h1, l1 = ax.get_legend_handles_labels(); h2, l2 = axg.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper right", fontsize=6.2, framealpha=0.9)

    parts = [float(r_pv.sum()), float(r_g.sum())]
    _bars = [(qg, MC.PALETTE["grid"], 0.85, ""), (parts[0], MC.PALETTE["pv"], 0.90, ""),
             (parts[1], MC.PALETTE["curtail"], 0.95, "///")]
    for i, (v, c, al, ha) in enumerate(_bars):
        ax2.bar(i, v / 1e3, width=0.6, color=c, alpha=al, hatch=ha,
                edgecolor="white", lw=0.3)
        ax2.text(i, v / 1e3 * 1.02, "%.1f" % (v / 1e3), ha="center", va="bottom", fontsize=7)
    ax2.set_xticks([0, 1, 2])
    ax2.set_xticklabels(["年计划购电量\n$Q_G$", "年弃光伏\n$R_{PV}$", "年弃计划电\n$R_G$"], fontsize=7)
    ax2.set_ylabel("电量 (千 kWh/年)", fontsize=8.5)
    _nice_ylim(ax2, max(qg, parts[0], parts[1]) / 1e3)   # 年计划购电柱曾超出可见刻度（豆包 2026-09-13）
    ax2.set_title("(b) 年度量级对比", fontsize=9, loc="left")
    ax2.text(0, max(qg, parts[0]) / 1e3 * 0.55,
             "$R_G/Q_G$ = %.4f%%\n$R_G/R_{PV}$ = %.3f%%\n$R_G>0$：%d 天"
             % (100 * parts[1] / qg, 100 * parts[1] / parts[0], n_rg_days),
             fontsize=7, color="#333333")
    ax2.grid(axis="y", color=MC.PALETTE["bound"], lw=0.4, alpha=0.5)
    fig.suptitle("Q2 弃电去向：光伏富余 vs 已付费未取用（主口径：非预见 + 因果裕度；两者不可混称“弃光”）",
                 fontsize=9.6, y=0.99)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    paths = MC.save_fig(fig, "q2_06_curtail_split", str(FIG_DIR))

    return _m(
        name="q2_06_curtail_split",
        purpose="Q2 弃电拆分：弃光伏 R_PV 与弃计划电 R_G 的月度堆叠与年度量级对比（R_G 为已付费未取用，不是售电/反送）",
        data_source=[str(F.ART)],
        key_values={
            "R_PV_kWh": round(parts[0], 4), "R_G_kWh": round(parts[1], 4),
            "QG_kWh": round(qg, 4), "R_G_over_QG_pct": round(100 * parts[1] / qg, 6),
            "R_G_positive_days": n_rg_days,
            "monthly": {k: {"R_PV": round(float(mo["R_PV_kWh"][i]), 3),
                            "R_G": round(float(mo["R_G_kWh"][i]), 3)}
                        for i, k in enumerate(mo["keys"])},
        },
        script="q2_fig_A_main.py",
    ), paths


FIGS = {"q2_01": fig_q2_01, "q2_02": fig_q2_02, "q2_03": fig_q2_03,
        "q2_04": fig_q2_04, "q2_05": fig_q2_05, "q2_06": fig_q2_06}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=None)
    a = ap.parse_args()
    MC.apply_style()
    missing = MC.verify_fonts()
    if missing.get("serif"):
        print("缺字闸门未过：", missing); return 2
    led, inp = _load()
    names = a.only or list(FIGS)
    man = Manifest(root=str(FIG_DIR.parent), group=GROUP)
    ok = 0
    for nm in names:
        entry, paths = FIGS[nm](led, inp)
        man.add(name=entry["name"], purpose=entry["purpose"], data_source=entry["data_source"],
                key_values=entry["key_values"], script=entry["script"])
        ok += 1
        print("[%s] 出图 OK -> %s" % (nm, paths["png"]))
    p = man.write()
    print("manifest ->", p)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
