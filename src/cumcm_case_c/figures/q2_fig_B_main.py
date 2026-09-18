# -*- coding: utf-8 -*-
r"""Q2 Tier B 机制图（对话6 · 主口径）。

q2_08_quantile_margin：报童/分位机制 —— 为什么"过去 4 天均值"要再按因果保守裕度下移 ≈7%。
  (a) 实测相对预报误差分布（预报 = 过去 4 天实际光伏曲线均值；掩码 预报 > 50 kW），标 P20/P50；
  (b) 冻结台账里的逐日因果裕度 margin_d（取自凭证，不重算）与 0/0.35 截断、均值线。

口径与诚实边界（务必保留在图注/manifest）：
  * 主口径规则（交付说明 §1）：margin_d = clip(−Q20(过去 28 天相对预报误差), 0, 0.35)，均值 ≈7%；
    报童临界比 c_u/(c_o+c_u) = 4p/(p+4p) = 0.8 ⇒ 取 80% 分位 ⇒ 等价于向下 20% 分位裕度。
  * **图上裕度一律取冻结台账值**。本人按文档规则独立复算的 margin 与台账均值差 0.15 个百分点、
    逐日最大差 0.0198（窗口/分位实现约定差异），故不声称逐日复现。

用法：$env:PYTHONPATH="D:\CMUCU\rag\.deps"; $env:PYTHONIOENCODING='utf-8'
      & $py "D:\CMUCU\6对话\code\q2_fig_B_main.py"
"""
from __future__ import annotations

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
MARGIN_REPRO_MAXDIFF = 0.019762      # 见模块 docstring 的独立复算差异（如实披露）


def rel_error_pool(inp: dict, *, mins: int = 4, thr: float = 50.0) -> np.ndarray:
    """构造"相对预报误差"样本池：预报 = 过去 mins 天实际曲线的逐时段均值。"""
    pv = inp["pv_kW"]
    out = []
    for i in range(mins, len(pv)):
        f = pv[i - mins:i].mean(axis=0)
        ok = f > thr
        if ok.sum() >= 24:
            out.append((pv[i][ok] - f[ok]) / f[ok])
    return np.concatenate(out)


def fig_q2_08(led, inp) -> dict:
    err = rel_error_pool(inp) * 100.0            # %
    q = np.quantile(err, [0.05, 0.20, 0.50, 0.80, 0.95])
    mg = led["margin"] * 100.0                   # 台账逐日裕度（%）

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(7.4, 3.4),
                                  gridspec_kw={"width_ratios": [1.25, 1.0], "wspace": 0.30})
    ax.hist(err, bins=60, color=MC.PALETTE["pv"], alpha=0.85, edgecolor="white", lw=0.2)
    ax.axvline(q[1], color=MC.PALETTE["emer"], lw=1.2, ls="--")
    ax.axvline(0, color=MC.PALETTE["net"], lw=1.0, ls=":")
    ax.text(q[1], ax.get_ylim()[1] * 0.96, " P20 = %.1f%%" % q[1], color=MC.PALETTE["emer"],
            fontsize=6.6, va="top", ha="left")
    ax.text(0, ax.get_ylim()[1] * 0.80, " 中位 %.1f%%" % q[2], color=MC.PALETTE["net"],
            fontsize=6.4, va="top", ha="left")
    ax.set_xlabel("相对预报误差 $(PV_{act}-PV_{fc})/PV_{fc}$ (%)", fontsize=8.5)
    ax.set_ylabel("样本数（10 分钟时段）", fontsize=8.5)
    ax.set_title("(a) 实测相对预报误差分布（预报=过去 4 天均值）", fontsize=8.8, loc="left")
    ax.grid(axis="y", color=MC.PALETTE["bound"], lw=0.4, alpha=0.5)
    ax.text(0.02, 0.03,
            "P05/P50/P95 = %.1f / %.1f / %.1f %%\n"
            "报童临界比 $c_u/(c_o+c_u)=4p/(p+4p)=0.8$\n⇒ 取 80%% 分位 ⇒ 向下 20%% 分位裕度"
            % (q[0], q[2], q[4]),
            transform=ax.transAxes, fontsize=6.0, va="bottom",
            bbox=dict(facecolor="white", edgecolor="none", alpha=0.85))

    x = np.arange(len(mg))
    ax2.plot(x, mg, "-", color=MC.PALETTE["soc"], lw=0.9)
    ax2.axhline(mg.mean(), color=MC.PALETTE["grid"], lw=1.0, ls="--")
    ax2.axhline(0, color=MC.PALETTE["bound"], lw=0.8)
    ax2.axhline(35, color=MC.PALETTE["bound"], lw=0.8, ls=":")
    ax2.text(len(mg) * 0.02, mg.mean() + 0.6, "均值 %.2f%%" % mg.mean(),
             color=MC.PALETTE["grid"], fontsize=6.6)
    ax2.text(len(mg) * 0.98, 35, "截断上限 35%", ha="right", va="bottom", fontsize=6.0,
             color="#666666")
    yt, yl = [], []
    for j, d in enumerate(led["dates"]):
        if str(d)[8:10] == "01":
            yt.append(j); yl.append(str(d)[:7])
    ax2.set_xticks(yt); ax2.set_xticklabels(yl, fontsize=6.6)
    ax2.set_xlim(0, len(mg) - 1); ax2.set_ylim(-1, 38)
    ax2.set_ylabel("因果裕度 $margin_d$ (%)", fontsize=8.5)
    ax2.set_xlabel("2025 年（334 天）", fontsize=8.5)
    ax2.set_title("(b) 冻结台账的逐日因果裕度（截断 [0, 35%]）", fontsize=8.8, loc="left")
    ax2.grid(axis="y", color=MC.PALETTE["bound"], lw=0.4, alpha=0.5)

    fig.suptitle("Q2 主口径的分位机制：紧急购电 5 倍代价 ⇒ 计划光伏按 P20 保守下移",
                 fontsize=9.6, y=0.99)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    paths = MC.save_fig(fig, "q2_08_quantile_margin", str(FIG_DIR))

    return {
        "name": "q2_08_quantile_margin",
        "purpose": "Q2 分位/报童机制：为何计划光伏要在'过去 4 天均值'上再按因果保守裕度下移 ≈7%"
                   "（(a) 实测相对预报误差分布与 P20；(b) 冻结台账逐日裕度）",
        "data_source": [str(F.ART) + "（margin 逐日序列）", "B对话/clean/attachment2_pv.csv（相对误差分布）",
                        "5对话/交付说明_Q2_因果裕度非预见.md §1（裕度规则）"],
        "key_values": {
            "err_pct_p05_p20_p50_p80_p95": [round(float(v), 4) for v in q],
            "err_sample_n": int(err.size),
            "margin_mean_pct": round(float(mg.mean()), 4),
            "margin_min_pct": round(float(mg.min()), 4),
            "margin_max_pct": round(float(mg.max()), 4),
            "critical_ratio": 0.8, "margin_quantile": 0.20, "margin_clip": [0.0, 0.35],
            "repro_note": "本人按文档规则的独立复算与台账均值差 0.15pp、逐日最大差 %.6f（窗口/分位约定差异）；"
                          "图上裕度一律取台账值，不声称逐日复现" % MARGIN_REPRO_MAXDIFF,
        },
        "script": "q2_fig_B_main.py",
    }, paths


def fig_q2_09(led, inp) -> dict:
    """终端残值 λ 的机制图（数据：`Q2交付\\04_证据\\q2_lam_new_caliber.json`，现行口径重跑）。"""
    lam_path = F.DELIV / "04_证据" / "q2_lam_new_caliber.json"
    rows = json.loads(lam_path.read_text(encoding="utf-8"))
    lam = np.array([r["lam"] for r in rows], float)
    tot = np.array([r["total"] for r in rows], float)
    send = np.array([r["s_end"] for r in rows], float)
    days = sorted({int(r["emg_days"]) for r in rows})
    segs = sorted({int(r["emg_segments"]) for r in rows})
    star = 0.4720
    i_star = int(np.argmin(np.abs(lam - star)))
    lo, hi = float(tot.min()), float(tot.max())
    rng, rng_pct = hi - lo, 100 * (hi - lo) / lo
    gap = float(tot[i_star] - lo)

    fig, ax = plt.subplots(figsize=(7.4, 4.0))
    ax.step(lam, tot, where="post", color=MC.PALETTE["grid"], lw=1.5,
            label="全年购电费用（左轴）")
    ax.plot(lam, tot, "o", ms=3.4, color=MC.PALETTE["grid"], markeredgecolor="white",
            markeredgewidth=0.4)
    ax.axvline(star, color=MC.PALETTE["emer"], lw=1.1, ls="--")
    ax.annotate("本文取 λ=%.4f\n（边际量 $C'(6000)$）" % star, xy=(star, tot[i_star]),
                xytext=(star + 0.06, lo + (hi - lo) * 0.55), fontsize=6.6,
                color=MC.PALETTE["emer"],
                arrowprops=dict(arrowstyle="->", color=MC.PALETTE["emer"], lw=0.8))
    for i, (l, t) in enumerate(zip(lam, tot)):
        ax.text(l, t + (hi - lo) * 0.045, "%.2f" % (t / 1e6), ha="center", va="bottom",
                fontsize=6.0, color=MC.PALETTE["grid"])
    ax.set_xlabel("终端残值 λ（元/kWh）", fontsize=8.5)
    ax.set_ylabel("全年购电费用（百万元）", fontsize=8.5)
    ax.set_xlim(-0.03, 0.95)
    ax.set_ylim(lo - (hi - lo) * 0.45, hi + (hi - lo) * 0.55)
    ax.set_title("Q2 终端残值 λ 的机制：三级台阶（费用对终端口径不敏感）", fontsize=9.2, loc="left")
    ax.grid(axis="y", color=MC.PALETTE["bound"], lw=0.4, alpha=0.5)

    ax2 = ax.twinx()
    ax2.step(lam, send, where="post", color=MC.PALETTE["soc"], lw=1.3, ls="-",
             label="年末 SOC（右轴）")
    ax2.plot(lam, send, "s", ms=3.2, color=MC.PALETTE["soc"], markeredgecolor="white",
             markeredgewidth=0.4)
    ax2.set_ylabel("年末 24:00 SOC (kWh)", color=MC.PALETTE["soc"], fontsize=8.5)
    ax2.tick_params(axis="y", colors=MC.PALETTE["soc"], labelsize=7.5)
    ax2.set_ylim(0, 12600)
    for lv, txt in ((1200, "放空 1200"), (7950, "适中 7950"), (10800, "充满 10800")):
        ax2.text(0.94, lv, txt + " ", ha="right", va="center", fontsize=6.0,
                 color=MC.PALETTE["soc"],
                 bbox=dict(facecolor="white", edgecolor="none", alpha=0.85, pad=0.6))
    h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=6.6, framealpha=0.9)
    ax.text(0.995, 0.02,
            "极差 %.2f 元（%.3f%%）；λ* 比最便宜的放空解贵 %.2f 元（%.3f%%）\n"
            "λ 只改变模式切换点：紧急购电形态恒定 %s 天 / %s 段"
            % (rng, rng_pct, gap, 100 * gap / lo, days[0] if len(days) == 1 else "多",
               segs[0] if len(segs) == 1 else "多"),
            transform=ax.transAxes, ha="right", va="bottom", fontsize=6.2,
            bbox=dict(facecolor="white", edgecolor="none", alpha=0.85))
    fig.tight_layout()
    paths = MC.save_fig(fig, "q2_09_terminal_lambda", str(FIG_DIR))
    return {
        "name": "q2_09_terminal_lambda",
        "purpose": "Q2 终端残值 λ 机制图：8 点 λ 扫描的三级台阶（年末放空 1200 / 适中 7950 / 充满 10800），"
                   "双轴显示费用与年末 SOC，标出本文取值 λ=0.4720；说明费用对终端口径不敏感、紧急形态恒定",
        "data_source": [str(lam_path), "6对话/q2_09_终端口径机制图_数据交付.md"],
        "key_values": {
            "lam_grid": [round(float(v), 4) for v in lam],
            "total_yuan": [round(float(v), 2) for v in tot],
            "s_end_kWh": [round(float(v), 2) for v in send],
            "lambda_star": star, "lambda_star_total_yuan": round(float(tot[i_star]), 2),
            "range_yuan": round(rng, 2), "range_pct": round(rng_pct, 4),
            "gap_vs_cheapest_yuan": round(gap, 2), "gap_vs_cheapest_pct": round(100 * gap / lo, 4),
            "emg_days_constant": days, "emg_segments_constant": segs,
            "note": "λ=0.4720 行逐位复现交付值 13,252,341.09（同源自洽）；旧 09-11 λ 曲线属旧口径，未使用",
        },
        "script": "q2_fig_B_main.py",
    }, paths


FIGS = {"q2_08": fig_q2_08, "q2_09": fig_q2_09}


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
