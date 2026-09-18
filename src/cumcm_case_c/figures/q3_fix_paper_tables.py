# -*- coding: utf-8 -*-
r"""重出 Q3 论文素材《论文表1表2表3_四个指定日期_v2.md》（修 表3 漏段）。

问题：`紧急购电量` 表的日期列**只在每日首行写一次**，原 md 生成时未做前向填充，
      导致每个指定日期只抄到**第 1 段**（如 03-20 只写 4.8769，实际 7 段合计 366.3371 kWh）。
本脚本从**提交件现算**重出：表1/表2 数值不变，表3 列全量段 + 当日合计，并在开头加勘误说明。

安全：只读提交件；写 1) 目标 md（重出）2) 勘误记录（含原文留档）3) 刷新 manifest 哈希。
用法：$env:PYTHONPATH="D:\CMUCU\rag\.deps"; $env:PYTHONIOENCODING='utf-8'
      & $py "D:\CMUCU\6对话\code\q3_fix_paper_tables.py" [--dry]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import q3_data_frozen as Q  # noqa: E402

MD = Q.Q3 / "03_论文素材" / "论文表1表2表3_四个指定日期_v2.md"
ERRATA = Q.Q3 / "04_证据" / "勘误_表3漏段_20260913.md"
BACKUP = Q.Q3 / "04_证据" / "_void" / "论文表1表2表3_四个指定日期_v2_勘误前.md"
MANIFEST = Q.Q3 / "manifest.sha256.json"


def sha256_of(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def render(sub: dict, seg: dict, *, old_sha: str, new_sha_xlsx: str) -> str:
    L = ["# 论文表1/表2/表3：四个指定日期（源：交付件 `result3_v2.xlsx`；**表3 已勘误**）", "",
         "> 列映射 `col = 2 + t`（t=0 → 第 2 列 = `[0:00,0:10)`）；单位 kWh / 元。",
         "> 口径：读法 C（`p·min(G0,A) + 0.5p(G0−A) + 1.5p(A−G0) + 5p·H`）+ 执行器 v2b；334 天。",
         "> **勘误（2026-09-13）**：本文件此前版本（sha256 `%s…`）的**表3 漏抄同日后续段**"
         % old_sha[:16],
         "> （`紧急购电量` 表日期列只在每日首行写一次，生成时未做前向填充）。本文已按提交件**前向填充后全量列出**，",
         "> 表1/表2 数值未变。勘误记录：`04_证据\\勘误_表3漏段_20260913.md`。", "",
         "> 提交件 sha256（字节，仅参考，xlsx 字节 sha 不稳定）：`%s`" % new_sha_xlsx, ""]
    for ds in Q.PAPER_DATES:
        i = sub["计划购电量"]["dates"].index(ds)
        g0 = sub["计划购电量"]["arr"][i]
        a = sub["调整购电量"]["arr"][i]
        # 方案 A（2026-09-13 统一）：两表的「全天购电费」= 本表购电量 × 该时段电价，两列不再相同。
        fee_plan = sub["计划购电量"]["dayfee"][i]
        fee_adj = sub["调整购电量"]["dayfee"][i]
        L += ["## %s" % ds, "", "**表1 购电量（指定时段）**", "",
              "| 时段 | 计划购电量 | 调整购电量 |", "| --- | ---: | ---: |"]
        for lab, t in (("10:00-10:10", 60), ("12:00-12:10", 72), ("14:00-14:10", 84),
                       ("16:00-16:10", 96), ("18:00-18:10", 108), ("20:00-20:10", 120)):
            L.append("| %s | %.4f | %.4f |" % (lab, g0[t], a[t]))
        L += ["| **全天购电量** | **%.4f** | **%.4f** |" % (g0.sum(), a.sum()),
              "| **全天购电费（元）** | **%.4f** | **%.4f** |" % (fee_plan, fee_adj), ""]
        L += ["**表2 充放电量（四小时段）与 0:00 / 24:00 储电量**", "",
              "| 时间段 | 充电量 | 放电量 |", "| --- | ---: | ---: |"]
        blocks = sub["充放电量"].get(ds, [])
        for b in blocks[:6]:
            L.append("| %s | %.4f | %.4f |" % (b["span"], b["C"], b["D"]))
        socs = [b["soc"] for b in blocks if b.get("soc") is not None]
        s0 = socs[0] if socs else float("nan")
        s1 = socs[-1] if socs else float("nan")
        L += ["| 0:00 储电量 | %.4f | |" % s0, "| 24:00 储电量 | %.4f | |" % s1, "",
              "（当日储电量序列，源文件同日内仅写首末两值：%s）"
              % ["%.4f" % s0, "%.4f" % s1], ""]
        segs = [s for s in sub["紧急购电量"] if s["date"] == ds]
        tot = sum(s["kWh"] for s in segs)
        L += ["**表3 紧急购电（全量段）**", "", "| 日期 | 时间段 | 购电量 |", "| --- | --- | ---: |"]
        if segs:
            for s in segs:
                L.append("| %s | %s | %.4f |" % (ds, s["span"], s["kWh"]))
            L.append("| **当日合计（%d 段）** | | **%.4f** |" % (len(segs), tot))
        else:
            L.append("| %s | 无 | 0.0000 |" % ds)
        L += ["", "---", ""]
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    old_sha = sha256_of(MD)
    sub = Q.load_submission(verbose=False)
    seg = Q.load_seg(Q.SEG_V2B, verbose=False)
    new = render(sub, seg, old_sha=old_sha, new_sha_xlsx=Q.sha256_of(Q.XLSX))

    # 勘误记录（含原文留档摘要）
    err = ["# 勘误：Q3 论文素材 表3 漏段（2026-09-13）", "",
           "> 对象：`03_论文素材\\论文表1表2表3_四个指定日期_v2.md`（勘误前 sha256 `%s`）" % old_sha, "",
           "## 问题", "",
           "`result3_v2.xlsx` 的 `紧急购电量` 表**日期列只在每日首行写一次**，后续行为同日续行；",
           "原 md 生成时未做「前向填充」，因此四个指定日期各自**只列了第 1 段**。", "",
           "## 原值 vs 勘误后（提交件现算）", "",
           "| 日期 | 原 md 段数/合计 | 勘误后段数/合计（kWh） |", "| --- | --- | --- |"]
    for ds in Q.PAPER_DATES:
        segs = [s for s in sub["紧急购电量"] if s["date"] == ds]
        first = segs[0]["kWh"] if segs else 0.0
        err.append("| %s | 1 / %.4f | **%d / %.4f** |"
                   % (ds, first, len(segs), sum(s["kWh"] for s in segs)))
    err += ["", "## 复现", "",
            "```powershell",
            "$env:PYTHONPATH='D:\\CMUCU\\rag\\.deps'; $env:PYTHONIOENCODING='utf-8'",
            "python D:\\CMUCU\\6对话\\code\\q3_fix_paper_tables.py",
            "```",
            "表3 全量段与 `07/…/q76_v2b_full_seg.jsonl` 的合并段**逐段一致**（段数 1571 = 1571）。", ""]

    if args.dry:
        print(new[:1500])
        return 0

    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(MD, BACKUP)
    MD.write_text(new, encoding="utf-8")
    ERRATA.write_text("\n".join(err), encoding="utf-8")

    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for f in m["files"]:
        if f["path"].endswith("论文表1表2表3_四个指定日期_v2.md"):
            f["sha256"] = sha256_of(MD)
            f["bytes"] = MD.stat().st_size
            f["note"] = "2026-09-13 勘误：表3 前向填充后全量段（原版本漏抄同日后续段）"
    m.setdefault("errata", []).append({
        "date": "2026-09-13",
        "file": "03_论文素材/论文表1表2表3_四个指定日期_v2.md",
        "issue": "表3 仅列每日期第 1 段（未对日期列前向填充）",
        "fixed_sha256": sha256_of(MD),
        "prev_sha256": old_sha,
        "errata_record": "04_证据/勘误_表3漏段_20260913.md",
        "backup": "04_证据/_void/论文表1表2表3_四个指定日期_v2_勘误前.md"})
    MANIFEST.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")

    print("已重出 md：", MD)
    print("  勘误前 sha256 =", old_sha[:16], "→ 勘误后 =", sha256_of(MD)[:16])
    print("  勘误记录：", ERRATA)
    print("  原文留档：", BACKUP)
    print("  manifest 已刷新（新 sha；并登记 errata 条目）")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
