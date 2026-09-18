# -*- coding: utf-8 -*-
r"""对话6 · Q3 图件资产闸门（组 q3）。

检查：svg+png 双份齐全 / PNG 300dpi / manifest 覆盖被检图名 / key_values 非空。
用法：python qc_figures_q3.py [--only <name> ...]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

FIG_ROOT = Path(r"D:\CMUCU\6对话\output\figures")
GROUP = "q3"

# 终版清单（VOI 用 v2b 四臂；epochs 并入 q3_03；m 网格(E1 口径)不出图，见限度图）
EXPECTED = [
    "q3_01_day_rollout_chain", "q3_02_cost_decomposition", "q3_03_rolling_value_voi",
    "q3_04_paper_tables_graph", "q3_05_soc_year", "q3_06_adj_structure",
    "q3_07_three_layer_price", "q3_08_exec_v2b_mechanism", "q3_09_qm_parameterization",
    "q3_10_settlement_readings", "q3_12_emergency_tail", "q3_14_limits_disclosure",
    "q3_15_flow", "q3_16_rollout_timeline",
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
        ok.append("[%s] %-30s %dx%d @%.0fdpi  svg=%dB"
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
