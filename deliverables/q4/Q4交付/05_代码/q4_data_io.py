# -*- coding: utf-8 -*-
"""
Q4 数据入口与锚点自检（runner 产物，机械执行，不做任何建模决策）。

只读 D:\\CMUCU\\B对话\\clean 下的原始清洗数据；只写本对话目录。
运行：见 D:\\CMUCU\\_subagent_tasks\\q4_data_core.md 第 3 节命令。
"""
import json
import os
from datetime import date, timedelta

import numpy as np

DATA = r"D:\CMUCU\B对话\clean"
OUT_JSON = r"D:\CMUCU\8对话\output\q4_data_anchor.json"

T = 144
DT = 1.0 / 6.0
S0 = 6000.0
SMIN = 1200.0
SMAX = 10800.0
EBAR = 5000.0 * DT
ETA = 0.9

DAYS = list(range(31, 365))  # 2025-02-01 ~ 2025-12-31，共 334 天


def read_matrix(fname):
    """读 日期 + 144 列 的清洗矩阵，返回 (dates, (n,144) float 数组)。"""
    path = os.path.join(DATA, fname)
    with open(path, "r", encoding="utf-8-sig") as fh:
        lines = [ln.rstrip("\n").rstrip("\r") for ln in fh if ln.strip()]
    header = lines[0].split(",")
    if len(header) != T + 1:
        raise ValueError("%s: 表头列数 %d != %d" % (fname, len(header), T + 1))
    dates = []
    rows = []
    for ln in lines[1:]:
        parts = ln.split(",")
        if len(parts) != T + 1:
            raise ValueError("%s: 数据行列数 %d != %d" % (fname, len(parts), T + 1))
        dates.append(parts[0])
        rows.append([float(v) for v in parts[1:]])
    return dates, np.array(rows, dtype=float)


def read_q1_price():
    """读 q1_clean.csv 的 price_元_kWh 列（144 行）。"""
    path = os.path.join(DATA, "q1_clean.csv")
    with open(path, "r", encoding="utf-8-sig") as fh:
        lines = [ln.strip() for ln in fh if ln.strip()]
    header = lines[0].split(",")
    idx = header.index("price_元_kWh")
    vals = [float(ln.split(",")[idx]) for ln in lines[1:]]
    return np.array(vals, dtype=float)


def check(cond, name, value):
    return {"name": name, "pass": bool(cond), "value": value}


def main():
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)

    dates_load, load = read_matrix("attachment2_load.csv")
    dates_pv, pv = read_matrix("attachment2_pv.csv")
    dates_p4, p4 = read_matrix("attachment4_clean.csv")
    q1_price = read_q1_price()

    days = DAYS
    end_day = date(2025, 1, 1) + timedelta(days=days[-1])
    start_day = date(2025, 1, 1) + timedelta(days=days[0])

    assertions = []

    # 1. 形状 / 有限性
    assertions.append(check(load.shape == (365, T), "shape_load_(365,144)", list(load.shape)))
    assertions.append(check(pv.shape == (365, T), "shape_pv_(365,144)", list(pv.shape)))
    assertions.append(check(p4.shape == (365, T), "shape_p4_(365,144)", list(p4.shape)))
    assertions.append(check(bool(np.isfinite(load).all()), "load_no_nan_inf",
                            int(np.isnan(load).sum()) + int(np.isinf(load).sum())))
    assertions.append(check(bool(np.isfinite(pv).all()), "pv_no_nan_inf",
                            int(np.isnan(pv).sum()) + int(np.isinf(pv).sum())))
    assertions.append(check(bool(np.isfinite(p4).all()), "p4_no_nan_inf",
                            int(np.isnan(p4).sum()) + int(np.isinf(p4).sum())))
    assertions.append(check(len(days) == 334, "n_days_334", len(days)))

    # 2. 附件4 价格统计
    p4_min = float(p4.min())
    p4_max = float(p4.max())
    p4_mean = float(p4.mean())
    n_nonpos = int((p4 <= 0).sum())
    assertions.append(check(True, "p4_min", p4_min))
    assertions.append(check(True, "p4_max", p4_max))
    assertions.append(check(True, "p4_mean", p4_mean))
    assertions.append(check(n_nonpos == 0, "p4_count_le_0_is_zero", n_nonpos))

    # 3. 附件1 = 附件4 逐时段全年均值
    p4_colmean = p4.mean(axis=0)
    p1 = q1_price  # 附件1 的 144 个电价（即 q1_clean.csv 的 price_元_kWh，4 位小数）
    max_dev = float(np.max(np.abs(p4_colmean - p1)))
    corr = float(np.corrcoef(p4_colmean, p1)[0, 1])
    assertions.append(check(max_dev <= 1e-4, "p4_colmean_vs_q1_price_max_abs_diff", max_dev))
    assertions.append(check(True, "p4_colmean_vs_q1_price_corr", corr))

    # 4. 日期索引自检
    idx0_ok = start_day == date(2025, 2, 1)
    idxn_ok = end_day == date(2025, 12, 31)
    assertions.append(check(idx0_ok, "days[0]_is_2025-02-01", str(start_day)))
    assertions.append(check(idxn_ok, "days[-1]_is_2025-12-31", str(end_day)))

    # 5. 附件1 电价 144 值 vs q1_clean.csv price 逐元素相等
    q1_max_diff = float(np.max(np.abs(p1 - q1_price)))
    assertions.append(check(q1_max_diff == 0.0, "p1_vs_q1_clean_price_max_diff", q1_max_diff))

    all_pass = all(a["pass"] for a in assertions)

    payload = {
        "task": "q4_data_core",
        "generated_by": "D:\\CMUCU\\8对话\\code\\q4_data_io.py",
        "data_dir": DATA,
        "files": {
            "attachment2_load.csv": "365x144 kW (实际负荷)",
            "attachment2_pv.csv": "365x144 kW (实际光伏)",
            "attachment4_clean.csv": "365x144 元/kWh (Q4 专用价格)",
            "q1_clean.csv": "144 行 (附件1 典型日: 电价/负荷/光伏)",
        },
        "constants": {
            "T": T, "DT": DT, "S0": S0, "SMIN": SMIN, "SMAX": SMAX,
            "EBAR": EBAR, "ETA": ETA,
        },
        "eval_window": {
            "days": [days[0], days[-1]],
            "n_days": len(days),
            "first_date": str(start_day),
            "last_date": str(end_day),
        },
        "p4_stats": {"min": p4_min, "max": p4_max, "mean": p4_mean, "count_le_0": n_nonpos},
        "p1_vs_p4_colmean": {"max_abs_diff": max_dev, "corr": corr},
        "p1_vs_q1_clean_price": {"max_abs_diff": q1_max_diff},
        "assertions": assertions,
        "all_pass": all_pass,
    }

    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    for a in assertions:
        print("%-46s %s  value=%s" % (a["name"], "PASS" if a["pass"] else "FAIL", a["value"]))
    print("ALL_PASS=%s" % all_pass)
    print("wrote %s" % OUT_JSON)


if __name__ == "__main__":
    main()
