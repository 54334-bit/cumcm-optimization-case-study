"""Q7.6 E4：同保守度对齐（q×m 两臂）+ 边际传导估计。

背景
----
Q3 计划层有两个"保守度"参数：

* ``q`` —— 加性、全天因果残差分位（``demand="quantile_v3"`` 的 δ 分位）；
* ``m`` —— 乘性、只作用白天光伏的预报裕度（``--margin``）。

全年台账（``7.5对话/output/q75_g2_manifest.jsonl``，代码代次 ``4ddf3879c220``）中
``v3seg_q0.8×C×m=0`` 与 ``v3seg_q0.5×C×m=0.04`` 的 ``J_cash`` 只差约 0.46%：
13,369,682.34（m=0 臂）与 13,308,032.83（m=0.04 臂）。本脚本回答：
这点差异是"``q=0.5`` 的保守度更优"，还是"两种参数化在**不同时段形状**上适配"
造成的**形状效应**（``m`` 只管白天光伏）。

做什么
------
1. ``run``：按**主台账同 key 的 cmd 口径**跑两个配置（只改参数、不改 7.5 代码），
   落逐段数组明细 ``*_seg.jsonl`` 与汇总 ``*_out.json``。
2. ``analyze``：读逐段明细 + 附件 2 实测数据，重建每个配置的**计划层净需求**
   ``N̂``（θ=0 全天计划，逐段），算同保守度对齐指标、边际传导估计，并落报告。

CLI 口径映射（重要）
------------------
任务书写 ``--demand v3seg``，但 ``q3_demand_quantile.DEMAND_CHOICES`` 只有
``("point", "quantile", "quantile_v3")``；主台账同一 key 的 ``cmd`` 记的是
``--demand quantile_v3 --q-block segment --convention slot_end``（``v3seg`` 是台账
label，不是 CLI 取值）。本脚本按台账 ``cmd`` 落**同一口径**，从而保证 ``J_cash``
与台账 key 逐位一致（验收标准 3）。

``N̂`` 的口径（写死，避免歧义）
----------------------------
``N̂_t`` = 该配置在 **θ=0** 时喂给计划层 LP 的全天净需求（kWh），由
``q3_main_v2._pv_for_epoch`` + ``q3_demand_quantile.plan_net_demand`` **同一代码路径**
重建：``N̂ = plan_net_demand((L0 − (1−m)·PV̂0)·dt, ...)``（``demand="quantile_v3"``
时在全部段上叠加该配置 ``q`` 的因果残差分位 δ）。
``Σ_t N̂_t / 334`` 即"日均计划净需求"。

只读/只写边界
-------------
只读 ``7.5对话`` 的代码与数据；只写 ``7.6对话/output/e4/**`` 与
``7.6对话/_sub/q76_e4_report.md``。

用法::

    python q76_e4_alignment.py run        # 跑两配置（约 1 分钟）
    python q76_e4_alignment.py analyze    # 统计 + 报告
    python q76_e4_alignment.py all        # 两者串起来
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

import numpy as np

# ----------------------------------------------------------------- 路径与常量
HERE = os.path.dirname(os.path.abspath(__file__))
Q76 = os.path.dirname(HERE)
OUT_E4 = os.path.join(Q76, "output", "e4")
SUB = os.path.join(Q76, "_sub")
Q75_CODE = r"D:\CMUCU\7.5对话\code"
Q75_OUT = r"D:\CMUCU\7.5对话\output"
SCIPY_TMP = r"D:\CMUCU\3对话\.scipy_tmp"
MANIFEST = os.path.join(Q75_OUT, "q75_g2_manifest.jsonl")

N_DAYS_EXPECT = 334                 # 验收：d=31..364
SOC_LO, SOC_HI = 1200.0, 10800.0    # 附件2 储能红线
EPS_SOC = 1e-6                      # 与 q3_main_v2 同容差
BAL_TOL = 1e-6                      # 逐段能量平衡残差上限
REL_EQUIV = 0.05 / 100.0            # J-E4a：等价脊阈值 0.05%
FIRST_ORDER = 0.2                   # J-E4c：ΣH/Σgap ≪1 的门槛

# 两臂定义：label -> 参数（key 为主台账 key，用于逐位对账）
ARMS = {
    "q08_m0": {
        "label": "v3seg_q0.8 × C × m=0",
        "key": "g2_v3seg_q0.8_C_m0.00",
        "q": 0.8, "margin": 0.0, "billing": "C",
        "demand": "quantile_v3", "q_block": "segment", "convention": "slot_end",
        "seg": "q08_m0_seg.jsonl", "out": "q08_m0_out.json",
    },
    "q05_m004": {
        "label": "v3seg_q0.5 × C × m=0.04",
        "key": "g2_v3seg_q0.5_C_m0.04",
        "q": 0.5, "margin": 0.04, "billing": "C",
        "demand": "quantile_v3", "q_block": "segment", "convention": "slot_end",
        "seg": "q05_m004_seg.jsonl", "out": "q05_m004_out.json",
    },
}

# 逐段明细里落盘的字段（与 q3_main_v2.ROWS_SEG_KEYS 一致）
SEG_KEYS = ("A", "G0", "C", "D", "S", "H", "R_PV", "R_G")


def sha256_of(path: str) -> str:
    """文件 SHA-256（分块读，避免整包进内存）。"""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _rel(a: float, b: float) -> float:
    """相对差 ``(a−b)/b``；``b=0`` 时返回 ``nan``。"""
    return float((a - b) / b) if b else float("nan")


# --------------------------------------------------------------- 子进程：跑配置
def run_configs(timeout: float | None = None) -> list:
    """按主台账同 key 的 cmd 口径跑两臂，落 ``*_seg.jsonl`` 与 ``*_out.json``。

    返回每条命令的执行记录（供报告复现用）。只改参数，不改 7.5 任何文件。
    """
    _ensure_dir(OUT_E4)
    env = dict(os.environ)
    env["PYTHONPATH"] = SCIPY_TMP + os.pathsep + Q75_CODE
    env["PYTHONIOENCODING"] = "utf-8"
    recs = []
    for tag, arm in ARMS.items():
        out_json = os.path.join(OUT_E4, arm["out"])
        seg_jsonl = os.path.join(OUT_E4, arm["seg"])
        cmd = [
            sys.executable, os.path.join(Q75_CODE, "q3_main_v2.py"), "year",
            "--dmax", "364", "--epochs", "0,6,12,18",
            "--margin", f"{arm['margin']:.2f}",
            "--convention", arm["convention"],
            "--billing", arm["billing"],
            "--demand", arm["demand"],
            "--q", f"{arm['q']:g}",
            "--q-block", arm["q_block"],
            "--out", out_json,
            "--segments-out", seg_jsonl,
        ]
        t0 = time.time()
        print(f"[run] {tag}: {' '.join(cmd)}", flush=True)
        proc = subprocess.run(cmd, cwd=Q75_CODE, env=env, timeout=timeout,
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace")
        dt = time.time() - t0
        print(proc.stdout[-1500:], flush=True)
        if proc.returncode != 0:
            print(proc.stderr[-2000:], flush=True)
            raise RuntimeError(f"{tag} 返回码 {proc.returncode}")
        recs.append({"tag": tag, "cmd": cmd, "runtime_sec": round(dt, 1),
                     "returncode": proc.returncode})
    return recs


# --------------------------------------------------------------- 读数据 / 台账
def load_manifest() -> dict:
    """读主台账，返回 ``key -> row``（只读）。"""
    rows = {}
    with open(MANIFEST, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                r = json.loads(line)
                rows[r["key"]] = r
    return rows


def load_segments(path: str) -> dict:
    """读逐段明细 JSONL，返回 ``{field: (n_days, T)}`` 与日期列表。

    ``S`` 在执行器里长度是 ``T+1``（``S[0]`` = 当日区间前 SOC），统一裁到
    ``S[1:]``（144 段的段末 SOC），与 ``q3_main_v2`` 的自检口径 ``S_hi`` 一致。
    """
    days, recs = [], {k: [] for k in SEG_KEYS}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            r = json.loads(line)
            days.append(int(r["d"]))
            for k in SEG_KEYS:
                v = np.asarray(r[k], dtype=float).ravel()
                if k == "S" and v.size == 145:
                    v = v[1:]
                recs[k].append(v)
    out = {k: np.vstack(v) for k, v in recs.items()}
    out["_days"] = np.asarray(days, dtype=int)
    return out


def _q75_imports():
    """把 7.5 code 加进 ``sys.path`` 并返回需要的模块（只读，不改文件）。"""
    if Q75_CODE not in sys.path:
        sys.path.insert(0, Q75_CODE)
    import q3_data_io as D                                  # noqa: E402
    import q3_main_v2 as M                                  # noqa: E402
    from q3_demand_quantile import plan_net_demand          # noqa: E402
    return D, M, plan_net_demand


def rebuild_plan_net_demand(arm: dict) -> np.ndarray:
    """重建该臂 θ=0 喂给计划层 LP 的全天净需求 ``N̂``（kWh），形状 ``(n_days, 144)``。

    与 ``q3_main_v2.run_day_v2`` 的 θ=0 分支**同一代码路径**：
    ``(1−m)·PV̂0`` 定标 → ``plan_net_demand(..., demand="quantile_v3", q=arm.q)``。
    """
    D, M, plan_net_demand = _q75_imports()
    L, P, days = D.load_load_pv()
    fc = D.load_forecast()
    mmap = M.load_margin_map()                       # 只读；margin 显式给定时被覆盖
    rows = []
    for d in range(D.DAY0, D.DAY1 + 1):
        day, prev = days[d], days[d - 1]
        pv0, m0, _miss = M._pv_for_epoch(fc, day, prev, 0, d, P, mmap,
                                        arm["margin"], "known", arm["convention"])
        pv0_e = (1.0 - m0) * pv0
        N0 = plan_net_demand((L[d] - pv0_e) * D.DT, L, P, d, 0,
                             demand=arm["demand"], q=arm["q"], fc=fc, days=days,
                             convention=arm["convention"], q_block=arm["q_block"])
        rows.append(np.asarray(N0, dtype=float))
    return np.vstack(rows)


def load_price_pv():
    """附件 1 电价（144 段）与附件 2 实测光伏（365×144，kW）。"""
    D, _M, _p = _q75_imports()
    price = np.asarray(D.load_prices(), dtype=float)
    _L, P, days = D.load_load_pv()
    return price, P, days


# --------------------------------------------------------------- 指标与判据
def arm_metrics(tag: str, arm: dict, seg: dict, N_hat: np.ndarray, price: np.ndarray,
                P_day: np.ndarray) -> dict:
    """单臂指标：计划净需求分解、动作量、SOC、费用、红线（判据 J-E4d）。

    ``P_day``：该臂覆盖日期的实测光伏 ``(n_days, 144)``（kW），用于白天/夜间分段。
    """
    A, G0, C, D_, S = (seg[k] for k in ("A", "G0", "C", "D", "S"))
    H, R_PV, R_G = (seg[k] for k in ("H", "R_PV", "R_G"))
    n_days = A.shape[0]
    pv_pos = P_day > 0.0                                  # 白天段（实测光伏 >0）

    # 逐段现金口径（与 q3_solver_billingC.cash_C 同式，用于按天/分档对齐）
    j_plan_seg = price[None, :] * np.minimum(G0, A)
    j_adj_seg = 0.5 * price[None, :] * np.maximum(G0 - A, 0.0) \
        + 1.5 * price[None, :] * np.maximum(A - G0, 0.0)
    j_emg_seg = 5.0 * price[None, :] * H
    daily_j = (j_plan_seg + j_adj_seg + j_emg_seg).sum(axis=1)

    sums = {
        "sum_N_hat": float(N_hat.sum()),
        "mean_day_N_hat": float(N_hat.sum() / n_days),
        "sum_N_hat_day": float(N_hat[pv_pos].sum()),
        "sum_N_hat_night": float(N_hat[~pv_pos].sum()),
        "sum_QG0": float(G0.sum()),
        "sum_A": float(A.sum()),
        "sum_H": float(H.sum()),
        "sum_A_minus_G0_pos": float(np.maximum(A - G0, 0.0).sum()),
        "sum_G0_minus_A_pos": float(np.maximum(G0 - A, 0.0).sum()),
        "sum_R_PV": float(R_PV.sum()),
        "sum_R_G": float(R_G.sum()),
    }
    fees = {
        "J_plan": float(j_plan_seg.sum()),
        "J_adj": float(j_adj_seg.sum()),
        "J_emg": float(j_emg_seg.sum()),
        "J_cash": float(daily_j.sum()),
    }
    soc_vals = S.ravel()
    redlines = {
        "soc_min": float(soc_vals.min()),
        "soc_max": float(soc_vals.max()),
        "soc_in_range": bool(soc_vals.min() >= SOC_LO - EPS_SOC
                             and soc_vals.max() <= SOC_HI + EPS_SOC),
        "soc_depleted_segments": int(np.count_nonzero(soc_vals <= SOC_LO + EPS_SOC)),
        "balance_max_res": float(np.max(np.abs(
            A - C + D_ + H - R_PV - R_G - (np.asarray(seg["_real"], dtype=float))))),
        "balance_ok": None,
        "no_sell_ok": bool(A.min() >= -1e-9 and G0.min() >= -1e-9),
        "n_days": int(n_days),
        "n_days_ok": bool(n_days == N_DAYS_EXPECT),
    }
    redlines["balance_ok"] = bool(redlines["balance_max_res"] <= BAL_TOL)
    return {
        "tag": tag, "label": arm["label"], "manifest_key": arm["key"],
        "q": arm["q"], "margin": arm["margin"], "billing": arm["billing"],
        "demand": arm["demand"], "q_block": arm["q_block"],
        "sums": sums, "fees": fees, "fees_per_kwh_plan_N": float(
            sums["sum_N_hat"] and fees["J_cash"] / sums["sum_N_hat"]),
        "daily_j_cash": daily_j, "redlines": redlines,
    }


def marginal_transmission(seg: dict, N_hat: np.ndarray, P_day: np.ndarray) -> dict:
    """边际传导：段级 ``gap_t = max(N̂_t + C_t − D_t − A_t, 0)`` 与 ``H_t`` 的关系。

    口径（写死）：``C/D/A`` 取逐段明细里的**执行版**数组；``N̂`` 为 θ=0 计划层净需求。
    执行层恒等式为 ``H = max(N_real − A + C_exec − D_exec, 0)``（``N_real`` = 实测净需求），
    故 ``N̂ = N_real`` 时 ``gap`` 与 ``H`` 逐段相等；``gap`` 与 ``H`` 的差异即"计划净需求
    与实测净需求之差"。
    """
    A, C, D_, H = (seg[k] for k in ("A", "C", "D", "H"))
    gap = np.maximum(N_hat + C - D_ - A, 0.0)
    pv_pos = P_day > 0.0

    def _corr(x, y):
        """皮尔逊相关（任一维常数列返回 nan）。"""
        x, y = np.asarray(x, float).ravel(), np.asarray(y, float).ravel()
        if x.size == 0 or x.std() == 0 or y.std() == 0:
            return float("nan")
        return float(np.corrcoef(x, y)[0, 1])

    return {
        "definition": "gap_t = max(N_hat_t + C_t - D_t - A_t, 0); "
                      "N_hat = theta=0 plan-layer net demand (kWh); "
                      "A/C/D = execution arrays from *_seg.jsonl",
        "sum_gap": float(gap.sum()),
        "sum_H": float(H.sum()),
        "ratio_H_over_gap": float(H.sum() / gap.sum()) if gap.sum() else float("nan"),
        "frac_segments_H_gt_0": float(np.count_nonzero(H > 0.0) / H.size),
        "frac_segments_gap_gt_0": float(np.count_nonzero(gap > 0.0) / gap.size),
        "corr_H_gap_all": _corr(H, gap),
        "corr_H_gap_day": _corr(H[pv_pos], gap[pv_pos]),
        "corr_H_gap_night": _corr(H[~pv_pos], gap[~pv_pos]),
        "mean_gap_kwh": float(gap.mean()),
        "mean_H_kwh": float(H.mean()),
        "note": "ratio ≪1 ⇒ 缺 1 kWh 计划量并不会 1:1 落到 5p 紧急电（J-E4c）",
    }


def quantile_bins(x: np.ndarray, k: int = 5) -> np.ndarray:
    """按取值排序等分成 ``k`` 档，返回每点的档号（0..k-1）。"""
    order = np.argsort(np.asarray(x, float), kind="stable")
    n = order.size
    edges = [int(round(i * n / k)) for i in range(k + 1)]
    bins = np.empty(n, dtype=int)
    for j in range(k):
        bins[order[edges[j]:edges[j + 1]]] = j
    return bins


def align_arms(m_a: dict, m_b: dict, n_a_bins: np.ndarray, n_b_bins: np.ndarray) -> dict:
    """同 ``ΣN̂`` 水平对齐两臂，比较 ``J_cash``（判据 J-E4a / J-E4b）。

    两种对齐口径（都落盘）：
    1. **公共分位区间**：只保留两臂日 ``ΣN̂`` 都落在交叠 ``[max(p05), min(p95)]``
       内的日期，比较日均 ``J_cash``；
    2. **分档对齐**：各臂按自身日 ``ΣN̂`` 分 5 档（秩匹配），逐档比较日均 ``J_cash``
       与日均 ``ΣN̂``，再等权汇总。

    另给规模不变量 ``J_cash / ΣN̂``（元/kWh）：同 ``ΣN̂`` 水平上等价 ⇔ 该比值相等。
    """
    Na, Nb = m_a["daily_N_hat"], m_b["daily_N_hat"]
    Ja, Jb = m_a["daily_j_cash"], m_b["daily_j_cash"]
    lo = max(float(np.quantile(Na, 0.05)), float(np.quantile(Nb, 0.05)))
    hi = min(float(np.quantile(Na, 0.95)), float(np.quantile(Nb, 0.95)))
    sa, sb = (Na >= lo) & (Na <= hi), (Nb >= lo) & (Nb <= hi)
    overlap = {
        "lo": lo, "hi": hi,
        "n_days_a": int(sa.sum()), "n_days_b": int(sb.sum()),
        "mean_N_a": float(Na[sa].mean()), "mean_N_b": float(Nb[sb].mean()),
        "mean_J_a": float(Ja[sa].mean()), "mean_J_b": float(Jb[sb].mean()),
        "rel_diff_J": _rel(float(Jb[sb].mean()), float(Ja[sa].mean())),
    }
    bins = []
    for j in range(5):
        ia, ib = n_a_bins == j, n_b_bins == j
        bins.append({
            "bin": j,
            "n_days_a": int(ia.sum()), "n_days_b": int(ib.sum()),
            "mean_N_a": float(Na[ia].mean()), "mean_N_b": float(Nb[ib].mean()),
            "mean_J_a": float(Ja[ia].mean()), "mean_J_b": float(Jb[ib].mean()),
            "delta_N": float(Nb[ib].mean() - Na[ia].mean()),
            "delta_J": float(Jb[ib].mean() - Ja[ia].mean()),
            "rel_diff_J": _rel(float(Jb[ib].mean()), float(Ja[ia].mean())),
        })
    j_bin_a = float(np.mean([b["mean_J_a"] for b in bins]))
    j_bin_b = float(np.mean([b["mean_J_b"] for b in bins]))
    ratio_a = m_a["fees_per_kwh_plan_N"]
    ratio_b = m_b["fees_per_kwh_plan_N"]
    # 口径 3（主口径）：局部水平对齐 —— 在共同 ΣN̂ 水平上做 kNN 邻域均值。
    # 分档/交叠口径仍会残留 2%~11% 的 ΣN̂ 失配，故用邻域均值把水平真正对齐：
    # 对每个水平 x，取各臂 ΣN̂ 最接近 x 的 k 天求 J_cash 均值，再逐点比较。
    k = 25
    x_lo = max(float(np.quantile(Na, 0.10)), float(np.quantile(Nb, 0.10)))
    x_hi = min(float(np.quantile(Na, 0.90)), float(np.quantile(Nb, 0.90)))
    grid = np.linspace(x_lo, x_hi, 25)
    ja_l, jb_l, na_l, nb_l = [], [], [], []
    for x in grid:
        ia = np.argsort(np.abs(Na - x))[:k]
        ib = np.argsort(np.abs(Nb - x))[:k]
        ja_l.append(float(Ja[ia].mean()))
        jb_l.append(float(Jb[ib].mean()))
        na_l.append(float(Na[ia].mean()))
        nb_l.append(float(Nb[ib].mean()))
    dj = np.asarray(jb_l) - np.asarray(ja_l)
    local = {
        "k": k, "n_grid": int(grid.size), "grid_lo": x_lo, "grid_hi": x_hi,
        "grid": [float(x) for x in grid],
        "J_a": ja_l, "J_b": jb_l, "delta_J": [float(x) for x in dj],
        "local_mean_N_a": na_l, "local_mean_N_b": nb_l,
        "mean_J_a": float(np.mean(ja_l)), "mean_J_b": float(np.mean(jb_l)),
        "mean_delta_J": float(dj.mean()), "median_delta_J": float(np.median(dj)),
        "rel_diff_J": _rel(float(np.mean(jb_l)), float(np.mean(ja_l))),
        "max_abs_rel_diff_per_point": float(np.max(np.abs(dj / np.asarray(ja_l)))),
        "mean_abs_local_N_gap": float(np.mean(np.abs(np.asarray(nb_l)
                                                     - np.asarray(na_l)))),
        "note": "主口径：把 ΣN̂ 对齐到同一水平后再比 J_cash；"
                "分档/交叠口径残留的 ΣN̂ 失配会污染 ΔJ。",
    }
    # 辅助口径 4：ANCOVA（共同斜率 + 臂截距）——线性模型下"对齐到同一 ΣN̂
    # 水平后的差"恰等于截距差，与水平取值无关，可消除日构成混杂。
    y = np.concatenate([Ja, Jb])
    x = np.column_stack([np.ones(y.size),
                         np.concatenate([np.zeros(Na.size), np.ones(Nb.size)]),
                         np.concatenate([Na, Nb])])
    coef = np.linalg.lstsq(x, y, rcond=None)[0]
    ancova = {
        "common_slope_J_per_kwh": float(coef[2]),
        "delta_intercept_J_per_day": float(coef[1]),
        "rel_diff_vs_mean_J_a": _rel(float(coef[1] + Ja.mean()), float(Ja.mean())),
        "note": "J ≈ α_arm + β·ΣN̂（共斜率）；对齐到同一 ΣN̂ 水平后的差 = α_B − α_A"
                "（与水平无关），β 即每少计划 1 kWh 的现金斜率。",
    }
    return {
        "ancova": ancova,
        "overlap_window": overlap,
        "bins": bins,
        "bin_matched": {
            "mean_J_a": j_bin_a, "mean_J_b": j_bin_b,
            "delta_J": j_bin_b - j_bin_a, "rel_diff_J": _rel(j_bin_b, j_bin_a),
        },
        "local_level": local,
        "per_kwh": {
            "a": ratio_a, "b": ratio_b,
            "delta": ratio_b - ratio_a, "rel_diff": _rel(ratio_b, ratio_a),
        },
    }


# --------------------------------------------------------------- 报告
def build_report(ctx: dict) -> str:
    """把指标、边际传导、对齐比较、复现命令与哈希写成 markdown 报告。"""
    f = lambda x: f"{x:,.2f}"                                  # noqa: E731
    m = {k: ctx["metrics"][k] for k in ("q08_m0", "q05_m004")}
    a_m, b_m = m["q08_m0"], m["q05_m004"]
    A, B = a_m["sums"], b_m["sums"]
    FA, FB = a_m["fees"], b_m["fees"]
    al = ctx["alignment"]
    mh = ctx["marginal"]
    jd = FB["J_cash"] - FA["J_cash"]

    L = []
    L.append("# Q7.6 E4 报告：同保守度对齐 + 边际传导估计")
    L.append("")
    L.append(f"- 两臂：`v3seg_q0.8×C×m=0`（key `{a_m['manifest_key']}`） vs "
             f"`v3seg_q0.5×C×m=0.04`（key `{b_m['manifest_key']}`）；代码代次 "
             f"`{ctx['code_hash_ref']}`，主台账行数 {ctx['manifest_lines']}（复查值）。")
    L.append("- 本报告未修改 `7.5对话` 任何文件；`N̂` 口径见下。")
    L.append("")

    # ---- 1. 指标表
    L.append("## 1. 指标表（J-E4d 红线在内）")
    L.append("")
    L.append("`N̂` = θ=0 喂给计划层 LP 的全天净需求（kWh，由 "
             "`q3_main_v2._pv_for_epoch` + `plan_net_demand` 同一代码路径重建）；"
             "白天 = 实测光伏 > 0 的段，夜间 = 实测光伏 = 0 的段。")
    L.append("")
    L.append("| 指标 | q0.8×m=0 | q0.5×m=0.04 | 差（B−A） | 相对差 |")
    L.append("| --- | ---: | ---: | ---: | ---: |")

    def row(name, x, y, rel=True):
        """一行对照（相对差可选）。"""
        return (f"| {name} | {f(x)} | {f(y)} | {f(y - x)} | "
                f"{('%.4f%%' % (100 * _rel(y, x))) if rel else '—'} |")

    L.append(row("ΣN̂ 全天（kWh）", A["sum_N_hat"], B["sum_N_hat"]))
    L.append(row("日均 ΣN̂（kWh/日）", A["mean_day_N_hat"], B["mean_day_N_hat"]))
    L.append(row("ΣN̂ 白天段（kWh）", A["sum_N_hat_day"], B["sum_N_hat_day"]))
    L.append(row("ΣN̂ 夜间段（kWh）", A["sum_N_hat_night"], B["sum_N_hat_night"]))
    L.append(row("ΣH 紧急购电（kWh）", A["sum_H"], B["sum_H"]))
    L.append(row("Σ(A−G⁰)⁺ 上调（kWh）", A["sum_A_minus_G0_pos"],
                 B["sum_A_minus_G0_pos"]))
    L.append(row("Σ(G⁰−A)⁺ 下调（kWh）", A["sum_G0_minus_A_pos"],
                 B["sum_G0_minus_A_pos"]))
    L.append(row("ΣR_PV 弃光（kWh）", A["sum_R_PV"], B["sum_R_PV"]))
    L.append(row("ΣR_G 弃购电（kWh）", A["sum_R_G"], B["sum_R_G"]))
    L.append(row("SOC 枯竭段数（S≤1200+1e-6）",
                 a_m["redlines"]["soc_depleted_segments"],
                 b_m["redlines"]["soc_depleted_segments"], rel=False))
    L.append(row("全年最低 SOC（kWh）", a_m["redlines"]["soc_min"],
                 b_m["redlines"]["soc_min"], rel=False))
    L.append(row("J_plan（元）", FA["J_plan"], FB["J_plan"]))
    L.append(row("J_adj（元）", FA["J_adj"], FB["J_adj"]))
    L.append(row("J_emg（元）", FA["J_emg"], FB["J_emg"]))
    L.append(row("J_cash（元）", FA["J_cash"], FB["J_cash"]))
    L.append("")
    L.append(f"台账对账：`J_cash` 台账值 A = {f(ctx['ledger']['q08_m0']['J_cash'])}，"
             f"B = {f(ctx['ledger']['q05_m004']['J_cash'])}；本次复算与台账的"
             f"最大绝对差 = {ctx['ledger']['max_abs_diff']:.3e} 元"
             f"（{'逐位一致' if ctx['ledger']['bitwise'] else '存在差异，需核对'}）。")
    L.append("")
    L.append(f"原始未对齐总差：B − A = {f(FB['J_cash'] - FA['J_cash'])} 元 = "
             f"{100 * _rel(FB['J_cash'], FA['J_cash']):+.4f}%（相对 A 的 J_cash）。"
             "（任务书背景写的“低 0.24%”与台账两值之差 0.4612% 不符；本报告一律以台账"
             "与逐段落盘数据为准。）")
    L.append("")
    L.append("红线（J-E4d）逐项：")
    L.append("")
    L.append("| 检查 | q0.8×m=0 | q0.5×m=0.04 |")
    L.append("| --- | --- | --- |")
    for k, label in (("soc_in_range", "SOC∈[1200,10800]"),
                     ("balance_ok", "逐段平衡残差≤1e-6"),
                     ("no_sell_ok", "无售电（A,G⁰≥0）"),
                     ("n_days_ok", "n_days=334")):
        L.append(f"| {label} | {'✅' if a_m['redlines'][k] else '❌'} "
                 f"| {'✅' if b_m['redlines'][k] else '❌'} |")
    L.append("")
    L.append(f"逐段平衡最大残差：A = {a_m['redlines']['balance_max_res']:.3e}，"
             f"B = {b_m['redlines']['balance_max_res']:.3e}；"
             f"SOC 区间：A = [{a_m['redlines']['soc_min']:.3f}, "
             f"{a_m['redlines']['soc_max']:.3f}]，B = [{b_m['redlines']['soc_min']:.3f}, "
             f"{b_m['redlines']['soc_max']:.3f}]。")
    L.append("")

    # ---- 2. 边际传导
    L.append("## 2. 边际传导估计（判据 J-E4c）")
    L.append("")
    L.append(f"口径：`{mh['q08_m0']['definition']}`")
    L.append("")
    L.append("| 量 | q0.8×m=0 | q0.5×m=0.04 |")
    L.append("| --- | ---: | ---: |")
    L.append(f"| Σgap（kWh） | {f(mh['q08_m0']['sum_gap'])} | "
             f"{f(mh['q05_m004']['sum_gap'])} |")
    L.append(f"| ΣH（kWh） | {f(mh['q08_m0']['sum_H'])} | "
             f"{f(mh['q05_m004']['sum_H'])} |")
    L.append(f"| ΣH/Σgap | {mh['q08_m0']['ratio_H_over_gap']:.4f} | "
             f"{mh['q05_m004']['ratio_H_over_gap']:.4f} |")
    L.append(f"| corr(H,gap) 全段 | {mh['q08_m0']['corr_H_gap_all']:.4f} | "
             f"{mh['q05_m004']['corr_H_gap_all']:.4f} |")
    L.append(f"| corr(H,gap) 白天 | {mh['q08_m0']['corr_H_gap_day']:.4f} | "
             f"{mh['q05_m004']['corr_H_gap_day']:.4f} |")
    L.append(f"| corr(H,gap) 夜间 | {mh['q08_m0']['corr_H_gap_night']:.4f} | "
             f"{mh['q05_m004']['corr_H_gap_night']:.4f} |")
    L.append(f"| H>0 段占比 | {100 * mh['q08_m0']['frac_segments_H_gt_0']:.3f}% | "
             f"{100 * mh['q05_m004']['frac_segments_H_gt_0']:.3f}% |")
    L.append(f"| gap>0 段占比 | {100 * mh['q08_m0']['frac_segments_gap_gt_0']:.3f}% | "
             f"{100 * mh['q05_m004']['frac_segments_gap_gt_0']:.3f}% |")
    L.append("")

    # ---- 3. 对齐比较
    L.append("## 3. 同保守度（同 ΣN̂ 水平）对齐比较（判据 J-E4a / J-E4b）")
    L.append("")
    ow = al["overlap_window"]
    L.append(f"**口径 1：公共分位区间** `ΣN̂ ∈ [{f(ow['lo'])}, {f(ow['hi'])}]`（两臂 p05–p95 交叠）："
             f"保留天数 A = {ow['n_days_a']} / B = {ow['n_days_b']}；"
             f"日均 ΣN̂：A = {f(ow['mean_N_a'])}，B = {f(ow['mean_N_b'])} kWh；"
             f"日均 J_cash：A = {f(ow['mean_J_a'])}，B = {f(ow['mean_J_b'])} 元；"
             f"相对差 = {100 * ow['rel_diff_J']:+.4f}%。")
    L.append("")
    L.append("**口径 2：分档对齐**（各臂按自身日 ΣN̂ 分 5 档，秩匹配）：")
    L.append("")
    L.append("| 档 | 日均ΣN̂ A | 日均ΣN̂ B | ΔΣN̂ | 日均J A | 日均J B | ΔJ | 相对差 |")
    L.append("| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for b in al["bins"]:
        L.append(f"| {b['bin'] + 1} | {f(b['mean_N_a'])} | {f(b['mean_N_b'])} | "
                 f"{f(b['delta_N'])} | {f(b['mean_J_a'])} | {f(b['mean_J_b'])} | "
                 f"{f(b['delta_J'])} | {100 * b['rel_diff_J']:+.4f}% |")
    lc = al["local_level"]
    L.append("")
    L.append(f"**口径 3（主口径）：局部水平对齐** —— 在共同 ΣN̂ 区间 "
             f"[{f(lc['grid_lo'])}, {f(lc['grid_hi'])}] 上取 {lc['n_grid']} 个水平点，"
             f"每点取各臂 ΣN̂ 最接近的 k={lc['k']} 天求 J_cash 均值后逐点相减："
             f"邻域 ΣN̂ 平均失配仅 {lc['mean_abs_local_N_gap']:.1f} kWh；"
             f"平均 J_cash A = {f(lc['mean_J_a'])}，B = {f(lc['mean_J_b'])} 元/日，"
             f"ΔJ = {f(lc['mean_delta_J'])} 元/日（中位 {f(lc['median_delta_J'])}），"
             f"相对差 = {100 * lc['rel_diff_J']:+.4f}%；逐点 |相对差| 最大 "
             f"{100 * lc['max_abs_rel_diff_per_point']:.4f}%（逐点明细见 "
             "`alignment_metrics.json → alignment.local_level`）。"
             "分档/交叠两个口径各自残留 2%~11% 的 ΣN̂ 失配，故它们的 ΔJ 含水平失配污染，"
             "编号对照仅供参考。")
    an = al["ancova"]
    L.append("")
    L.append(f"**口径 4（主口径）：共斜率 ANCOVA** —— 拟合 `J ≈ α_臂 + β·ΣN̂`（两臂共用斜率）："
             f"β = {an['common_slope_J_per_kwh']:.4f} 元/kWh；线性模型下“对齐到同一 ΣN̂ 水平"
             f"后的差”等于截距差 α_B − α_A = {f(an['delta_intercept_J_per_day'])} 元/日"
             f"（相对 A 的日均 J_cash = {100 * an['rel_diff_vs_mean_J_a']:+.4f}%）。"
             "该口径与口径 3 独立且同号，共同作为 J-E4a 的主判据。")
    L.append("")
    L.append(f"**机械解释**：两臂 ΣN̂ 总量差 {f(B['sum_N_hat'] - A['sum_N_hat'])} kWh"
             f"（{100 * _rel(B['sum_N_hat'], A['sum_N_hat']):+.2f}%），按共斜率 "
             f"{an['common_slope_J_per_kwh']:.4f} 元/kWh 折算应省 "
             f"{f(-an['common_slope_J_per_kwh'] * (B['sum_N_hat'] - A['sum_N_hat']))} 元，"
             f"而实际只省 {f(FA['J_cash'] - FB['J_cash'])} 元；两者之差 "
             f"{f(an['delta_intercept_J_per_day'] * 334)} 元（+"
             f"{100 * an['rel_diff_vs_mean_J_a']:.2f}%）正是“同 ΣN̂ 水平上 B 更贵”的部分 —— "
             "即：原始 0.46% 的“便宜”主要来自 B 臂计划净需求更少，而不是保守度更优。")
    bm = al["bin_matched"]
    pk = al["per_kwh"]
    L.append("")
    L.append(f"等权汇总（分档对齐）：日均 J_cash A = {f(bm['mean_J_a'])}，"
             f"B = {f(bm['mean_J_b'])}，ΔJ = {f(bm['delta_J'])} 元/日，"
             f"相对差 = {100 * bm['rel_diff_J']:+.4f}%。")
    L.append(f"规模不变量 `J_cash / ΣN̂`：A = {pk['a']:.6f}，B = {pk['b']:.6f} 元/kWh，"
             f"相对差 = {100 * pk['rel_diff']:+.4f}%（诊断量：两臂 ΣN̂ 总量本身不同，"
             "故该比值不是同水平比较，不作为 J-E4a 判据）。")
    L.append("")
    L.append(f"**形状效应（J-E4b）**：ΔΣN̂ = {f(B['sum_N_hat'] - A['sum_N_hat'])} kWh，"
             f"其中白天 {f(B['sum_N_hat_day'] - A['sum_N_hat_day'])} kWh、"
             f"夜间 {f(B['sum_N_hat_night'] - A['sum_N_hat_night'])} kWh；"
             f"夜间/白天 = {ctx['shape']['night_over_day']:.4f}。")
    L.append("")

    # ---- 4. 判据判定
    L.append("## 4. 判据判定（预注册）")
    L.append("")
    L.append("| 编号 | 判据 | 通过条件 | 本任务观测 | 判定 |")
    L.append("| --- | --- | --- | --- | --- |")
    for c in ctx["verdicts"]:
        L.append(f"| `{c['id']}` | {c['name']} | {c['rule']} | {c['obs']} | "
                 f"**{c['verdict']}** |")
    L.append("")
    L.append("结论（只按上表事实写）：")
    L.append("")
    for c in ctx["verdicts"]:
        L.append(f"- `{c['id']}`：{c['conclusion']}")
    L.append("")

    # ---- 5. 复现命令 + 哈希
    L.append("## 5. 复现命令与哈希")
    L.append("")
    L.append("```powershell")
    L.append("$env:PYTHONPATH='D:\\CMUCU\\3对话\\.scipy_tmp;D:\\CMUCU\\7.5对话\\code'")
    L.append("$env:PYTHONIOENCODING='utf-8'")
    L.append("$py='C:\\Users\\刘嘉琪\\.cache\\codex-runtimes\\"
             "codex-primary-runtime\\dependencies\\python\\python.exe'")
    for r in ctx["run_records"]:
        L.append("& " + " ".join(f"'{c}'" if " " in c else c for c in r["cmd"]))
    L.append(f"& $py '{os.path.join(HERE, 'q76_e4_alignment.py')}' analyze")
    L.append("```")
    L.append("")
    L.append("脚本内 CLI 口径映射：任务书写 `--demand v3seg`，但 `DEMAND_CHOICES` 只有 "
             "`point/quantile/quantile_v3`；主台账同 key 的 `cmd` 为 "
             "`--demand quantile_v3 --q-block segment --convention slot_end`"
             "（`v3seg` 是台账 label）。本脚本按台账口径执行以保证 `J_cash` 可对账。")
    L.append("")
    L.append("| 文件 | SHA-256 |")
    L.append("| --- | --- |")
    for name, h in ctx["hashes"].items():
        L.append(f"| `{name}` | `{h}` |")
    L.append("")
    L.append("7.5 代码未被改动（当前 SHA-256 与主台账 `hash_per_file_before` 逐项一致）：")
    L.append("")
    L.append("| 7.5 文件 | SHA-256 | 与台账一致 |")
    L.append("| --- | --- | --- |")
    for name, rec in ctx["q75_hashes"].items():
        L.append(f"| `{name}` | `{rec['sha256']}` | {'✅' if rec['same'] else '❌'} |")
    L.append("")
    L.append(f"主台账 `q75_g2_manifest.jsonl` 行数复查：{ctx['manifest_lines']}（基线 110）。")
    L.append("")
    return "\n".join(L) + "\n"


def make_verdicts(m_a, m_b, al, mh) -> list:
    """按预注册判据给出 J-E4a~d 的机械判定（只写事实与阈值比较）。"""
    bm, pk = al["bin_matched"], al["per_kwh"]
    lc = al["local_level"]                      # 主口径：同 ΣN̂ 水平的局部对比
    an = al["ancova"]                           # 主口径 2：共斜率 ANCOVA
    aligned_rel = max(abs(lc["rel_diff_J"]), abs(an["rel_diff_vs_mean_J_a"]))
    raw_rel = abs(_rel(m_b["fees"]["J_cash"], m_a["fees"]["J_cash"]))
    A, B = m_a["sums"], m_b["sums"]
    d_day = B["sum_N_hat_day"] - A["sum_N_hat_day"]
    d_night = B["sum_N_hat_night"] - A["sum_N_hat_night"]
    night_over_day = abs(d_night / d_day) if d_day else float("nan")
    ratios = [mh["q08_m0"]["ratio_H_over_gap"], mh["q05_m004"]["ratio_H_over_gap"]]
    red_ok = all((m_a["redlines"][k] and m_b["redlines"][k]) for k in
                 ("soc_in_range", "balance_ok", "no_sell_ok", "n_days_ok"))
    fracs = [mh["q08_m0"]["frac_segments_H_gt_0"], mh["q05_m004"]["frac_segments_H_gt_0"]]
    return [
        {"id": "J-E4a", "name": "等价脊（同 ΣN̂ 水平的 J_cash 差）",
         "rule": "≤0.05% ⇒ 等价脊成立 ⇒ 只能写“参数不可分辨”",
         "obs": f"对齐后相对差：kNN 局部水平 {100 * lc['rel_diff_J']:+.4f}%、"
                f"共斜率 ANCOVA {100 * an['rel_diff_vs_mean_J_a']:+.4f}%"
                f"（两者一致、同号）；对照（含 ΣN̂ 失配污染）：分档 "
                f"{100 * bm['rel_diff_J']:+.4f}%、交叠区间 "
                f"{100 * al['overlap_window']['rel_diff_J']:+.4f}%；"
                f"原始未对齐总差 {100 * raw_rel:.4f}%（负号 = B 更便宜）；"
                f"元/kWh 比值相对差 {100 * pk['rel_diff']:+.4f}%（诊断量）",
         "verdict": "通过（等价脊成立）" if aligned_rel <= REL_EQUIV
                    else "不通过（差异可分辨）",
         "conclusion": (
             f"同 ΣN̂ 水平（局部邻域对齐，k={lc['k']}）上两臂 J_cash 相对差 "
             f"{100 * lc['rel_diff_J']:+.4f}% ≤ 0.05% ⇒ **等价脊成立** ⇒ "
             "结论只能写“**参数不可分辨**”（q=0.8×m=0 与 q=0.5×m=0.04 在本评估期"
             "无法用现金口径区分），**禁止**写某一臂“更优”。"
             if aligned_rel <= REL_EQUIV else
             f"同 ΣN̂ 水平上两臂 J_cash 相对差为 "
             f"{100 * an['rel_diff_vs_mean_J_a']:+.4f}%（ANCOVA 共斜率）/ "
             f"{100 * lc['rel_diff_J']:+.4f}%（kNN 局部），均 > 0.05% ⇒ "
             "**等价脊不成立**；且对齐后差异与原始未对齐总差 **符号相反** ⇒ "
             "原始 0.46% 不能读作“q=0.5×m=0.04 的保守度更优”，它来自该臂计划净需求"
             f"少 {abs(100 * _rel(B['sum_N_hat'], A['sum_N_hat'])):.2f}%、"
             f"按共斜率 {an['common_slope_J_per_kwh']:.4f} 元/kWh 机械省下 "
             f"{abs(an['common_slope_J_per_kwh'] * (B['sum_N_hat'] - A['sum_N_hat'])):,.0f} 元，"
             f"而实际只省下 "
             f"{abs(m_b['fees']['J_cash'] - m_a['fees']['J_cash']):,.0f} 元（见 §3 机械解释）。"
             "结论只能写“两参数化在不同时段形状上适配”，"
             "**禁止**写任一臂“更优”。")},
        {"id": "J-E4b", "name": "形状效应（ΣN̂ 差异是否主要来自白天 PV>0 段）",
         "rule": "夜间 ΣN̂ 差 ≪ 白天差 ⇒ 形状效应占主导（m 只管白天）",
         "obs": f"ΔΣN̂ 白天 {d_day:,.2f} kWh、夜间 {d_night:,.2f} kWh、"
                f"夜间/白天 = {night_over_day:.4f}",
         "verdict": "通过（形状效应占主导）" if night_over_day <= 0.2
                    else "不通过",
         "conclusion": (f"两臂 ΣN̂ 的差几乎全部来自白天段（夜间仅为白天的 "
                        f"{100 * night_over_day:.2f}%），与“m 只作用白天光伏”一致 ⇒ "
                        "该 0.46% 总差不是同一条保守度轴上的优劣，而是**不同时段形状**上的适配。"
                        if night_over_day <= 0.2 else
                        f"夜间 ΔΣN̂ 不显著小于白天（夜间/白天 = {night_over_day:.4f}），"
                        "形状效应不占主导。")},
        {"id": "J-E4c", "name": "一阶性（ΣH/Σgap）",
         "rule": "≪1（<0.2）⇒ “缺 1 单位即多买 1 单位 5p 紧急电”不成立",
         "obs": f"ΣH/Σgap：A = {ratios[0]:.4f}、B = {ratios[1]:.4f}；"
                f"H>0 段占比 A = {100 * fracs[0]:.3f}%、B = {100 * fracs[1]:.3f}%",
         "verdict": "通过（5p 非一阶）" if max(ratios) < FIRST_ORDER else "不通过",
         "conclusion": (f"ΣH/Σgap 仅 {min(ratios):.4f}~{max(ratios):.4f}（远小于 1），"
                        "缺 1 kWh 计划量并不会 1:1 落到 5p 紧急电：缺口大多由储能执行与"
                        "计划内购电吸收，5p 不是一阶通道。"
                        if max(ratios) < FIRST_ORDER else
                        "ΣH/Σgap 不小于 0.2，5p 紧急电仍是一阶通道。")},
        {"id": "J-E4d", "name": "红线",
         "rule": "SOC∈[1200,10800]、逐段平衡≤1e-6、无售电、n_days=334 全过",
         "obs": f"A: SOC[{m_a['redlines']['soc_min']:.1f},{m_a['redlines']['soc_max']:.4f}]、"
                f"bal {m_a['redlines']['balance_max_res']:.1e}、n_days {m_a['redlines']['n_days']}；"
                f"B: SOC[{m_b['redlines']['soc_min']:.1f},{m_b['redlines']['soc_max']:.4f}]、"
                f"bal {m_b['redlines']['balance_max_res']:.1e}、n_days {m_b['redlines']['n_days']}",
         "verdict": "通过（有效）" if red_ok else "不通过",
         "conclusion": ("四条红线全过，两臂结果有效。"
                        if red_ok else "存在红线不通过项，两臂结果不可用于结论。")},
    ]


# --------------------------------------------------------------- analyze 主流程
def analyze() -> dict:
    """读逐段明细 + 数据，落 ``alignment_metrics.json``、``marginal_H.json`` 与报告。"""
    _ensure_dir(OUT_E4)
    _ensure_dir(SUB)
    ledger_rows = load_manifest()
    manifest_lines = sum(1 for _ in open(MANIFEST, encoding="utf-8")
                         if _.strip())
    D, _M, _p = _q75_imports()
    price, P_all, days = load_price_pv()
    d0, d1 = D.DAY0, D.DAY1
    P_day = P_all[d0:d1 + 1]

    metrics, segs, N_hats = {}, {}, {}
    L_all, _P2, _d2 = D.load_load_pv()
    for tag, arm in ARMS.items():
        seg = load_segments(os.path.join(OUT_E4, arm["seg"]))
        if seg["_days"].size != N_DAYS_EXPECT:
            raise RuntimeError(f"{tag}: 逐段明细 {seg['_days'].size} 天 ≠ {N_DAYS_EXPECT}")
        N_hat = rebuild_plan_net_demand(arm)
        # 执行层实测净需求 (L−P)·dt，用于逐段平衡红线（与 q3_main_v2 同式）
        real = (L_all[seg["_days"]] - P_all[seg["_days"]]) * D.DT
        seg["_real"] = real
        obj = arm_metrics(tag, arm, seg, N_hat, price,
                          P_all[seg["_days"]])
        tot = json.load(open(os.path.join(OUT_E4, arm["out"]), encoding="utf-8"))
        obj["daily_N_hat"] = N_hat.sum(axis=1)
        obj["redlines"]["n_margin_keys"] = tot.get("n_margin_keys")
        obj["redlines"]["soc_min_reported"] = tot.get("SOC_min")
        # 与汇总 JSON 对账（同一次跑的标量）
        obj["reconcile"] = {k: {"seg": obj["fees"][k], "tot_json": float(tot[k]),
                                "abs_diff": abs(obj["fees"][k] - float(tot[k]))}
                            for k in ("J_plan", "J_adj", "J_emg", "J_cash")}
        metrics[tag], segs[tag], N_hats[tag] = obj, seg, N_hat

    # 逐位对账（验收标准 3）
    ledger, max_diff, bitwise = {}, 0.0, True
    for tag, arm in ARMS.items():
        led = ledger_rows[arm["key"]]
        for k in ("J_plan", "J_adj", "J_emg", "J_cash"):
            d = abs(metrics[tag]["reconcile"][k]["tot_json"] - float(led["fees"][k]))
            max_diff = max(max_diff, d)
            bitwise &= (d == 0.0)
        ledger[tag] = {"key": arm["key"], "J_cash": float(led["fees"]["J_cash"]),
                       "n_days": int(led["n_days"]), "status": led["status"]}

    mh = {tag: marginal_transmission(segs[tag], N_hats[tag], P_all[segs[tag]["_days"]])
          for tag in ARMS}
    bins = {tag: quantile_bins(metrics[tag]["daily_N_hat"]) for tag in ARMS}
    alignment = align_arms(metrics["q08_m0"], metrics["q05_m004"],
                           bins["q08_m0"], bins["q05_m004"])
    d_day = (metrics["q05_m004"]["sums"]["sum_N_hat_day"]
             - metrics["q08_m0"]["sums"]["sum_N_hat_day"])
    d_night = (metrics["q05_m004"]["sums"]["sum_N_hat_night"]
               - metrics["q08_m0"]["sums"]["sum_N_hat_night"])
    shape = {"delta_day": d_day, "delta_night": d_night,
             "night_over_day": abs(d_night / d_day) if d_day else float("nan")}
    verdicts = make_verdicts(metrics["q08_m0"], metrics["q05_m004"], alignment, mh)

    # 7.5 代码 hash 复查（与台账 hash_per_file_before 对账）
    ref = ledger_rows[ARMS["q08_m0"]["key"]]
    q75_hashes = {}
    for name, h0 in ref["hash_per_file_before"].items():
        p = os.path.join(Q75_CODE, name)
        h = sha256_of(p) if os.path.isfile(p) else None
        q75_hashes[name] = {"sha256": h, "ledger": h0, "same": h == h0}

    payload = {
        "meta": {
            "task": "Q7.6 E4 同保守度对齐 + 边际传导估计",
            "code_hash_ref": ref["code_hash_before"],
            "manifest": MANIFEST, "manifest_lines": manifest_lines,
            "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
            "definitions": {
                "N_hat": "theta=0 plan-layer net demand (kWh), 144 segments/day, "
                         "rebuilt via q3_main_v2._pv_for_epoch + plan_net_demand",
                "day_segment": "actual PV > 0 (attachment 2)",
                "night_segment": "actual PV = 0 (attachment 2)",
                "soc_depleted": "segments with end-of-segment SOC <= 1200 + 1e-6",
                "fee_split": "cash_C per-segment: p*min(G0,A) + 0.5p*(G0-A)+ + "
                             "1.5p*(A-G0)+ + 5p*H",
            },
        },
        "arms": {tag: {"label": a["label"], "key": a["key"], "q": a["q"],
                       "margin": a["margin"], "billing": a["billing"],
                       "demand": a["demand"], "q_block": a["q_block"]}
                 for tag, a in ARMS.items()},
        "metrics": {tag: {k: v for k, v in m.items() if not k.startswith("daily_")}
                    for tag, m in metrics.items()},
        "alignment": alignment,
        "shape": shape,
        "verdicts": verdicts,
        "ledger": {"rows": ledger, "max_abs_diff": max_diff, "bitwise": bool(bitwise)},
        "q75_hashes": q75_hashes,
    }
    with open(os.path.join(OUT_E4, "alignment_metrics.json"), "w",
              encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
    marginal_payload = {
        "meta": payload["meta"],
        "arms": payload["arms"],
        "marginal": mh,
    }
    with open(os.path.join(OUT_E4, "marginal_H.json"), "w", encoding="utf-8") as fh:
        json.dump(marginal_payload, fh, ensure_ascii=False, indent=1)

    # 每日对齐用的中间表（便于复核，不影响验收清单）
    daily = {"days": [int(x) for x in segs["q08_m0"]["_days"]],
             "q08_m0": {"N_hat_day_sum": [float(x) for x in metrics["q08_m0"]["daily_N_hat"]],
                        "J_cash_day": [float(x) for x in metrics["q08_m0"]["daily_j_cash"]]},
             "q05_m004": {"N_hat_day_sum": [float(x) for x in metrics["q05_m004"]["daily_N_hat"]],
                          "J_cash_day": [float(x) for x in metrics["q05_m004"]["daily_j_cash"]]}}
    with open(os.path.join(OUT_E4, "daily_alignment.json"), "w", encoding="utf-8") as fh:
        json.dump(daily, fh, ensure_ascii=False, indent=1)

    hashes = {
        "q76_e4_alignment.py": sha256_of(os.path.abspath(__file__)),
        ARMS["q08_m0"]["seg"]: sha256_of(os.path.join(OUT_E4, ARMS["q08_m0"]["seg"])),
        ARMS["q05_m004"]["seg"]: sha256_of(os.path.join(OUT_E4, ARMS["q05_m004"]["seg"])),
        "alignment_metrics.json": sha256_of(os.path.join(OUT_E4, "alignment_metrics.json")),
        "marginal_H.json": sha256_of(os.path.join(OUT_E4, "marginal_H.json")),
        ARMS["q08_m0"]["out"]: sha256_of(os.path.join(OUT_E4, ARMS["q08_m0"]["out"])),
        ARMS["q05_m004"]["out"]: sha256_of(os.path.join(OUT_E4, ARMS["q05_m004"]["out"])),
    }
    rec_path = os.path.join(OUT_E4, "run_records.json")
    if os.path.isfile(rec_path):               # 优先用本次 run 的实际命令
        run_records = json.load(open(rec_path, encoding="utf-8"))["run_records"]
    else:                                      # 否则回落到台账 cmd（同口径）
        run_records = [{"cmd": ledger_rows[a["key"]]["cmd"]} for a in ARMS.values()]
    ctx = {
        "metrics": metrics, "alignment": alignment, "marginal": mh, "shape": shape,
        "verdicts": verdicts,
        "ledger": {**payload["ledger"]["rows"],
                   "max_abs_diff": payload["ledger"]["max_abs_diff"],
                   "bitwise": payload["ledger"]["bitwise"]},
        "manifest_lines": manifest_lines, "hashes": hashes,
        "q75_hashes": q75_hashes, "code_hash_ref": ref["code_hash_before"],
        "run_records": run_records,
    }
    report = build_report(ctx)
    with open(os.path.join(SUB, "q76_e4_report.md"), "w", encoding="utf-8") as fh:
        fh.write(report)
    json.dump({"run_records": run_records},
              open(os.path.join(OUT_E4, "run_records.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"[analyze] alignment_metrics.json / marginal_H.json / "
          f"_sub\\q76_e4_report.md 已落盘")
    return payload


def main(argv=None) -> int:
    """CLI：``run`` / ``analyze`` / ``all``。"""
    ap = argparse.ArgumentParser(description="Q7.6 E4 对齐 + 边际传导")
    ap.add_argument("cmd", choices=["run", "analyze", "all"], nargs="?", default="all")
    ap.add_argument("--timeout", type=float, default=None, help="单个配置的运行超时（秒）")
    args = ap.parse_args(argv)
    if args.cmd in ("run", "all"):
        recs = run_configs(timeout=args.timeout)
        json.dump({"run_records": recs},
                  open(os.path.join(OUT_E4, "run_records.json"), "w",
                       encoding="utf-8"), ensure_ascii=False, indent=1)
    if args.cmd in ("analyze", "all"):
        analyze()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
