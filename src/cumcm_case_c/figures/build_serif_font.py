# -*- coding: utf-8 -*-
r"""把本机 NotoSerifSC-VF.ttf 实例化成静态字重。

背景（实测）：本机只装了 NotoSerifSC-VF.ttf（可变字体）。matplotlib 3.11 对可变字体
只取默认实例，并报 findfont Failed to find font weight normal, now using 200。
normal / semibold / bold 三种请求实测渲染完全相同（墨量逐位一致 0.2034），
即图内与正文文字都会偏细（ExtraLight），黑白打印容易发虚。

处置：用 fontTools 的 instancer 生成静态实例（默认 wght=400 Regular，另出 700 Bold），
落到 D:\CMUCU\6对话\assets\fonts\ ，再注册给 matplotlib，使 weight="normal" 命中真 Regular。

用法：
    & $py "D:\CMUCU\6对话\code\build_serif_font.py"
"""

from __future__ import annotations

import sys
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

SRC = Path(r"C:\Windows\Fonts\NotoSerifSC-VF.ttf")
OUT_DIR = Path(r"D:\CMUCU\6对话\assets\fonts")
TARGETS = {400: "NotoSerifSC-Regular.ttf", 700: "NotoSerifSC-Bold.ttf"}
FAMILY = "Noto Serif SC"


def normalize_names(path: Path, subfamily: str, weight_class: int, bold: bool) -> None:
    """把静态实例的 name/OS2 表规范成统一字族 <FAMILY> + 子族 Regular/Bold。

    目的：让 matplotlib 的 family=FAMILY 能按 weight 在 Regular(400)/Bold(700) 之间正确选择，
    不再回落到可变字体的默认实例（wght=200）。
    """
    f = TTFont(path)
    name = f["name"]
    full = f"{FAMILY} {subfamily}"
    ps = f"{FAMILY.replace(' ', '')}-{subfamily}"
    for rec in list(name.names):
        if rec.nameID == 1:
            name.setName(FAMILY, rec.nameID, rec.platformID, rec.platEncID, rec.langID)
        elif rec.nameID == 2:
            name.setName(subfamily, rec.nameID, rec.platformID, rec.platEncID, rec.langID)
        elif rec.nameID == 4:
            name.setName(full, rec.nameID, rec.platformID, rec.platEncID, rec.langID)
        elif rec.nameID == 6:
            name.setName(ps, rec.nameID, rec.platformID, rec.platEncID, rec.langID)
        elif rec.nameID in (16, 17):          # 清掉 typographic family/subfamily，避免歧义
            name.removeNames(rec.nameID)
    os2 = f["OS/2"]
    os2.usWeightClass = weight_class
    os2.fsSelection = (os2.fsSelection & ~0b100000) | (0b100000 if bold else 0)
    head = f["head"]
    head.macStyle = (head.macStyle & ~0b1) | (0b1 if bold else 0)
    f.save(path)
    f.close()


def report_fvar(path: Path) -> None:
    f = TTFont(path, lazy=True)
    if "fvar" not in f:
        print("no fvar table")
        return
    fv = f["fvar"]
    print("axes:")
    for a in fv.axes:
        print("  tag=%s min=%s default=%s max=%s name=%s"
              % (a.axisTag, a.minValue, a.defaultValue, a.maxValue,
                 f["name"].getDebugName(a.axisNameID)))
    print("named instances: %d" % len(fv.instances))
    for i in fv.instances[:24]:
        coords = ", ".join("%s=%s" % (k, v) for k, v in i.coordinates.items())
        print("  %s (%s)" % (f["name"].getDebugName(i.subfamilyNameID), coords))
    f.close()


def build(wght: int, out_name: str) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dst = OUT_DIR / out_name
    f = TTFont(SRC)
    inst = instancer.instantiateVariableFont(f, {"wght": wght}, updateFontNames=True,
                                            inplace=False, optimize=True)
    inst.save(dst)
    inst.close()
    f.close()
    normalize_names(dst, "Bold" if wght >= 700 else "Regular", wght, wght >= 700)
    good = TTFont(dst, lazy=True)
    fam = good["name"].getDebugName(4) or good["name"].getDebugName(1)
    sub = good["name"].getDebugName(2)
    cls = good["OS/2"].usWeightClass
    good.close()
    print("  wght=%d -> %s (%.1f MB) family=%s subfamily=%s usWeightClass=%s"
          % (wght, dst, dst.stat().st_size / 1e6, fam, sub, cls))
    return dst


if __name__ == "__main__":
    print("== NotoSerifSC-VF.ttf ==")
    report_fvar(SRC)
    print("== build static instances ==")
    for w, n in TARGETS.items():
        build(w, n)
    print("DONE")
    sys.exit(0)
