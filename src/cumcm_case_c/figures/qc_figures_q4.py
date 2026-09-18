# -*- coding: utf-8 -*-
r"""对话6 · Q4 图件资产闸门（组 q4）。

检查：svg+png 双份齐全 / PNG 300dpi / manifest 覆盖被检图名 / key_values 非空 /
      图内引用数字与证据 JSON 现算一致（锚点由 q4_data_frozen.py 负责，本闸门只做资产层）。
用法：python qc_figures_q4.py [--only <name> ...]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

FIG_ROOT = Path(r"D:\CMUCU\6对话\output\figures")
GROUP = "q4"

# 终版清单（6 张；Q4-2 与 Q4-3 口径分家，见 6对话\红线约束_图件自检_20260913.md E 组）
EXPECTED = [
    "q4_01_price_caliber", "q4_02_plan_heatmap", "q4_03_soc_price_7d",
    "q4_04_price_four", "q4_05_cf_2x2", "q4_06_effect_split",
]


def check(names: list[str]) -> tuple[list[str], list[str]]:
    d = FIG_ROOT / GROUP
    ok, bad = [], []
    for n in names:
        svg, png = d / f"{n}.svg", d / f"{n}.png"
        miss = [p.name for p in (svg, png) if not p.exists()]
        if miss:
            bad.append("[%s] 缺文件 %s" % (GROUP, miss))
            continue
        if png.stat().st_size < 5000:
            bad.append("[%s] %s 体积过小 %dB" % (GROUP, png.name, png.stat().st_size))
            continue
        with Image.open(png) as im:
            dpi, (w, h) = im.info.get("dpi"), im.size
        if not dpi or min(dpi) < 290:
            bad.append("[%s] %s dpi=%s 不足 300" % (GROUP, png.name, dpi))
            continue
        ok.append("[%s] %-28s %dx%d @%.0fdpi  svg=%dB"
                  % (GROUP, n, w, h, dpi[0], svg.stat().st_size))
    mf = d / f"{GROUP}_figures_manifest.json"
    if not mf.exists():
        bad.append("[%s] 缺 manifest %s" % (GROUP, mf.name))
    else:
        try:
            payload = json.loads(mf.read_text(encoding="utf-8"))
            figs = payload.get("figures", [])
            got = {it["name"] for it in figs}
            lack = [n for n in names if n not in got]
            if lack:
                bad.append("[%s] manifest 未覆盖 %s" % (GROUP, lack))
            no_kv = [it["name"] for it in figs if not it.get("key_values")]
            if no_kv:
                bad.append("[%s] manifest 缺 key_values: %s" % (GROUP, no_kv))
            # 每张图必须登记数据源与生成脚本（论文可溯源）
            no_src = [it["name"] for it in figs if not it.get("data_source")]
            if no_src:
                bad.append("[%s] manifest 缺 data_source: %s" % (GROUP, no_src))
        except Exception as e:  # noqa: BLE001
            bad.append("[%s] manifest 解析失败 %s: %s" % (GROUP, type(e).__name__, e))
    return ok, bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=None)
    a = ap.parse_args()
    names = a.only or EXPECTED
    ok, bad = check(names)
    print("=" * 96)
    for line in ok:
        print("OK   ", line)
    for line in bad:
        print("FAIL ", line)
    print("=" * 96)
    print("通过 %d 项，问题 %d 项（检查 %d 张）" % (len(ok), len(bad), len(names)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
