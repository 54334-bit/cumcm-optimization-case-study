# -*- coding: utf-8 -*-
r"""对话6 图件资产闸门（Q2 组）。

检查项（与对话4 的验收口径一致，便于两条线对齐）：
1. 期望图件 svg + png 双份齐全；
2. PNG 为 300dpi、体积合理非空；
3. `q2_figures_manifest.json` 覆盖被检查图名且 key_values 非空。

用法：
    python qc_figures.py                       # 检查全部 14 张（未出的会报缺文件）
    python qc_figures.py --only q2_01 q2_02     # 只检查已出的子集
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

FIG_ROOT = Path(r"D:\CMUCU\6对话\output\figures")
GROUP = "q2"

# 规划清单（`Q2图件规划_准备稿.md` §4）：Tier A 6 张 / Tier B 4 张 / Tier C 4 张
EXPECTED: list[str] = [
    "q2_01_day_plan_exec", "q2_02_emergency_calendar", "q2_03_paper_table3",
    "q2_04_cost_structure", "q2_05_soc_year", "q2_06_curtail_split",
    "q2_07_saa_structure", "q2_08_quantile_margin", "q2_09_terminal_lambda", "q2_10_model_flow",
    "q2_11_forecast_caliber", "q2_12_irreducible_cost", "q2_13_pv_shortfall_vs_emergency",
    "q2_14_emergency_tail",
]


def check(names: list[str]) -> tuple[list[str], list[str]]:
    d = FIG_ROOT / GROUP
    ok, problems = [], []
    for n in names:
        svg, png = d / f"{n}.svg", d / f"{n}.png"
        miss = [p.name for p in (svg, png) if not p.exists()]
        if miss:
            problems.append("[%s] 缺文件 %s" % (GROUP, miss))
            continue
        if png.stat().st_size < 5000:
            problems.append("[%s] %s 体积过小 %dB" % (GROUP, png.name, png.stat().st_size))
            continue
        with Image.open(png) as im:
            dpi, (w, h) = im.info.get("dpi"), im.size
        if not dpi or min(dpi) < 290:
            problems.append("[%s] %s dpi=%s 不足 300" % (GROUP, png.name, dpi))
            continue
        ok.append("[%s] %-28s %dx%d @%.0fdpi  svg=%dB"
                  % (GROUP, n, w, h, dpi[0], svg.stat().st_size))

    mf = d / f"{GROUP}_figures_manifest.json"
    if not mf.exists():
        problems.append("[%s] 缺 manifest %s" % (GROUP, mf.name))
    else:
        try:
            payload = json.loads(mf.read_text(encoding="utf-8"))
            figs = payload.get("figures", [])
            got = {it["name"] for it in figs}
            lack = [n for n in names if n not in got]
            if lack:
                problems.append("[%s] manifest 未覆盖 %s" % (GROUP, lack))
            no_kv = [it["name"] for it in figs if not it.get("key_values")]
            if no_kv:
                problems.append("[%s] manifest 缺 key_values: %s" % (GROUP, no_kv))
        except Exception as e:  # noqa: BLE001
            problems.append("[%s] manifest 解析失败 %s: %s" % (GROUP, type(e).__name__, e))
    return ok, problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=None)
    a = ap.parse_args()
    names = a.only or EXPECTED
    unknown = [n for n in names if n not in EXPECTED]
    ok, bad = check(names)
    print("=" * 96)
    for line in ok:
        print("OK   ", line)
    for line in bad:
        print("FAIL ", line)
    for n in unknown:
        print("WARN  未在规划清单中的图名：", n)
    print("=" * 96)
    print("通过 %d 项，问题 %d 项（检查 %d 张）" % (len(ok), len(bad), len(names)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
