# -*- coding: utf-8 -*-
r"""统一绘图基线（C 题微网调度）。

用途
----
全项目所有 matplotlib 图件共用本模块，保证：字体不乱码、配色统一、
输出同时落地 SVG（矢量）与 300dpi PNG（论文用）。

使用
----
    import sys; sys.path.insert(0, r"D:\CMUCU\6对话\code")
    from mpl_config import apply_style, PALETTE, save_fig, hour_axis
    apply_style()
    fig, ax = plt.subplots(figsize=(7.0, 3.2))
    ...
    save_fig(fig, "q2_01_plan_overview", r"D:\CMUCU\6对话\output\figures\q2")

关键点
------
1. MPLCONFIGDIR 必须在 import matplotlib 之前设置，否则会命中
   <USER_HOME>\AppData\Local\matplotlib 的不可写缓存锁（本机实测报
   PermissionError）。本模块在顶部完成设置。
2. 中文字体走 matplotlib 的 font fallback 列表：拉丁/数字优先 Times
   New Roman（顶刊观感），中文回退到 SimSun / 微软雅黑。
3. 不修改任何源数据；本模块只负责绘图表现层。
"""

from __future__ import annotations

import os
from pathlib import Path

# --------------------------------------------------------------------------
# 0. 缓存目录（必须先于 matplotlib 导入设置）
# --------------------------------------------------------------------------
_MPL_CACHE = Path(r"D:\CMUCU\6对话\.mplcache")
_MPL_CACHE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_MPL_CACHE))

import matplotlib  # noqa: E402

matplotlib.use("Agg")

import matplotlib.font_manager as fm  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import MultipleLocator  # noqa: E402


# --------------------------------------------------------------------------
# 1. 字体注册与选择
# --------------------------------------------------------------------------
_FONT_CANDIDATES = [
    ("Times New Roman", r"C:\Windows\Fonts\times.ttf"),
    ("Times New Roman", r"C:\Windows\Fonts\timesbd.ttf"),
    ("SimSun", r"C:\Windows\Fonts\simsun.ttc"),
    ("SimHei", r"C:\Windows\Fonts\simhei.ttf"),
    ("Microsoft YaHei", r"C:\Windows\Fonts\msyh.ttc"),
    ("Microsoft YaHei", r"C:\Windows\Fonts\msyhbd.ttc"),
    ("Noto Sans SC", r"C:\Windows\Fonts\NotoSansSC-VF.ttf"),
    ("Noto Serif SC", r"C:\Windows\Fonts\NotoSerifSC-VF.ttf"),
]

# --------------------------------------------------------------------------
# 【对话 6 · 2026-09-11】衬线字重坑与处置（重要，勿删）
#   本机只装了可变字体 NotoSerifSC-VF.ttf，其 fvar 默认实例是 **wght=200 (ExtraLight)**
#   （实测 axes: min 200 / default 200 / max 900）。matplotlib 对可变字体**只取默认实例**，
#   会报 "findfont: Failed to find font weight normal, now using 200"，
#   且 normal / semibold / bold 三种请求渲染结果**完全相同**（墨量逐位一致 0.2034）
#   → 图内中英文全部偏细，黑白打印易发虚。
#   处置：由 code/build_serif_font.py 用 fontTools 实例化出静态
#   Regular(400) / Bold(700)，并把 name/OS2 表统一成字族 "Noto Serif SC"，
#   放在 assets/fonts/ 下；注册后 weight="normal"/"bold" 均可命中正确字重。
# --------------------------------------------------------------------------
_ASSET_FONT_DIR = Path(r"D:\CMUCU\6对话\assets\fonts")
_SERIF_STATIC = [_ASSET_FONT_DIR / "NotoSerifSC-Regular.ttf",
                 _ASSET_FONT_DIR / "NotoSerifSC-Bold.ttf"]
_FONT_CANDIDATES += [("Noto Serif SC", str(p)) for p in _SERIF_STATIC if p.exists()]


def _register_fonts() -> list[str]:
    """把本机可用的中英文字体注册进 matplotlib，返回可用族名列表。"""
    families: list[str] = []
    for name, path in _FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                fm.fontManager.addfont(path)
            except Exception:
                continue
            if name not in families:
                families.append(name)
    return families


_REGISTERED = _register_fonts()

# 实测结论（matplotlib 3.11，本机）：逐字形 fallback 不生效，字体列表只会命中
# 第一个可用族，缺字直接报 "Glyph missing"。因此必须选「中文 + 拉丁 + 数学符号
# 全覆盖」的单一字体，而不是指望 Times + 宋体混排。
#   Noto Serif SC （静态 Regular/Bold）：中西文同族衬线、零缺字 → **默认（全项目统一）**
#   Microsoft YaHei：零缺字告警（含 U+2212），现代无衬线 → 备选（serif=False）
#   SimSun        ：仅缺 U+2212（由 axes.unicode_minus=False 规避），最后备用
_SANS_PRIMARY = next((f for f in ("Microsoft YaHei", "Noto Sans SC", "SimHei")
                      if f in _REGISTERED), "DejaVu Sans")
# 注意：SimSun/SimHei 缺 U+2212，仅作后备；Noto Serif SC 中文与符号全覆盖，优先。
_SERIF_PRIMARY = next((f for f in ("Noto Serif SC", "SimSun")
                       if f in _REGISTERED), "DejaVu Serif")
FONT_SANS = [_SANS_PRIMARY, "DejaVu Sans"]
FONT_SERIF = [_SERIF_PRIMARY, "DejaVu Serif"]

# 对话 6 统一风格：**默认衬线**（Noto Serif SC，中西文同族衬线，与论文正文宋体观感一致）。
# 全项目图件统一此基准；需要无衬线的场景显式 apply_style(serif=False)。
SERIF_DEFAULT = True


# --------------------------------------------------------------------------
# 2. 语义配色（本题专用，色盲友好）
# --------------------------------------------------------------------------
PALETTE: dict[str, str] = {
    "price":     "#B2182B",  # 电价：砖红
    "load":      "#2166AC",  # 小区负载：深蓝
    "pv":        "#E8A33D",  # 光伏：琥珀
    "grid":      "#762A83",  # 计划购电：紫
    "charge":    "#1B7837",  # 充电：绿
    "discharge": "#D6604D",  # 放电：橙红
    "soc":       "#35978F",  # 储电量 SOC：青
    "curtail":   "#9E9E9E",  # 弃光/弃电：灰
    "emer":      "#CC0000",  # 紧急购电：正红
    "net":       "#4D4D4D",  # 净负荷：深灰
    "residual":  "#8C6D31",  # 残值/对偶 λ：土黄
    "bound":     "#BDBDBD",  # 边界/参考线：浅灰
    "baseline":  "#7F7F7F",  # 对照基线
}

# 序列色（多情景、多灵敏度场景）
SEQ_BLUE = ["#08306B", "#2171B5", "#6BAED6", "#C6DBEF"]
SEQ_WARM = ["#7F2704", "#D94801", "#FD8D3C", "#FDD0A2"]


# --------------------------------------------------------------------------
# 3. 统一 rcParams
# --------------------------------------------------------------------------
def apply_style(*, serif: bool | None = None, small: bool = False) -> None:
    """套用统一科研风格。

    serif=None（默认） ：取模块常量 SERIF_DEFAULT（对话 6 起为 True）。
    serif=True         ：衬线 Noto Serif SC（静态 Regular/Bold），中西文同族、与正文宋体一致。
    serif=False        ：微软雅黑无衬线（备选）。
    """
    if serif is None:
        serif = SERIF_DEFAULT
    base = 8.0 if small else 9.5
    family = "serif" if serif else "sans-serif"
    plt.rcParams.update({
        # 字体
        "font.family": family,
        "font.serif": FONT_SERIF,
        "font.sans-serif": FONT_SANS,
        # 关键：SimSun/SimHei 缺 U+2212，关闭 unicode_minus 用 ASCII 连字符替代
        "axes.unicode_minus": False,
        "font.size": base,
        "axes.titlesize": base + 1.0,
        "axes.labelsize": base,
        "xtick.labelsize": base - 1.0,
        "ytick.labelsize": base - 1.0,
        "legend.fontsize": base - 1.0,
        "figure.titlesize": base + 2.0,
        # 数学字体：衬线配 stix，无衬线配 stixsans，避免与正文观感打架
        "mathtext.fontset": "stix" if serif else "stixsans",
        "mathtext.default": "it",
        # 布局
        "figure.figsize": (7.0, 3.4),
        "figure.dpi": 120,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.03,
        "figure.constrained_layout.use": False,
        # 轴
        "axes.linewidth": 0.8,
        "axes.edgecolor": "#333333",
        "axes.labelcolor": "#111111",
        "axes.titlepad": 5.0,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": "#DDDDDD",
        "grid.linewidth": 0.6,
        "grid.alpha": 0.9,
        "grid.linestyle": "-",
        # 刻度：朝内、细、顶右不留框
        "xtick.direction": "in",
        "ytick.direction": "in",
        "xtick.major.size": 3.0,
        "ytick.major.size": 3.0,
        "xtick.minor.size": 1.6,
        "ytick.minor.size": 1.6,
        "xtick.major.width": 0.8,
        "ytick.major.width": 0.8,
        "xtick.top": False,
        "ytick.right": False,
        "axes.spines.top": False,
        "axes.spines.right": False,
        # 线
        "lines.linewidth": 1.4,
        "lines.markersize": 3.5,
        "lines.solid_capstyle": "round",
        # 图例
        "legend.frameon": False,
        "legend.handlelength": 1.8,
        "legend.labelspacing": 0.35,
        "legend.columnspacing": 1.1,
        # 输出
        # SVG 存字形轮廓：不依赖阅读端字体、杜绝缺字，代价是文字不可再编辑
        "svg.fonttype": "path",
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    })


# --------------------------------------------------------------------------
# 4. 时间轴助手（本题统一 144 个 10 分钟区间，口径 R）
# --------------------------------------------------------------------------
def hour_axis(ax, *, ticks_hours=range(0, 25, 2), label: str = "时间",
              minor_every_hour: bool = True, rotate: float = 0.0):
    """把 x 轴标成 [0,144] 区间号 → 小时刻度（区间 t 起点 = t/6 小时）。"""
    ax.set_xlim(0, 144)
    ax.set_xticks([h * 6 for h in ticks_hours])
    ax.set_xticklabels([f"{h:d}:00" for h in ticks_hours], rotation=rotate)
    if minor_every_hour:
        ax.xaxis.set_minor_locator(MultipleLocator(6))
    ax.set_xlabel(label)
    return ax


def interval_to_hhmm(t: int) -> str:
    """区间号 t（0-based，口径 R）→ 区间起点 'HH:MM'。"""
    m = t * 10
    return f"{m // 60:d}:{m % 60:02d}"


# --------------------------------------------------------------------------
# 5. 导出助手
# --------------------------------------------------------------------------
def save_fig(fig, name: str, outdir: str, *, png_dpi: int = 300,
             also_pdf: bool = False, close: bool = True) -> dict[str, str]:
    """同时导出 SVG + 300dpi PNG（+可选 PDF），返回路径字典。"""
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    paths = {"svg": str(out / f"{name}.svg"), "png": str(out / f"{name}.png")}
    fig.savefig(paths["svg"], format="svg")
    fig.savefig(paths["png"], format="png", dpi=png_dpi)
    if also_pdf:
        paths["pdf"] = str(out / f"{name}.pdf")
        fig.savefig(paths["pdf"], format="pdf")
    if close:
        plt.close(fig)
    return paths


def smoke_test(outdir: str = r"D:\CMUCU\4对话\output\figures\_smoke") -> dict[str, str]:
    """自检：中英文字体 + 数学公式 + 中文负号 + 导出链路。"""
    apply_style()
    fig, ax = plt.subplots(figsize=(5.2, 2.6))
    x = [t / 6 for t in range(144)]
    import math
    ax.plot(x, [math.sin(2 * math.pi * v / 24) for v in x],
            color=PALETTE["load"], label="小区负载 Load")
    ax.plot(x, [math.cos(2 * math.pi * v / 24) for v in x],
            color=PALETTE["pv"], label="光伏预测 PV")
    ax.axhline(0, color=PALETTE["bound"], lw=0.8)
    ax.set_title("字体自检：中文 + Times + 数学 $\\lambda^{*}=0.4720$ 元/kWh")
    ax.set_ylabel("功率 (kW)")
    ax.set_xlabel("时间 (h)")
    ax.text(0.02, 0.05, "负号测试：−1.5 ~ 10.8 kWh", transform=ax.transAxes)
    ax.legend(loc="upper right", ncol=2)
    return save_fig(fig, "style_smoke", outdir)


def verify_fonts() -> dict[str, list[str]]:
    """字体闸门：渲染中英数混排，捕获缺字告警。返回 {模式: [缺字告警]}。"""
    import warnings

    probe = ("中文：微网购电策略 储能充放电效率 计划购电量 紧急购电 净负荷 弃光 "
             "0.4720 元/kWh，负号 −1.5，区间 0:00−24:00")
    out: dict[str, list[str]] = {}
    for mode, serif in (("sans", False), ("serif", True)):
        apply_style(serif=serif)
        fig, ax = plt.subplots(figsize=(6.4, 1.2))
        ax.axis("off")
        ax.text(0.01, 0.68, probe, fontsize=9)
        ax.text(0.01, 0.30, r"$J^{*}=\sum_t p_t G_t$   $\eta=0.9$   $\lambda^{*}$   $\Delta S$",
                fontsize=9)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            fig.canvas.draw()
            plt.close(fig)
        msgs = [str(w.message) for w in caught
                if "missing from font" in str(w.message) or "does not have a glyph" in str(w.message)]
        out[mode] = sorted(set(msgs))
    return out


if __name__ == "__main__":
    print("cachedir:", matplotlib.get_cachedir())
    print("registered fonts:", _REGISTERED)
    print("sans primary:", _SANS_PRIMARY, "| serif primary:", _SERIF_PRIMARY)
    gate = verify_fonts()
    for mode, msgs in gate.items():
        print(f"font gate [{mode}]: {'PASS (0 缺字)' if not msgs else 'FAIL ' + str(msgs[:3])}")
    print("saved:", smoke_test())
