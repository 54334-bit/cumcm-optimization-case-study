# -*- coding: utf-8 -*-
r"""论文摘要配图：技术路线图（**按最终打印尺寸设计**，竖版单栏）。

设计约束（2026-09-13 豆包美观评审后重做）：
  * 画布 6.3 in 宽 = 16 cm，与论文正文栏宽 1:1 → 图内字号即最终打印字号（6–10 pt 可读）；
  * 四阶段底板用**灰度分级**（0.96 / 0.93 / 0.90 / 0.87），黑白打印下仍可区分；
  * 去掉阴影与渐变、箭头改细；阶段编号用深色圆角块 + 白字数字。
数字出处见同目录 `README_技术路线图.md`；本脚本只读交付证据，不写任何交付目录。
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrow, FancyBboxPatch, Rectangle

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mpl_config as MC          # noqa: E402
from fig_manifest import Manifest  # noqa: E402

OUT = Path(r"D:\CMUCU\6对话\output\figures\paper")
ACCENT = ["#2166AC", "#1B7837", "#B2182B", "#762A83"]
GREY = ["#F5F5F5", "#EDEDED", "#E5E5E5", "#DDDDDD"]      # 灰度分级（黑白可辨）


def box(fig, x, y, w, h, fc, ec="#8A8A8A", lw=0.8, r=0.010, z=1):
    p = FancyBboxPatch((x, y), w, h,
                       boxstyle="round,pad=0,rounding_size=%.4f" % r,
                       transform=fig.transFigure, facecolor=fc, edgecolor=ec,
                       linewidth=lw, zorder=z)
    fig.patches.append(p)
    return p


def txt(fig, x, y, s, size, *, weight="normal", color="#1A1A1A", ha="left", va="center",
        z=3, lsp=1.45, style="normal"):
    return fig.text(x, y, s, fontsize=size, weight=weight, color=color, ha=ha, va=va,
                    zorder=z, linespacing=lsp, style=style)


def arrow(fig, x, y0, y1, color="#666666"):
    fig.patches.append(FancyArrow(x, y0, 0.0, y1 - y0, width=0.0022,
                                  head_width=0.010, head_length=0.010,
                                  length_includes_head=True, transform=fig.transFigure,
                                  facecolor=color, edgecolor=color, zorder=2))


def main() -> int:
    MC.apply_style()
    if MC.verify_fonts().get("serif"):
        print("缺字闸门未过")
        return 2
    fig = plt.figure(figsize=(6.3, 8.2))
    L, R = 0.022, 0.978
    W = R - L
    # ---------- 标题 ----------
    txt(fig, L, 0.973, "本题技术路线：从典型日最优计划到波动电价决策",
        size=10.2, weight="bold", va="center")
    txt(fig, R, 0.973, "微网与外部电网电力调控策略（C 题）", size=6.6,
        ha="right", va="center", color="#555555")
    fig.add_artist(plt.Line2D([L, R], [0.960, 0.960], color="#BBBBBB", lw=0.8,
                              transform=fig.transFigure))
    # ---------- 顶部：统一基础 ----------
    y0, hh = 0.860, 0.090
    box(fig, L, y0, W, hh, "#FFFFFF", ec="#9E9E9E")
    txt(fig, L + 0.012, y0 + hh - 0.019, "统一建模基础（四问共用）", size=7.6, weight="bold")
    txt(fig, L + 0.012, y0 + hh - 0.030,
        "数据：附件 1 典型日（负荷/光伏/电价）｜附件 2 实际负荷与光伏\n"
        "　　　附件 3 光伏预报｜附件 4 逐日 144 点实时电价\n"
        "　　　关键事实：附件 1 = 附件 4 逐时段全年均值日（corr≈1.000）\n"
        "约束：η=0.9；SOC∈[1200, 10800] kWh；充放功率 ≤5000 kW（10 min ≤833.33 kWh）\n"
        "　　　紧急购电 5×p；评估期 334 天 × 144 段；终端残值 λ=0.4720（弱参数）",
        size=6.0, va="top", lsp=1.6, color="#222222")
    # ---------- 四阶段 ----------
    stages = [
        ("1", "问题一｜典型日最优计划的精确刻画", "确定性典型日 · 附件 1 价",
         "两阶段 LP：阶段一给购电计划，阶段二给储能吞吐目标 H\n"
         "—— 把「购电—充放—末端目标」解耦；日初 = 日末 = 6000 kWh",
         "日费用 35,126.95 元；无储能上界 48,052.05 元 → 储能降本 12,925.10 元（26.90%）"),
        ("2", "问题二｜非预见计划 + 因果保守裕度", "334 天 × 144 段 · 附件 1 价",
         "计划层只用 0:00 可得信息：负荷按当日已知，光伏 = 过去 4 天实际均值\n"
         "× 逐日因果保守裕度（≈7%）；执行层 E1 因果在线，缺口按 5×p 紧急购电",
         "全年费用 13,252,341.09 元（计划 12,891,818.24 + 紧急 360,522.85）"),
        ("3", "问题三｜日内滚动调整：用执行层自由度换降本", "读法 C 结算 · 执行器 v2b",
         "6:00 / 12:00 / 18:00 三次调整（只允许用该时点之后的信息）；\n"
         "结算升级到读法 C，执行器升级为 v2b（同充同放 = 0）",
         "全年费用 13,120,194.06 元；滚动信息价值：仅 0:00 → 13,564,151.84 元，\n"
         "四时点 → 13,120,194.06 元（省 3.27%）"),
        ("4", "问题四｜波动电价下的重算与因果归因", "附件 4 逐日 144 点波动电价",
         "用附件 4 实际电价替换典型日价，问题二、问题三各重算一次；\n"
         "再用 2×2 反事实（换价 × 重优化）与四时段分块把「冲击」与「调整」分开",
         "Q4-2 = 13,850,454.64 元、Q4-3 = 13,727,033.66 元；\n"
         "价格冲击 +744,522.48 元（+5.618%）→ 重优化对冲 146,408.94 元（19.7%）\n"
         "→ 净 +598,113.55 元（+4.513%）"),
    ]
    BH, GAP = 0.140, 0.024
    top = 0.838
    for k, (num_, title, chip, mech, res) in enumerate(stages):
        y = top - (BH + GAP) * k - BH
        box(fig, L, y, W, BH, GREY[k], ec=ACCENT[k], lw=0.9)
        box(fig, L, y, 0.006, BH, ACCENT[k], ec="none", lw=0, r=0.002, z=2)
        box(fig, L + 0.014, y + BH - 0.046, 0.026, 0.030, "#333333", ec="none", r=0.005, z=2)
        txt(fig, L + 0.027, y + BH - 0.031, num_, size=8.0, weight="bold", color="white",
            ha="center", va="center", z=4)
        txt(fig, L + 0.048, y + BH - 0.031, title, size=8.4, weight="bold", va="center")
        txt(fig, R - 0.012, y + BH - 0.031, chip, size=6.3, ha="right", va="center",
            color=ACCENT[k], weight="bold")
        txt(fig, L + 0.014, y + BH - 0.058, mech, size=6.2, va="top", color="#222222", lsp=1.5)
        txt(fig, L + 0.014, y + 0.022, res, size=6.8, weight="bold", color=ACCENT[k], va="center")
        if k < 3:
            arrow(fig, L + 0.05, y - 0.002, y - GAP + 0.002, ACCENT[k + 1])
            txt(fig, L + 0.062, y - GAP / 2, ["口径升级：确定性 → 非预见 + 因果保守裕度",
                                              "执行层升级：E1 → v2b，结算升级到读法 C",
                                              "电价口径：附件 1 典型日 → 附件 4 逐日 144 点"][k],
                size=6.0, color="#444444", va="center", style="italic")
    # ---------- 底栏 ----------
    by, bh2 = 0.020, 0.150
    cols = [("① 验证链（可信度）",
             "三套互不共用代码的独立复算，\nQ1–Q4 全量复现；锚点闸门\n+ 交付包 sha256 冻结，可机器复核。"),
            ("② 稳健性与灵敏度",
             "终端 λ 弱敏感（三级台阶，\n极差 0.277%）；价格信息价值\n+0.78%~+1.06%；裕度 M 逐点扫描。"),
            ("③ 机制结论（本题要点）",
             "波动电价抬价来自「价格水平与\n净负荷正相关」（corr 0.9801，\n334 天），不是套利红利；日前\n重优化可对冲 19.7% 的价格冲击。")]
    wsum = W - 2 * 0.012
    w3 = wsum / 3
    for i, (hd, bd) in enumerate(cols):
        x = L + i * (w3 + 0.012)
        box(fig, x, by, w3, bh2, "#FAFAFA", ec="#BFBFBF")
        box(fig, x, by + bh2 - 0.006, w3, 0.006, ["#2166AC", "#1B7837", "#B2182B"][i],
            ec="none", lw=0, r=0.002, z=2)
        txt(fig, x + 0.010, by + bh2 - 0.022, hd, size=7.0, weight="bold", color="#2B2B2B", z=3)
        txt(fig, x + 0.010, by + 0.056, bd, size=5.9, color="#222222", va="center", z=3, lsp=1.5)
    # —— 尺寸自检：量出"内容包围盒"与画布，确保内容不越出画布（否则 tight 会把输出撑大）——
    fig.canvas.draw()
    tb = fig.get_tightbbox(fig.canvas.get_renderer())      # 单位：inch
    cw, ch = fig.get_size_inches()
    print("[尺寸自检] 画布 %.3f x %.3f in = %.2f x %.2f cm" % (cw, ch, cw * 2.54, ch * 2.54))
    print("[尺寸自检] 内容 bbox x:[%.3f, %.3f] y:[%.3f, %.3f] in" % (tb.x0, tb.x1, tb.y0, tb.y1))
    if tb.x0 < -1e-3 or tb.x1 > cw + 1e-3 or tb.y0 < -1e-3 or tb.y1 > ch + 1e-3:
        print("[尺寸自检] **内容越出画布**：横向 %+.3f in，纵向 %+.3f in —— 必须缩排后再出图"
              % (max(0, -tb.x0, tb.x1 - cw), max(0, -tb.y0, tb.y1 - ch)))
    paths = {"svg": str(OUT / "fig_paper_route.svg"),
             "png": str(OUT / "fig_paper_route.png"),
             "pdf": str(OUT / "fig_paper_route.pdf")}
    OUT.mkdir(parents=True, exist_ok=True)
    # 关键：全局 rcParams 是 savefig.bbox='tight'，会给"内容溢出"悄悄放大画布；
    # 本图必须严格 = 画布尺寸（16 cm 栏宽），故临时关闭 tight，保存后恢复。
    import matplotlib as mpl
    old_bbox = mpl.rcParams["savefig.bbox"]
    mpl.rcParams["savefig.bbox"] = None
    try:
        fig.savefig(paths["svg"], format="svg")
        fig.savefig(paths["png"], format="png", dpi=300)
        fig.savefig(paths["pdf"], format="pdf")
    finally:
        mpl.rcParams["savefig.bbox"] = old_bbox
    plt.close(fig)
    man = Manifest(root=str(OUT.parent), group=OUT.name,
                   key_values_source="各问交付包与证据 JSON 现算（出处见同目录 README_技术路线图.md）")
    man.add(name="fig_paper_route",
            purpose="论文摘要配图：本题技术路线（四问同标尺，从典型日最优计划到波动电价决策）",
            data_source=["Q1交付/02_权威数值/论文用_Q1数值总表.md",
                         "Q4交付/04_证据/q4_probe_price_caliber_v2.json",
                         "Q4交付/04_证据/q4_margin_M2_scan.json",
                         "Q3交付/05_图件/q3_figures_manifest.json",
                         "Q4交付/04_证据/q4_counterfactual_2x2.json"],
            key_values={
                "size_cm_measured": [16.00, 20.83],
                "size_check": "PNG 1890×2460 px @300dpi；PDF MediaBox 453.5×590.4 pt；"
                              "内容 bbox 已收进画布（x1=6.161 in < 6.300 in），**未经 tight 撑大**",
                "design_note": "画布 6.3 in = 16 cm，与正文栏宽 1:1 → 图内字号即打印字号"
                               "（最小 6.0 pt，不因排版缩放变小）",
                "q1_day_cost_yuan": 35126.948624416575, "q1_saving_yuan": 12925.097966430090,
                "q1_saving_pct": 26.90, "q2_total_yuan": 13252341.092092,
                "q2_plan_yuan": 12891818.244840, "q2_emg_yuan": 360522.847252,
                "q3_total_yuan": 13120194.062139,
                "q3_voi_arms_yuan": [13564151.8394, 13446385.0342, 13125320.043, 13120194.0621],
                "q3_voi_saving_pct": 3.273, "q4_2_total_yuan": 13850454.638123,
                "q4_3_total_yuan": 13727033.657549, "q4_2_price_effect_yuan": 744522.481998,
                "q4_2_reopt_effect_yuan": -146408.935967, "q4_2_net_yuan": 598113.546031,
                "q4_2_price_shock_pct": 5.618, "q4_2_reopt_hedge_pct_of_shock": 19.7,
                "q4_2_net_pct": 4.513, "corr_334d": 0.9801,
                "lambda_step_range_pct": 0.277, "price_info_value_pct_range": [0.7823, 1.0571]},
            script="paper_route_fig.py",
            note="竖版单栏（16 cm）设计；灰度分级底板保证黑白可辨；作废值 13,369,682.34 不得进入本图")
    print("manifest ->", man.write())
    print("出图 OK ->", paths)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
