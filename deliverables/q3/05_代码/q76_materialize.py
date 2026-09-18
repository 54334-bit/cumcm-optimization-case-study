# -*- coding: utf-8 -*-
"""B2 物化驱动：逐段 JSONL → 解法 JSON → ``result3.xlsx``（模板另存副本）。

本脚本只做「物化 + 前后哈希取证」，**不做求解、不做口径裁定**，也不修改模板。

冻结口径（照抄 7.5 ``q3_materialize.py``，不得自创）
---------------------------------------------------
- 列映射 = 位置映射 ``col = 2 + t``（模板表头整体错位一格，禁止按标签对齐）；
  第 145 列 = 第 144 段，第 146 列 = 全天购电量，第 147 列 = 全天购电费。
- 报账读法 ``C``：``p·min(G⁰,A) + 0.5p(G⁰−A)⁺ + 1.5p(A−G⁰)⁺ + 5p·H``。
- 表 1 = ``G0``、表 2 = ``A``、表 3 = 四小时块充放电量、表 4 = 紧急购电真实发生段
  （同日相邻合并、跨日不合并、日期只在当日首段写一次）。

实现方式
--------
物化引擎直接 **以库方式只读引用** 7.5 的 ``q3_materialize.py``（唯一口径来源），
调用前先复算其 SHA-256 与冻结值比对，不一致即中止（防止 7.5 被改动后口径漂移）。
本仓库的格式转换（JSONL → 顶层含 ``days`` 数组）由同目录 ``q76_jsonl_to_days.py`` 完成。

用法
----
    python q76_materialize.py --seg <seg.jsonl> --solution <solution.json> \\
        --out <result3.xlsx> --template <附件5/result3.xlsx> \\
        --price <q1_clean.csv> --reading C --report <报告.json>

退出码：0 成功；2 输入问题；3 写前自检不通过 / 引擎哈希不符。
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import sys
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parent
Q75_CODE = Path(r"D:\CMUCU\7.5对话\code")
# 冻结哈希（2026-09-12 复算，与 _sub/q76_pioneer_B.md 记录一致）
FROZEN_ENGINE_SHA256 = "4B7CAA678F15444579206DEA85BD72357A6258D3390B9083954F4E86891501FF"

DEFAULT_TEMPLATE = r"D:\CMUCU\赛题\C题\附件\附件5\result3.xlsx"
DEFAULT_PRICE_CSV = r"D:\CMUCU\B对话\clean\q1_clean.csv"


def sha256_of(path) -> str:
    """文件 SHA-256（大写十六进制）。"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def load_engine():
    """只读引入 7.5 冻结物化引擎，并复算哈希。返回 ``(engine_module, sha256)``。"""
    target = Q75_CODE / "q3_materialize.py"
    if not target.exists():
        raise FileNotFoundError(f"冻结物化引擎不存在：{target}")
    sys.path.insert(0, str(Q75_CODE))
    import q3_materialize as engine  # noqa: E402  （只读引用，不改 7.5）
    # ★ 2026-09-12 整改：7.5 的 engine 把时段块写成 BLOCK=36（6 小时），
    #   而模板表 2 的「指定时间段」是 4 小时块（0:00-4:00 / 4:00-8:00 / …）。
    #   结果会导致第 5、6 行（16:00-20:00、20:00-24:00）恒为 0、并整体错位。
    #   在本侧覆盖为 24（不改 7.5 任何文件），并断言 24*6==144。
    if hasattr(engine, "BLOCK"):
        engine.BLOCK = 24
        assert 24 * 6 == 144, "block override sanity"
        print("[q76] override engine.BLOCK = 24 (4h blocks, 6 per day)")

    got = sha256_of(engine.__file__)
    if got != FROZEN_ENGINE_SHA256:
        raise ValueError(
            "物化引擎 SHA-256 与冻结值不一致，拒绝据此物化：\n"
            f"  实际 {got}\n  冻结 {FROZEN_ENGINE_SHA256}")
    return engine, got


def run(seg, solution, out, template=DEFAULT_TEMPLATE, price_csv=DEFAULT_PRICE_CSV,
        reading="C", force=False) -> dict:
    """转换（可选）→ 物化 → 哈希取证。返回物化报告 dict。"""
    tpl = Path(template)
    if not tpl.exists():
        raise FileNotFoundError(f"模板不存在：{tpl}")
    if Path(out).resolve() == tpl.resolve():
        raise ValueError("拒绝覆盖模板：--out 不能等于模板路径")

    engine, engine_sha = load_engine()
    tpl_sha_before = sha256_of(tpl)
    tpl_bytes_before = tpl.stat().st_size

    conv = None
    if seg is not None:
        sys.path.insert(0, str(CODE_DIR))
        import q76_jsonl_to_days as CV  # noqa: E402

        conv = CV.convert(seg, solution, price_csv=price_csv)

    rep = engine.materialize(str(solution), str(out), template=str(tpl),
                             price_csv=str(price_csv), reading=reading, force=force)

    tpl_sha_after = sha256_of(tpl)
    tpl_bytes_after = tpl.stat().st_size
    out_p = Path(out)
    return {
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "pipeline": {
            "seg_jsonl": str(seg) if seg else None,
            "solution_json": str(solution),
            "out_xlsx": str(out),
            "template": str(tpl),
            "price_csv": str(price_csv),
            "reading": str(reading).upper(),
        },
        "conversion": conv,
        "materialize": rep,
        "engine": {"path": str(engine.__file__), "sha256": engine_sha,
                   "frozen_sha256": FROZEN_ENGINE_SHA256,
                   "sha_match": engine_sha == FROZEN_ENGINE_SHA256},
        "template_integrity": {
            "sha256_before": tpl_sha_before,
            "sha256_after": tpl_sha_after,
            "bytes_before": tpl_bytes_before,
            "bytes_after": tpl_bytes_after,
            "unchanged": (tpl_sha_before == tpl_sha_after
                          and tpl_bytes_before == tpl_bytes_after),
        },
        "out_xlsx": {
            "path": str(out_p),
            "exists": out_p.exists(),
            "bytes": out_p.stat().st_size if out_p.exists() else None,
            "sha256": sha256_of(out_p) if out_p.exists() else None,
        },
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="B2 物化：逐段 JSONL → 解法 JSON → result3.xlsx（另存副本）")
    ap.add_argument("--seg", default=None, help="主线 --segments-out 落的 JSONL（给了就先转换）")
    ap.add_argument("--solution", required=True, help="解法 JSON（顶层含 days；--seg 给定时为转换输出）")
    ap.add_argument("--out", required=True, help="输出的 xlsx（不得等于模板）")
    ap.add_argument("--template", default=DEFAULT_TEMPLATE, help="附件5 模板（只读）")
    ap.add_argument("--price", default=DEFAULT_PRICE_CSV, help="附件1 清洗件（144 段电价）")
    ap.add_argument("--reading", default="C", choices=["A", "C", "a", "c"], help="报账读法（默认 C）")
    ap.add_argument("--report", default=None, help="物化报告 JSON")
    ap.add_argument("--force", action="store_true", help="允许覆盖已存在的输出")
    args = ap.parse_args(argv)

    try:
        rep = run(args.seg, args.solution, args.out, template=args.template,
                  price_csv=args.price, reading=args.reading, force=args.force)
    except FileNotFoundError as e:
        print(f"[ERROR] 输入缺失：{e}", file=sys.stderr)
        return 2
    except FileExistsError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 2
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
        print(f"[ERROR] 数据/口径不合法：{e}", file=sys.stderr)
        return 3

    m = rep["materialize"]
    print("[OK] B2 物化完成")
    print(f"  输出      ：{m['out']}")
    print(f"  区间      ：{m['date_first']} ~ {m['date_last']}（{m['n_days']} 天）")
    print(f"  列映射    ：{m['col_map']['col_of_t']}（首段列 {m['col_map']['first_t_col']}）")
    print(f"  充放电行数：{m['sheets']['soc']['rows']}")
    print(f"  紧急购电行：{m['sheets']['emergency']['rows']}"
          f"（合并前 {m['sheets']['emergency']['segments_merged']} 段）")
    print(f"  模板未改  ：{rep['template_integrity']['unchanged']} "
          f"({rep['template_integrity']['sha256_after'][:16]}…)")
    print(f"  引擎哈希  ：{rep['engine']['sha_match']} ({rep['engine']['sha256'][:16]}…)")
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(json.dumps(rep, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
        print(f"  物化报告  ：{args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
