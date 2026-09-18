"""Q1 公共常量与数据加载模块。

本模块只提供常量、数据读取与区间映射，不参与建模与求解。
所有数值口径以 ``A对话/Q1建模/Q1_1.0.md`` 为准。
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
from typing import Dict, List, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# 常量（写死，不得改动）
# ---------------------------------------------------------------------------
T = 144                 # 时段数
DT = 1.0 / 6.0          # 单时段时长（小时）
PMAX = 5000.0           # 储能端口最大功率（kW）
EBAR = PMAX * DT        # 单时段最大充/放电量（kWh），保留未舍入值
S_MIN = 1200.0          # SOC 下限（kWh）
S_MAX = 10800.0         # SOC 上限（kWh）
S0 = 6000.0             # 日初 SOC（kWh）
S_T = 6000.0            # 日末 SOC（kWh）
ETA_C = 0.9             # 充电效率
ETA_D = 0.9             # 放电效率

# 晚峰区间（口径 R，0-based 时段索引）[18:00, 21:00)
LATE_START = 108
LATE_END = 126          # 不含
N_LATE = LATE_END - LATE_START

# 表1 六个指定时段对应的 0-based row_id
TABLE1_ROWS = (60, 72, 84, 96, 108, 120)

# 六个四小时块（block 索引 -> row_id 区间）
BLOCK_BOUNDS = (
    (0, 24),      # 0:00-4:00
    (24, 48),     # 4:00-8:00
    (48, 72),     # 8:00-12:00
    (72, 96),     # 12:00-16:00
    (96, 120),    # 16:00-20:00
    (120, 144),   # 20:00-24:00
)


# 数据文件路径（绝对路径，避免与工作目录耦合）
CSV_PATH = r"D:\CMUCU\B对话\clean\q1_clean.csv"
IMAGE_PATH = r"D:\CMUCU\B对话\clean\q1_image.json"


def _sha256(path: str) -> str:
    """返回文件的 SHA-256 十六进制字符串。"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_data() -> Dict:
    """读取清洗后 CSV，返回带 numpy 数组与审计信息的字典。

    Returns
    -------
    Dict
        - ``row_id``: int array (144,)
        - ``raw_time``: str array (144,)
        - ``interval_start`` / ``interval_end``: str array (144,)
        - ``price``: float array (144,)  元/kWh
        - ``load_kw`` / ``pv_kw``: float array (144,)
        - ``load_e`` / ``pv_e``: float array (144,) kWh（已乘 dt）
        - ``csv_sha256`` / ``image_sha256``: str
    """
    if not os.path.exists(CSV_PATH):
        raise FileNotFoundError(f"输入数据不存在: {CSV_PATH}")

    rows: List[Dict[str, str]] = []
    with open(CSV_PATH, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    if len(rows) != T:
        raise ValueError(f"CSV 行数 {len(rows)} != {T}")

    row_id = np.array([int(r["row_id"]) for r in rows], dtype=int)
    raw_time = np.array([r["raw_time"] for r in rows], dtype=object)
    interval_start = np.array([r["interval_start"] for r in rows], dtype=object)
    interval_end = np.array([r["interval_end"] for r in rows], dtype=object)
    price = np.array([float(r["price_元_kWh"]) for r in rows], dtype=float)
    load_kw = np.array([float(r["load_kW"]) for r in rows], dtype=float)
    pv_kw = np.array([float(r["pv_kW"]) for r in rows], dtype=float)

    # 检查 row_id 为严格 0..143
    if not np.array_equal(row_id, np.arange(T)):
        raise ValueError("row_id 不是严格的 0..143 顺序")

    load_e = load_kw * DT
    pv_e = pv_kw * DT

    return {
        "row_id": row_id,
        "raw_time": raw_time,
        "interval_start": interval_start,
        "interval_end": interval_end,
        "price": price,
        "load_kw": load_kw,
        "pv_kw": pv_kw,
        "load_e": load_e,
        "pv_e": pv_e,
        "csv_sha256": _sha256(CSV_PATH),
        "image_sha256": _sha256(IMAGE_PATH) if os.path.exists(IMAGE_PATH) else "",
    }


def load_image_anchors() -> Dict:
    """读取画像锚点 JSON。"""
    with open(IMAGE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def compute_profile(price: np.ndarray, load_kw: np.ndarray, pv_kw: np.ndarray) -> Dict:
    """按口径 R 独立复算数据画像。

    返回与 ``q1_image.json`` 同口径的画像字典，供审计比对与预注册使用。
    """
    pv_surplus_kw = np.maximum(pv_kw - load_kw, 0.0)
    net_late = (load_kw[LATE_START:LATE_END] - pv_kw[LATE_START:LATE_END])

    i_min = int(np.argmin(price))
    i_max = int(np.argmax(price))

    return {
        "min_price": {"value": float(np.min(price)), "label": str(raw_time_label(i_min))},
        "max_price": {"value": float(np.max(price)), "label": str(raw_time_label(i_max))},
        "peak_valley_ratio": float(np.max(price) / np.min(price)),
        "non_positive_price_count": int(np.sum(price <= 0.0)),
        "pv_surplus_kWh": float(np.sum(pv_surplus_kw) * DT),
        "peak_pv_surplus_kW": float(np.max(pv_surplus_kw)),
        "late_net_load_18_21_kWh": float(np.sum(net_late) * DT),
        "late_interval_count": int(N_LATE),
        "n_intervals": int(T),
        "dt_h": float(DT),
        "Ebar_kWh": float(EBAR),
    }


def raw_time_label(idx: int) -> str:
    """由 0-based 时段索引还原原始时间标签。"""
    minutes = (idx + 1) * 10
    if minutes >= 1440:
        return "0:00+1"
    h = minutes // 60
    m = minutes % 60
    return f"{h:02d}:{m:02d}"


def tolerances(load_e: np.ndarray, pv_e: np.ndarray, j1_star: float) -> Dict[str, float]:
    """按 §9 容差链计算各容差。"""
    e_scale_pre = max(1.0, S_MAX, EBAR, float(np.max(load_e)), float(np.max(pv_e)))
    eps_energy = max(1e-6, 1e-9 * e_scale_pre)
    eps_soc = max(1e-6, 1e-9 * S_MAX)
    eps_cost = max(1e-6, 1e-9 * max(1.0, abs(j1_star)))
    eps_j = max(1e-6, 1e-9 * max(1.0, abs(j1_star)))
    eps_mutex = eps_energy
    return {
        "E_scale_pre": e_scale_pre,
        "eps_energy": eps_energy,
        "eps_soc": eps_soc,
        "eps_cost": eps_cost,
        "eps_J": eps_j,
        "eps_mutex": eps_mutex,
    }
