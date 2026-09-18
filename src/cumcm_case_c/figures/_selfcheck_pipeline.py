# -*- coding: utf-8 -*-
r"""对话6 自检：① manifest 合并写行为；② 风格层与出图链路（serif + 缺字闸门 + smoke）。

用法：
    $env:PYTHONPATH="D:\CMUCU\rag\.deps"
    & $py "D:\CMUCU\6对话\code\_selfcheck_pipeline.py"

只写 `D:\CMUCU\6对话\output\_selftest\`（非交付）与 `output\figures\_smoke\`（非交付），
不碰任何数据源、不碰 Q2 结果文件。
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

OUT_SELFTEST = Path(r"D:\CMUCU\6对话\output\_selftest")


def check_manifest_merge() -> bool:
    """模拟三个脚本先后写同一份 manifest，验证元数据互不冲掉。"""
    from fig_manifest import Manifest

    if OUT_SELFTEST.exists():
        shutil.rmtree(OUT_SELFTEST)
    OUT_SELFTEST.mkdir(parents=True, exist_ok=True)

    # 脚本 A：两张图
    ma = Manifest(root=str(OUT_SELFTEST), group="q2")
    ma.add(name="q2_01", purpose="A 写的 q2_01", data_source=["a.json"],
           key_values={"k": 1}, script="a.py")
    ma.add(name="q2_02", purpose="A 写的 q2_02", data_source=["a.json"],
           key_values={"k": 2}, script="a.py")
    p = ma.write()

    # 脚本 B：只写自己那两张（旧版会在这里把 A 的元数据冲空）
    mb = Manifest(root=str(OUT_SELFTEST), group="q2")
    mb.add(name="q2_03", purpose="B 写的 q2_03", data_source=["b.json"],
           key_values={"k": 3}, script="b.py")
    mb.write()

    # 脚本 C：更新 q2_01（同名应被本次条目覆盖，其余保留）
    mc = Manifest(root=str(OUT_SELFTEST), group="q2")
    mc.add(name="q2_01", purpose="C 改写的 q2_01", data_source=["c.json"],
           key_values={"k": 10}, script="c.py")
    mc.write()

    d = json.loads(p.read_text(encoding="utf-8"))
    figs = {f["name"]: f for f in d["figures"]}
    ok = (
        d["count"] == 3
        and figs["q2_01"]["purpose"] == "C 改写的 q2_01"
        and figs["q2_01"]["script"] == "c.py"
        and figs["q2_02"]["purpose"] == "A 写的 q2_02"      # 未被 B/C 冲掉
        and figs["q2_02"]["script"] == "a.py"
        and figs["q2_03"]["purpose"] == "B 写的 q2_03"
        and isinstance(figs["q2_03"]["data_source"], list)
    )
    print("[manifest] 合并写自检：", "PASS" if ok else "FAIL")
    print("           count=%s  q2_01.purpose=%r  q2_02.purpose=%r  q2_03.purpose=%r"
          % (d["count"], figs["q2_01"]["purpose"], figs["q2_02"]["purpose"],
             figs["q2_03"]["purpose"]))
    return ok


def check_style_pipeline() -> bool:
    import mpl_config as MC

    MC.apply_style()
    missing = MC.verify_fonts()
    print("[style]   缺字闸门 verify_fonts() =", missing)
    ok = not missing.get("serif") and not missing.get("sans")

    paths = MC.smoke_test(r"D:\CMUCU\6对话\output\figures\_smoke")
    png, svg = Path(paths["png"]), Path(paths["svg"])
    print("[style]   smoke 出图：", png.name, png.stat().st_size, "B |",
          svg.name, svg.stat().st_size, "B")
    ok = ok and png.exists() and svg.exists() and png.stat().st_size > 10000
    return ok


def main() -> int:
    a = check_manifest_merge()
    b = check_style_pipeline()
    print("\nSELFCHECK:", "PASS" if (a and b) else "FAIL")
    return 0 if (a and b) else 1


if __name__ == "__main__":
    raise SystemExit(main())
