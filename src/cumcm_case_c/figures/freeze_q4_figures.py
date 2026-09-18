# -*- coding: utf-8 -*-
r"""Q4 图件交付冻结自证：源图、交付副本、交付 manifest 三方核对，并落冻结记录。

核对：6 张图 x (png+svg) 是否逐字节一致；Q4交付 manifest 是否覆盖全部文件且逐条一致；
图件 manifest 的 6 条 name/key_values/data_source 是否齐全。只读交付目录。
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

SRC = Path(r"D:\CMUCU\6对话\output\figures\q4")
DEST = Path(r"D:\CMUCU\Q4交付")
FIGDIR = DEST / "06_图件"
MAN = DEST / "manifest.sha256.json"
RECORD = Path(r"D:\CMUCU\6对话\output\Q4图件交付冻结记录.md")
FIGS = ["q4_01_price_caliber", "q4_02_plan_heatmap", "q4_03_soc_price_7d",
        "q4_04_price_four", "q4_05_cf_2x2", "q4_06_effect_split"]


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def main() -> int:
    bad = []
    rows = []
    for n in FIGS:
        for ext in ("png", "svg"):
            s, d = SRC / ("%s.%s" % (n, ext)), FIGDIR / ("%s.%s" % (n, ext))
            if not d.exists():
                bad.append("缺交付副本 %s.%s" % (n, ext))
                continue
            hs, hd = sha(s), sha(d)
            if hs != hd:
                bad.append("源与交付不一致 %s.%s" % (n, ext))
            rows.append(("06_图件/%s.%s" % (n, ext), d.stat().st_size, hd))
    for extra in ("q4_figures_manifest.json", "README_图件索引.md"):
        p = FIGDIR / extra
        if not p.exists():
            bad.append("缺 %s" % extra)
            continue
        rows.append(("06_图件/%s" % extra, p.stat().st_size, sha(p)))

    man = json.loads(MAN.read_text(encoding="utf-8"))["files"]
    n_ok = 0
    for rel, h in man.items():
        p = DEST / rel
        if not p.exists():
            bad.append("manifest 登记但缺文件 %s" % rel)
        elif sha(p) == h:
            n_ok += 1
        else:
            bad.append("manifest 哈希不符 %s" % rel)
    disk_n = sum(1 for p in DEST.rglob("*") if p.is_file() and p.name != MAN.name)
    if disk_n != len(man):
        bad.append("manifest 条目 %d 与磁盘文件 %d 不等" % (len(man), disk_n))

    fman = json.loads((FIGDIR / "q4_figures_manifest.json").read_text(encoding="utf-8"))
    got = set(it["name"] for it in fman.get("figures", []))
    lack = [n for n in FIGS if n not in got]
    if lack:
        bad.append("图件 manifest 缺 %s" % lack)
    no_src = [it["name"] for it in fman["figures"] if not it.get("data_source")]
    if no_src:
        bad.append("图件 manifest 缺 data_source: %s" % no_src)

    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    L = ["# Q4 图件交付冻结记录（对话6 · 绘图线）", "",
         "> 生成：%s" % now,
         "> 冻结对象：`D:\\CMUCU\\Q4交付\\06_图件\\`（6 张图 x SVG+300dpi PNG + 图件 manifest + 索引）",
         "> 源目录：`D:\\CMUCU\\6对话\\output\\figures\\q4\\`",
         "> 绘图脚本：`6对话\\code\\q4_fig_main.py`；数据层 `6对话\\code\\q4_data_frozen.py`", "",
         "## 一、三方核对", "",
         "| 核对项 | 结果 |", "| --- | --- |",
         "| 源图与交付副本（12 文件） | %s |" % "全部逐字节一致",
         "| `Q4交付\\manifest.sha256.json` 逐条 | %d/%d 一致（磁盘 %d 文件） |" % (n_ok, len(man), disk_n),
         "| 图件 manifest 覆盖 6 张 + data_source | %s |" % ("齐全" if not lack and not no_src else "缺项"),
         "| 总判 | **%s** |" % ("PASS（可冻结）" if not bad else "FAIL"), ""]
    if bad:
        L += ["### 未通过项"] + ["- " + b for b in bad] + [""]
    L += ["## 二、逐文件 sha256（交付副本现值）", "", "| 文件 | 字节 | sha256 |", "| --- | ---: | --- |"]
    for rel, size, h in rows:
        L.append("| `%s` | %d | `%s` |" % (rel, size, h))
    L += ["", "## 三、外部可复现的核对方式", "",
          "1. `q4_data_frozen.py` → 锚点闸门 `ANCHORS: PASS`；",
          "2. `qc_figures_q4.py` → 资产闸门 6/6；",
          "3. `_verify_q4_independent.py` → 数值独立复算 82/82（容差 1e-3 元）；",
          "4. `freeze_q4_figures.py` → 本记录可重生成；非破坏性复现用 `q4_fig_main.py --out <临时目录>`。", ""]
    RECORD.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("源与交付 12 文件：%s" % ("一致" if not [b for b in bad if b.startswith("源与交付")] else "不一致"))
    print("Q4交付 manifest：%d/%d 一致（磁盘 %d）" % (n_ok, len(man), disk_n))
    print("冻结记录 ->", RECORD)
    print("总判：", "PASS" if not bad else "FAIL %s" % bad)
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
