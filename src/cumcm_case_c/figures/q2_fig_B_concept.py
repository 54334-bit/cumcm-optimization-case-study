# -*- coding: utf-8 -*-
r"""Q2 概念示意图草稿（painter · 对话6 图件线 R3 · 2026-09-12）。

产出（**草稿目录**，不写 manifest、不进交付，由主对话合入）：
    _draft/q2_07_saa_structure.{svg,png}   两阶段随机规划结构示意
    _draft/q2_10_model_flow.{svg,png}      Q2 全流程与双轨验证

口径：主口径 = 非预见 + 因果保守裕度（`5对话\交付说明_Q2_因果裕度非预见.md`）。
      图内数值只取该交付说明 §1/§2 已背书的参数与主口径结果，不出现任何旧口径数字。

用法：
    $env:PYTHONPATH="D:\CMUCU\rag\.deps"; $env:PYTHONIOENCODING='utf-8'
    & $py "D:\CMUCU\6对话\output\figures\q2\_draft\q2_concept_diagrams.py"
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

sys.path.insert(0, r"D:\CMUCU\6对话\code")
import mpl_config as MC  # noqa: E402

OUT = Path(r"D:\CMUCU\6对话\output\figures\q2")      # 已由主对话合入交付目录（原为 _draft）
P = MC.PALETTE


# ---------------------------------------------------------------------------
# 版面助手（坐标系统一 0–100 × 0–100，便于按比例排版）
# ---------------------------------------------------------------------------
def canvas(w: float, h: float):
    fig = plt.figure(figsize=(w, h))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    return fig, ax


def panel(ax, x0, y0, x1, y1, *, title=None, lines=(), fc="#FFFFFF",
          ec="#666666", ls="-", lw=0.9, tfs=8.0, bfs=6.7, tcol="#111111",
          hatch=None, radius=1.6, zorder=2, tpad=2.0, lsp=1.55):
    """圆角信息框：标题（小号）在上，正文行块整体居中。"""
    ax.add_patch(FancyBboxPatch(
        (x0, y0), x1 - x0, y1 - y0,
        boxstyle="round,pad=0,rounding_size=%.2f" % radius,
        fc=fc, ec=ec, ls=ls, lw=lw, hatch=hatch, zorder=zorder))
    cx = (x0 + x1) / 2.0
    top = y1
    if title:
        ax.text(cx, y1 - tpad, title, ha="center", va="top", fontsize=tfs,
                color=tcol, zorder=zorder + 1)
        top = y1 - tpad - tfs * 0.30
    if lines:
        ax.text(cx, (y0 + top) / 2.0, "\n".join(lines), ha="center", va="center",
                fontsize=bfs, color="#222222", linespacing=lsp, zorder=zorder + 1)


def arrow(ax, x0, y0, x1, y1, *, color="#555555", lw=1.0, ls="-", rad=0.0, zorder=3):
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0), zorder=zorder,
                arrowprops=dict(arrowstyle="-|>", color=color, lw=lw, ls=ls,
                                shrinkA=0, shrinkB=0,
                                connectionstyle="arc3,rad=%.3f" % rad))


def label(ax, x, y, s, *, fs=6.6, color="#444444", ha="center", va="center",
          rot=0, zorder=4):
    ax.text(x, y, s, ha=ha, va=va, fontsize=fs, color=color, rotation=rot, zorder=zorder)


# ---------------------------------------------------------------------------
# q2_07 两阶段随机规划结构示意
# ---------------------------------------------------------------------------
def fig_q2_07() -> dict:
    fig, ax = canvas(7.4, 5.6)
    fig.suptitle("Q2 两阶段随机规划结构示意：here-and-now 计划层 + 情景 recourse + 终端价值项",
                 fontsize=10.0, y=0.985)

    # ---- 行 A：可用信息 vs 当日未发生（信息壁垒） ----
    panel(ax, 1.5, 72.5, 62.0, 93.5, title="(a) 决策时点 d 日 0:00：可得信息（计划层的全部输入）",
          fc="#F4F8FD", ec=P["load"], tcol=P["load"], tfs=7.8, tpad=1.8)
    label(ax, 31.7, 88.6, "点预报 = 过去 4 天实际光伏均值 × (1 − 因果裕度)",
          fs=6.4, color=P["load"])
    info = [
        (2.6, 21.6, "附件1 电价曲线", ["p_t（144 段/日）", "当天即已知"]),
        (22.8, 41.8, "光伏点预报", ["过去 4 天实际", "光伏曲线的均值"]),
        (43.0, 61.0, "因果保守裕度", ["过去 28 天相对预报", "误差的 20% 分位数", "（逐日重估）"]),
    ]
    for x0, x1, ti, ln in info:
        panel(ax, x0, 76.9, x1, 86.4, title=ti, lines=ln, fc="#FFFFFF",
              ec=P["load"], tfs=6.6, bfs=5.9, radius=1.1, tpad=1.1, lsp=1.45)
    label(ax, 31.7, 74.4, "负荷曲线：题面未给负荷预报，按当日已知处理（不引入未来信息）",
          fs=6.0, color="#555555")

    panel(ax, 64.5, 72.5, 98.5, 93.5,
          title="(b) 计划层看不到的（当日尚未发生）", ls="--",
          fc="#FDF3F3", ec=P["emer"], tcol=P["emer"], tfs=7.8, tpad=1.8)
    ax.text(81.5, 86.2, "d 日实际光伏出力", ha="center", va="center",
            fontsize=6.6, color="#333333", zorder=4)
    ax.text(81.5, 82.8, "d 日实际负荷", ha="center", va="center",
            fontsize=6.6, color="#333333", zorder=4)
    ax.text(81.5, 78.0, "→ 仅结算（执行）阶段可见\n→ 计划层不得使用", ha="center",
            va="center", fontsize=6.2, color=P["emer"], linespacing=1.6, zorder=4)

    ax.plot([63.3, 63.3], [72.5, 93.5], ls="--", lw=1.0, color=P["emer"], zorder=1)
    label(ax, 63.3, 70.6, "信息壁垒：不预见性", fs=6.4, color=P["emer"])

    # ---- 行 B：第一阶段 here-and-now ----
    panel(ax, 6.0, 51.0, 94.0, 68.5,
          title="(c) 第一阶段 here-and-now：全天共享的 G_plan（先于情景实现，一次定好）",
          fc="#F6F2F8", ec=P["grid"], tcol=P["grid"], tfs=7.8, tpad=1.8)
    ax.text(50.0, 61.5,
            "决策变量  G_plan,t（t = 1…144）：当天 144 段购电计划一次性确定，"
            "对任何情景实现都不再改变；\n同一组 G_plan 必须同时满足储能容量 [1200, 10800] kWh、"
            "功率 ≤ 5000 kW 与 SOC 链式递推。",
            ha="center", va="center", fontsize=6.6, color="#222222",
            linespacing=1.6, zorder=4)
    ax.text(50.0, 55.8,
            r"$\min\ \sum_{t} p_t\,G_{plan,t}\ +\ \mathbb{E}_{\xi}\left[Q(G_{plan},\xi)\right]\ -\ \lambda\,s_T$",
            ha="center", va="center", fontsize=9.0, color="#111111", zorder=4)
    label(ax, 50.0, 52.8, "终端价值项 − λ·s_T：储能残值抵扣（同一电价对偶口径，非硬性终端约束）",
          fs=6.1, color=P["residual"])

    # ---- 行 C：情景 recourse ----
    ax.text(50.0, 48.2, "情景集 Ξ：计划层只能用 (a) 的可得信息指定情景，"
                        "ξ 的实现值在计划之后才揭晓",
            ha="center", va="center", fontsize=6.4, color="#444444", zorder=6,
            bbox=dict(facecolor="white", edgecolor="none", pad=1.1))
    sc = [(2.0, 31.0, "情景 ξ(1)：光伏实现偏低",
           ["第二阶段 recourse：给定", "G_plan 与 ξ，选择 H_t / C_t / D_t",
            "Q = Σ_t 5·p_t·H_t", "（缺口按当时电价 5 倍紧急购电）"]),
          (34.5, 65.5, "情景 ξ(2)：接近点预报",
           ["富余电量先充电", "再放电供负荷", "仍富余则弃光伏",
            "（充电 → 放电 → 弃光）"]),
          (69.0, 98.0, "情景 ξ(3)：光伏实现偏高",
           ["计划购电偏保守", "乐观情景下", "弃光伏与弃计划电",
            "同时出现的代价"])]
    for x0, x1, ti, ln in sc:
        panel(ax, x0, 29.5, x1, 45.0, title=ti, lines=ln, fc="#FFFFFF",
              ec=P["grid"], tfs=6.9, bfs=6.1, radius=1.2, tpad=1.4)
        arrow(ax, 50.0, 50.6, (x0 + x1) / 2.0, 45.3, color=P["grid"], lw=1.0, zorder=5)

    # ---- 行 D：本文主口径的落地 ----
    panel(ax, 2.0, 13.0, 98.0, 27.5,
          title="(d) 本文主口径的落地：情景层退化为「按可得信息构造的单条可执行点预报」",
          fc="#F5FAF5", ec=P["charge"], tcol=P["charge"], tfs=7.8, tpad=1.8)
    ax.text(50.0, 21.8,
            "计划层：用 (a) 的可得信息生成点预报（不预见、可复现）→ 求解全天 G_plan；"
            "执行层：用附件2 当天实际负荷与实际光伏结算，缺口按当时电价 5 倍紧急购电。",
            ha="center", va="center", fontsize=6.6, color="#222222", zorder=4)
    ax.text(50.0, 17.2,
            "全年购电费用 13,252,341.09 元 ＝ 计划购电费 12,891,818.24 元 ＋ 紧急购电费 360,522.85 元；"
            "紧急购电 242 天 / 375 段 / 55,801.05 kWh；年末 SOC 7,950.0 kWh。",
            ha="center", va="center", fontsize=6.6, color="#111111", zorder=4)
    label(ax, 50.0, 14.4, "完全信息口径（计划直接用当天实际光伏）不具可执行性，只作理想下界，不作主结果。",
          fs=6.0, color="#666666")

    label(ax, 50.0, 8.8,
          "数值来源：《交付说明_Q2_因果裕度非预见》§1 参数与 §2 主口径结果；旧口径数字不参与本图。",
          fs=6.0, color="#666666")
    label(ax, 50.0, 5.2,
          "本图为方法结构示意（不表示已对情景集求期望最优）：主口径把 Ξ 收缩为单条点预报，"
          "Q 层退化为确定性执行。",
          fs=6.0, color="#666666")

    return MC.save_fig(fig, "q2_07_saa_structure", str(OUT))


# ---------------------------------------------------------------------------
# q2_10 Q2 全流程与双轨验证
# ---------------------------------------------------------------------------
def fig_q2_10() -> dict:
    fig, ax = canvas(7.6, 4.6)
    fig.suptitle("Q2 全流程与双轨验证：数据 → 预报构造 → 计划层 → 结算/执行 → 物化 → CP5（主口径：非预见 + 因果裕度）",
                 fontsize=9.4, y=0.975)

    stages = [
        (1.0, 18.0, "① 数据层",
         ["附件1 电价曲线 p_t", "（144 段）", "附件2 实际负荷 / 光伏", "（334 天 × 144 段）"]),
        (20.5, 37.5, "② 预报构造",
         ["光伏点预报 =", "过去 4 天实际均值", "× (1 − 因果裕度)", "裕度 = 过去 28 天相对", "预报误差 20% 分位数"]),
        (40.0, 57.0, "③ 计划层（0:00）",
         ["min Σ_t p_t·G_plan,t", "+ E[Q] − λ·s_T", "s.t. 容量 [1200,10800]", "功率 ≤ 5000 kW", "SOC 链式递推"]),
        (59.5, 76.5, "④ 结算 / 执行层",
         ["用实际负荷 / 光伏", "缺口 → 5 倍价紧急购电", "富余 → 先充电、再弃光", "得 H_t / C_t / D_t"]),
        (79.0, 99.0, "⑤ 交付物",
         ["物化 result2.xlsx", "表1 计划购电", "表2 充放电", "表3 紧急购电段"]),
    ]
    for x0, x1, ti, ln in stages:
        panel(ax, x0, 62.0, x1, 90.0, title=ti, lines=ln, fc="#F7F9FC",
              ec=P["load"], tfs=7.4, bfs=6.3, radius=1.3, tpad=1.5)
    for i in range(len(stages) - 1):
        arrow(ax, stages[i][1] + 0.4, 76.0, stages[i + 1][0] - 0.6, 76.0,
              color=P["load"], lw=1.1)

    # ---- 双轨验证 ----
    ax.text(50.0, 57.2, "双轨验证（同一份 result2.xlsx 反解，互相独立）",
            ha="center", va="center", fontsize=7.0, color="#333333", zorder=6,
            bbox=dict(facecolor="white", edgecolor="none", pad=1.8))

    panel(ax, 2.0, 24.0, 48.5, 52.0, title="物理轨 · CP5",
          fc="#F5FAF5", ec=P["charge"], tcol=P["charge"], tfs=8.0, tpad=2.0)
    ax.text(25.25, 37.0,
            "① SOC 链式自洽：s_0 → s_1 按 η = 0.9 递推，\n"
            "   与表2 充放电量逐段复算一致；\n"
            "② 边界复核：SOC ∈ [1200, 10800] kWh、\n"
            "   充放电功率 ≤ 5000 kW；\n"
            "③ 表3 段复现：同日相邻正区间合并，\n"
            "   紧急时段与电量逐段对齐。",
            ha="center", va="center", fontsize=6.5, color="#222222",
            linespacing=1.65, zorder=4)

    panel(ax, 51.5, 24.0, 98.0, 52.0, title="经济轨 · 费用恒等式",
          fc="#F6F2F8", ec=P["grid"], tcol=P["grid"], tfs=8.0, tpad=2.0)
    ax.text(74.75, 37.0,
            "① 费用恒等式：\n"
            "   12,891,818.24 + 360,522.85\n"
            "   = 13,252,341.09 元；\n"
            "② 电量口径：计划购电 21,283,432.62 kWh、\n"
            "   紧急购电 242 天 / 375 段 / 55,801.05 kWh；\n"
            "③ 年末 SOC 7,950.0 kWh（终端价值口径）。",
            ha="center", va="center", fontsize=6.5, color="#222222",
            linespacing=1.65, zorder=4)

    arrow(ax, 50.0, 61.4, 50.0, 52.8, color="#666666", lw=1.0, ls="--", zorder=5)
    arrow(ax, 50.0, 23.4, 50.0, 18.6, color="#666666", lw=1.0, ls="--", zorder=5)
    label(ax, 51.8, 21.2, "两轨不一致即回退修正", fs=6.0, color="#666666", ha="left")

    ax.text(50.0, 14.5,
            "闭环：物理轨与经济轨全部通过 → 冻结口径并进入交付；任一轨不通过 → 回到 ③ 计划层修正后重跑（迭代有上限，不无界返工）。",
            ha="center", va="center", fontsize=6.4, color="#333333", zorder=4)
    ax.text(50.0, 8.5,
            "数值来源：《交付说明_Q2_因果裕度非预见》§1 参数与 §2 主口径结果（全年 13,252,341.09 元）。",
            ha="center", va="center", fontsize=6.0, color="#666666", zorder=4)
    ax.text(50.0, 4.5,
            "旧口径（已作废）的数字一律不在本图中出现，口径与全部数值以该交付说明为准。",
            ha="center", va="center", fontsize=6.0, color="#999999", zorder=4)

    return MC.save_fig(fig, "q2_10_model_flow", str(OUT))


def main() -> int:
    MC.apply_style()
    gate = MC.verify_fonts()
    if gate.get("serif"):
        print("缺字闸门未过：", gate)
        return 2
    print("字体闸门 PASS（serif 0 缺字）")
    from fig_manifest import Manifest

    man = Manifest(root=str(OUT.parent), group=OUT.name)
    for fn in (fig_q2_07, fig_q2_10):
        p = fn()
        print("OK ->", p["png"])
        name = Path(p["png"]).stem
        if name == "q2_07_saa_structure":
            purpose = ("Q2 两阶段随机规划结构示意：here-and-now 的 0:00 全天计划 + 情景 recourse + "
                       "终端价值项；突出「计划层看不到当天实际光伏，只能用可得信息」的主口径特征（概念图，无数值结论）")
        else:
            purpose = ("Q2 全流程与双轨验证：数据（附件1 电价 / 附件2 实际）→ 预报构造（过去 4 天均值 × 因果裕度）"
                       "→ 计划层 → 结算/执行（实际值、5 倍紧急购电）→ 物化 result2.xlsx → 物理轨/经济轨验证（概念图）")
        man.add(name=name, purpose=purpose,
                data_source=["5对话/交付说明_Q2_因果裕度非预见.md §0/§1（口径声明）",
                             "6对话/Q2最终裁决与可用数字_对话5到6对话.md（关键数字）"],
                key_values={"caliber": "非预见 + 因果保守裕度（主口径）",
                            "total_yuan": 13252341.09, "J_plan_yuan": 12891818.24,
                            "J_emg_yuan": 360522.85, "QG_kWh": 21283432.62,
                            "emg_days": 242, "emg_spans": 375, "emg_kWh": 55801.05,
                            "note": "概念示意图：图中数值仅取自交付说明/裁决书的主口径值，不含任何旧口径数字"},
                script="q2_fig_B_concept.py")
    print("manifest ->", man.write())
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
