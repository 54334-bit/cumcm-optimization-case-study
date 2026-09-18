"""Q1 独立验证器。

本验证器不复用建模矩阵，直接从解向量各分量按物理式重算，遵循
``Q1_1.0.md`` §4.5 与 §9 容差链。
"""

from __future__ import annotations

from typing import Dict, List

import numpy as np

from q1_common import (
    ETA_C,
    ETA_D,
    T,
    EBAR,
    S0,
    S_T,
    S_MIN,
    S_MAX,
    LATE_START,
    LATE_END,
    N_LATE,
)


def validate(
    price: np.ndarray,
    load_e: np.ndarray,
    pv_e: np.ndarray,
    comp: Dict[str, np.ndarray],
    j1_star: float,
    j_actual: float,
    h_report: float,
    j0: float,
    eps: Dict[str, float],
    eta_c: float = ETA_C,
    eta_d: float = ETA_D,
    s0: float = S0,
    s_t: float = S_T,
    s_min: float = S_MIN,
    s_max: float = S_MAX,
    ebar: float = EBAR,
) -> List[Dict[str, object]]:
    """逐项检查，返回 errors 列表（空列表表示通过）。"""
    price = np.asarray(price, dtype=float)
    load_e = np.asarray(load_e, dtype=float)
    pv_e = np.asarray(pv_e, dtype=float)
    G = np.asarray(comp["G"], dtype=float)
    C = np.asarray(comp["C"], dtype=float)
    D = np.asarray(comp["D"], dtype=float)
    R = np.asarray(comp["R"], dtype=float)
    S = np.asarray(comp["S"], dtype=float)

    eps_energy = float(eps["eps_energy"])
    eps_soc = float(eps["eps_soc"])
    eps_cost = float(eps["eps_cost"])
    eps_j = float(eps["eps_J"])
    eps_mutex = float(eps["eps_mutex"])

    errors: List[Dict[str, object]] = []

    def _add(name: str, detail: str) -> None:
        errors.append({"check": name, "detail": detail})

    # 1) 平衡残差
    e_bal = G + pv_e + D - load_e - C - R
    if float(np.max(np.abs(e_bal))) > eps_energy:
        _add("energy_balance", f"max|e_bal|={float(np.max(np.abs(e_bal))):.6e} > {eps_energy:.3e}")

    # 2) SOC 递推残差
    e_soc = S[1:] - S[:-1] - eta_c * C + D / eta_d
    if float(np.max(np.abs(e_soc))) > eps_soc:
        _add("soc_recursion", f"max|e_soc|={float(np.max(np.abs(e_soc))):.6e} > {eps_soc:.3e}")

    # 3) 非负与上界
    if float(np.min(G)) < -eps_energy:
        _add("G_nonneg", f"min G={float(np.min(G)):.6e}")
    if float(np.min(C)) < -eps_energy:
        _add("C_nonneg", f"min C={float(np.min(C)):.6e}")
    if float(np.min(D)) < -eps_energy:
        _add("D_nonneg", f"min D={float(np.min(D)):.6e}")
    if float(np.min(R)) < -eps_energy:
        _add("R_nonneg", f"min R={float(np.min(R)):.6e}")
    if float(np.max(R - pv_e)) > eps_energy:
        _add("R_upper", f"max(R-PV_e)={float(np.max(R - pv_e)):.6e}")
    if float(np.max(C - ebar)) > eps_energy:
        _add("C_upper", f"max(C-Ebar)={float(np.max(C - ebar)):.6e}")
    if float(np.max(D - ebar)) > eps_energy:
        _add("D_upper", f"max(D-Ebar)={float(np.max(D - ebar)):.6e}")

    # 4) SOC 区间与初末
    if float(np.min(S - s_min)) < -eps_soc:
        _add("S_lower", f"min(S-S_min)={float(np.min(S - s_min)):.6e}")
    if float(np.max(S - s_max)) > eps_soc:
        _add("S_upper", f"max(S-S_max)={float(np.max(S - s_max)):.6e}")
    if abs(float(S[0]) - s0) > eps_soc:
        _add("S0", f"|S0-{s0}|={abs(float(S[0]) - s0):.6e}")
    if abs(float(S[-1]) - s_t) > eps_soc:
        _add("ST", f"|ST-{s_t}|={abs(float(S[-1]) - s_t):.6e}")

    # 5) 循环守恒 Q_D = eta_c*eta_d*Q_C
    q_c = float(np.sum(C))
    q_d = float(np.sum(D))
    if abs(q_d - eta_c * eta_d * q_c) > T * eps_energy:
        _add("cycle_conservation", f"|Q_D-0.81*Q_C|={abs(q_d - eta_c * eta_d * q_c):.6e}")

    # 6) 互斥 min(C_t, D_t) <= eps_mutex
    mutex = np.minimum(C, D)
    if float(np.max(mutex)) > eps_mutex:
        _add("mutex", f"max min(C,D)={float(np.max(mutex)):.6e} > {eps_mutex:.3e}")

    # 7) 费用
    if j_actual > j1_star + eps_j:
        _add("cost_lock", f"J_actual={j_actual:.8f} > J1*+eps_J={j1_star + eps_j:.8f}")
    if j1_star > j0 + eps_cost:
        _add("J0_upper", f"J1*={j1_star:.8f} > J0+eps_cost={j0 + eps_cost:.8f}")

    # 8) 晚峰下界（后验，用实际 S_108）
    late_net = float(np.sum(load_e[LATE_START:LATE_END] - pv_e[LATE_START:LATE_END]))
    s_late = float(S[LATE_START])
    late_max_discharge = min(eta_d * (s_late - s_min), N_LATE * ebar)
    late_min_purchase = max(0.0, late_net - late_max_discharge)
    late_purchase = float(np.sum(G[LATE_START:LATE_END]))
    if late_purchase < late_min_purchase - N_LATE * eps_energy:
        _add(
            "late_lower_bound",
            f"late G={late_purchase:.6f} < LateMinPurchase_actual={late_min_purchase:.6f}",
        )

    # 9) 独立重算费用与吞吐一致
    j_recalc = float(np.dot(price, G))
    if abs(j_recalc - j_actual) > eps_cost:
        _add("cost_recalc", f"recalc J={j_recalc:.8f} vs report J_actual={j_actual:.8f}")
    h_recalc = float(np.sum(C + D))
    if abs(h_recalc - h_report) > eps_energy:
        _add(
            "throughput_recalc",
            f"recalc H={h_recalc:.8f} vs report H={h_report:.8f}",
        )

    return errors
