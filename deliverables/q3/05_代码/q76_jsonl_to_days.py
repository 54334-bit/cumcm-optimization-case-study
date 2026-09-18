# -*- coding: utf-8 -*-
"""把主线 ``--segments-out`` 落的 JSONL 转成 ``q3_materialize`` 认得的解法 JSON。

背景
----
``q3_main_v2.py year --segments-out`` 写的是 **JSONL（每天一行）**，而冻结物化
脚手架 ``q3_materialize.load_solution`` 要求 **单文件、顶层含 ``days`` 数组**
(``json.loads(path.read_text())``)。直接把 JSONL 喂进去会报
``json.JSONDecodeError: Extra data``。本脚本就是这一步机械转换。

输入（每行一天，字段实测）
--------------------------
``d / date / billing / info / demand / q / q_block / A / G0 / C / C_plan /
D / D_plan / S(145) / H / R_PV / R_G``，其中 ``A/G0/C/D/H`` 均为 144 段。

输出 schema（``q3_solution_v1`` 子集，只落物化需要的字段）
---------------------------------------------------------
```json
{"meta": {"date_first": "...", "date_last": "...", "dt_hours": 0.1666666667,
          "eta": 0.9, "s_lo": 1200, "s_hi": 10800, "s_init": 6000.0,
          "col_map": {"mode": "position", "col_of_t": "2+t"}},
 "price": [144 个元/kWh],
 "days": [{"date": "2025-02-01", "G0": [...], "A": [...],
           "C": [...], "D": [...], "H": [...]}]}
```

用法
----
    python q76_jsonl_to_days.py --seg <seg.jsonl> --out <solution.json> \
        --price <q1_clean.csv>

退出码：0 成功；2 输入问题。
"""
from __future__ import annotations

import argparse
import csv
import datetime as _dt
import io
import json
import sys
from pathlib import Path

T = 144                      # 每天的 10 分钟区间数
DT = 1.0 / 6.0               # h

DEFAULT_PRICE_CSV = r"D:\CMUCU\B对话\clean\q1_clean.csv"
# 逐段解法里的字段名（照抄实测 JSONL，不得自创别名）
FIELDS = ("G0", "A", "C", "D", "H")


def load_price_csv(path) -> list:
    """从附件1 清洗件读 144 段电价（元/kWh），列名按候选顺序匹配。"""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"附件1 清洗件不存在：{p}")
    with io.open(p, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError(f"附件1 清洗件为空：{p}")
    col = None
    for cand in ("price_元_kWh", "price", "价格", "电价"):
        if cand in rows[0]:
            col = cand
            break
    if col is None:
        col = list(rows[0].keys())[4]        # 兜底：第 5 列（实测即电价列）
    price = [float(r[col]) for r in rows]
    if len(price) != T:
        raise ValueError(f"电价长度 {len(price)} != {T}（{p}）")
    return price


def _vec(day: dict, key: str, path) -> list:
    """取 144 段向量并做长度/类型自检。"""
    if key not in day or day[key] is None:
        raise ValueError(f"{path}：{day.get('date', '?')} 缺少字段 `{key}`")
    v = [float(x) for x in day[key]]
    if len(v) != T:
        raise ValueError(f"{path}：{day.get('date', '?')} 字段 `{key}` 长度 {len(v)} != {T}")
    return v


def convert(seg_path, out_path, price_csv=DEFAULT_PRICE_CSV, eta=0.9,
            s_init=6000.0, s_lo=1200.0, s_hi=10800.0) -> dict:
    """JSONL（每天一行）→ 顶层含 ``days`` 的解法 JSON，落盘并返回统计。"""
    seg = Path(seg_path)
    if not seg.exists():
        raise FileNotFoundError(f"逐段 JSONL 不存在：{seg}")

    days = []
    with io.open(seg, "r", encoding="utf-8-sig") as f:
        for ln, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            date = str(raw.get("date") or raw.get("日期") or "").strip()
            if not date:
                raise ValueError(f"{seg}:{ln} 缺少 date 字段")
            rec = {"date": date}
            for k in FIELDS:
                rec[k] = _vec(raw, k, f"{seg}:{ln}")
            days.append(rec)

    if not days:
        raise ValueError(f"逐段 JSONL 为空：{seg}")

    # 按日期排序 + 唯一性/连续性自检（物化要求 2025-02-01 ~ 2025-12-31 逐日）
    days.sort(key=lambda d: d["date"])
    dates = [d["date"] for d in days]
    if len(set(dates)) != len(dates):
        raise ValueError("逐段 JSONL 存在重复日期")
    d0 = _dt.date.fromisoformat(dates[0])
    d1 = _dt.date.fromisoformat(dates[-1])
    if (d1 - d0).days + 1 != len(days):
        raise ValueError(f"日期不连续：{dates[0]} ~ {dates[-1]} 共 {len(days)} 天")

    price = load_price_csv(price_csv)
    sol = {
        "meta": {
            "date_first": dates[0],
            "date_last": dates[-1],
            "dt_hours": DT,
            "eta": float(eta),
            "s_lo": float(s_lo),
            "s_hi": float(s_hi),
            "s_init": float(s_init),
            "n_days": len(days),
            "col_map": {"mode": "position", "col_of_t": "2+t"},
            "source_seg": str(seg),
            "price_csv": str(price_csv),
        },
        "price": price,
        "days": days,
    }

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(sol, ensure_ascii=False), encoding="utf-8")

    return {
        "source_seg": str(seg),
        "out": str(out),
        "n_days": len(days),
        "date_first": dates[0],
        "date_last": dates[-1],
        "price_csv": str(price_csv),
        "sum_G0": sum(sum(d["G0"]) for d in days),
        "sum_A": sum(sum(d["A"]) for d in days),
        "sum_C": sum(sum(d["C"]) for d in days),
        "sum_D": sum(sum(d["D"]) for d in days),
        "sum_H": sum(sum(d["H"]) for d in days),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="JSONL（每天一行）→ 顶层含 days 数组的解法 JSON")
    ap.add_argument("--seg", required=True, help="主线 --segments-out 落的 JSONL")
    ap.add_argument("--out", required=True, help="输出的解法 JSON（顶层含 days）")
    ap.add_argument("--price", default=DEFAULT_PRICE_CSV, help="附件1 清洗件（144 段电价）")
    ap.add_argument("--eta", type=float, default=0.9, help="储能充放电效率（默认 0.9，照抄主线）")
    ap.add_argument("--s-init", type=float, default=6000.0, help="初始储电量 kWh（默认 6000）")
    ap.add_argument("--s-lo", type=float, default=1200.0, help="储电量下限 kWh（默认 1200）")
    ap.add_argument("--s-hi", type=float, default=10800.0, help="储电量上限 kWh（默认 10800）")
    ap.add_argument("--report", default=None, help="可选：统计写入该 JSON")
    args = ap.parse_args(argv)

    try:
        rep = convert(args.seg, args.out, price_csv=args.price, eta=args.eta,
                      s_init=args.s_init, s_lo=args.s_lo, s_hi=args.s_hi)
    except FileNotFoundError as e:
        print(f"[ERROR] 输入缺失：{e}", file=sys.stderr)
        return 2
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
        print(f"[ERROR] 数据不合法：{e}", file=sys.stderr)
        return 2

    print("[OK] JSONL → 解法 JSON 完成")
    print(f"  输入  ：{rep['source_seg']}")
    print(f"  输出  ：{rep['out']}")
    print(f"  区间  ：{rep['date_first']} ~ {rep['date_last']}（{rep['n_days']} 天）")
    print(f"  合计  ：G0={rep['sum_G0']:.3f}  A={rep['sum_A']:.3f}  "
          f"C={rep['sum_C']:.3f}  D={rep['sum_D']:.3f}  H={rep['sum_H']:.3f}")
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(json.dumps(rep, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
        print(f"  统计  ：{args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
