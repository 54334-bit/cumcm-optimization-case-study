"""Q1 两阶段 LP 求解与 MILP 兜底。

建模口径严格对齐 ``Q1_1.0.md`` §3、§10：

- 变量顺序 ``x = [G(0..143), C(0..143), D(0..143), R(0..143), S(0..144)]``。
- ``S_t`` 为时间节点 ``t*10min`` 处的储电量（``S_0``=0:00，``S_144``=24:00）。
- 储能递推 ``S_{t+1} = S_t + eta_c*C_t - D_t/eta_d``。
"""

from __future__ import annotations

from typing import Dict, Tuple

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, linprog, milp

from q1_common import (
    ETA_C,
    ETA_D,
    T,
    EBAR,
    S0,
    S_T,
    S_MIN,
    S_MAX,
)


# 变量块偏移
_OFF_G = 0
_OFF_C = T
_OFF_D = 2 * T
_OFF_R = 3 * T
_OFF_S = 4 * T
N_VAR = 4 * T + (T + 1)  # 721


_LP_STATUS = {0: "optimal", 1: "iteration_limit", 2: "infeasible", 3: "unbounded", 4: "numerical"}


def _lp_status_str(code: int) -> str:
    return _LP_STATUS.get(int(code), f"status_{code}")


def _idx_g(t: int) -> int:
    return _OFF_G + t


def _idx_c(t: int) -> int:
    return _OFF_C + t


def _idx_d(t: int) -> int:
    return _OFF_D + t


def _idx_r(t: int) -> int:
    return _OFF_R + t


def _idx_s(t: int) -> int:
    return _OFF_S + t


def build_model(
    price: np.ndarray,
    load_e: np.ndarray,
    pv_e: np.ndarray,
    eta_c: float = ETA_C,
    eta_d: float = ETA_D,
    s0: float = S0,
    s_t: float = S_T,
    s_min: float = S_MIN,
    s_max: float = S_MAX,
    ebar: float = EBAR,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, list]:
    """构造 Q1 线性规划的等式矩阵、右端项、目标向量与变量边界。

    Returns
    -------
    (A_eq, b_eq, c1, bounds)
        ``c1`` 为第一阶段成本目标系数；第二阶段目标 ``c2`` 由调用方自行构造。
    """
    price = np.asarray(price, dtype=float)
    load_e = np.asarray(load_e, dtype=float)
    pv_e = np.asarray(pv_e, dtype=float)
    if price.shape != (T,) or load_e.shape != (T,) or pv_e.shape != (T,):
        raise ValueError("price/load_e/pv_e 长度必须为 T=144")

    n_eq = 2 * T + 2
    A_eq = np.zeros((n_eq, N_VAR), dtype=float)
    b_eq = np.zeros(n_eq, dtype=float)

    # 1) 能量平衡 G_t + D_t - C_t - R_t = Load_e - PV_e
    for t in range(T):
        A_eq[t, _idx_g(t)] = 1.0
        A_eq[t, _idx_d(t)] = 1.0
        A_eq[t, _idx_c(t)] = -1.0
        A_eq[t, _idx_r(t)] = -1.0
        b_eq[t] = load_e[t] - pv_e[t]

    # 2) 储能递推 S_{t+1} - S_t - eta_c*C_t + D_t/eta_d = 0
    for t in range(T):
        row = T + t
        A_eq[row, _idx_s(t + 1)] = 1.0
        A_eq[row, _idx_s(t)] = -1.0
        A_eq[row, _idx_c(t)] = -eta_c
        A_eq[row, _idx_d(t)] = 1.0 / eta_d
        b_eq[row] = 0.0

    # 3) S_0 = s0
    A_eq[2 * T, _idx_s(0)] = 1.0
    b_eq[2 * T] = s0

    # 4) S_T = s_t
    A_eq[2 * T + 1, _idx_s(T)] = 1.0
    b_eq[2 * T + 1] = s_t

    # 第一阶段成本目标
    c1 = np.zeros(N_VAR, dtype=float)
    c1[_OFF_G:_OFF_G + T] = price

    # 变量边界
    lb = np.zeros(N_VAR, dtype=float)
    ub = np.full(N_VAR, np.inf, dtype=float)
    for t in range(T):
        ub[_idx_c(t)] = ebar
        ub[_idx_d(t)] = ebar
        ub[_idx_r(t)] = pv_e[t]
    lb[_OFF_S:_OFF_S + T + 1] = s_min
    ub[_OFF_S:_OFF_S + T + 1] = s_max
    bounds = list(zip(lb.tolist(), ub.tolist()))

    return A_eq, b_eq, c1, bounds


def _cost_cvec(price: np.ndarray) -> np.ndarray:
    """构造费用约束行的系数向量（作用于 G 块）。"""
    v = np.zeros(N_VAR, dtype=float)
    v[_OFF_G:_OFF_G + T] = np.asarray(price, dtype=float)
    return v


def _throughput_cvec() -> np.ndarray:
    """第二阶段吞吐目标系数向量（C + D）。"""
    v = np.zeros(N_VAR, dtype=float)
    v[_OFF_C:_OFF_C + T] = 1.0
    v[_OFF_D:_OFF_D + T] = 1.0
    return v


def _unpack(x: np.ndarray) -> Dict[str, np.ndarray]:
    return {
        "G": np.asarray(x[_OFF_G:_OFF_G + T], dtype=float),
        "C": np.asarray(x[_OFF_C:_OFF_C + T], dtype=float),
        "D": np.asarray(x[_OFF_D:_OFF_D + T], dtype=float),
        "R": np.asarray(x[_OFF_R:_OFF_R + T], dtype=float),
        "S": np.asarray(x[_OFF_S:_OFF_S + T + 1], dtype=float),
    }


def _linprog_solver_options() -> Dict:
    return {
        "presolve": True,
        "primal_feasibility_tolerance": 1e-9,
        "dual_feasibility_tolerance": 1e-9,
    }


def solve_two_stage_lp(
    price: np.ndarray,
    load_e: np.ndarray,
    pv_e: np.ndarray,
    eps_j: float,
    eta_c: float = ETA_C,
    eta_d: float = ETA_D,
    s0: float = S0,
    s_t: float = S_T,
    s_min: float = S_MIN,
    s_max: float = S_MAX,
    ebar: float = EBAR,
) -> Dict:
    """两阶段 LP 求解。

    Returns
    -------
    Dict
        包含 ``phase1`` / ``phase2`` 子字典、``x``、``J1_star``、``J_actual``、
        ``H`` 与解分量。若任一阶段非 optimal，则 ``status`` 非 ``optimal``。
    """
    price = np.asarray(price, dtype=float)
    load_e = np.asarray(load_e, dtype=float)
    pv_e = np.asarray(pv_e, dtype=float)
    A_eq, b_eq, c1, bounds = build_model(
        price, load_e, pv_e, eta_c, eta_d, s0, s_t, s_min, s_max, ebar
    )

    res1 = linprog(
        c1,
        A_eq=A_eq,
        b_eq=b_eq,
        bounds=bounds,
        method="highs",
        options=_linprog_solver_options(),
    )

    phase1 = {
        "status": _lp_status_str(res1.status),
        "status_code": int(res1.status),
        "success": bool(res1.success),
        "message": res1.message,
        "fun": None if res1.fun is None else float(res1.fun),
        "nit": int(res1.nit) if res1.nit is not None else None,
    }

    if not res1.success or res1.x is None:
        return {
            "status": "not_optimal",
            "phase1": phase1,
            "phase2": None,
            "x": None,
            "J1_star": None,
            "J_actual": None,
            "H": None,
            "components": None,
            "method": "lp",
        }

    j1_star = float(res1.fun)
    c2 = _throughput_cvec()
    A_ub = _cost_cvec(price).reshape(1, -1)
    b_ub = np.array([j1_star + eps_j])

    res2 = linprog(
        c2,
        A_ub=A_ub,
        b_ub=b_ub,
        A_eq=A_eq,
        b_eq=b_eq,
        bounds=bounds,
        method="highs",
        options=_linprog_solver_options(),
    )

    phase2 = {
        "status": _lp_status_str(res2.status),
        "status_code": int(res2.status),
        "success": bool(res2.success),
        "message": res2.message,
        "fun": None if res2.fun is None else float(res2.fun),
        "nit": int(res2.nit) if res2.nit is not None else None,
    }

    if not res2.success or res2.x is None:
        return {
            "status": "not_optimal",
            "phase1": phase1,
            "phase2": phase2,
            "x": None,
            "J1_star": j1_star,
            "J_actual": None,
            "H": None,
            "components": None,
            "method": "lp",
        }

    comp = _unpack(res2.x)
    j_actual = float(np.dot(price, comp["G"]))
    _lock = j1_star + eps_j
    if j_actual > _lock and (j_actual - _lock) <= 1e-9 * max(1.0, abs(j1_star)):
        # 二阶段费用约束在求解器可行容差内饱和，np.dot 重算产生 ~1ULP 上浮，钳到费用锁
        j_actual = _lock
    h = float(np.sum(comp["C"] + comp["D"]))
    return {
        "status": "optimal",
        "phase1": phase1,
        "phase2": phase2,
        "x": np.asarray(res2.x, dtype=float),
        "J1_star": j1_star,
        "J_actual": j_actual,
        "H": h,
        "components": comp,
        "method": "lp",
    }


def solve_two_stage_milp(
    price: np.ndarray,
    load_e: np.ndarray,
    pv_e: np.ndarray,
    eps_j: float,
    eta_c: float = ETA_C,
    eta_d: float = ETA_D,
    s0: float = S0,
    s_t: float = S_T,
    s_min: float = S_MIN,
    s_max: float = S_MAX,
    ebar: float = EBAR,
) -> Dict:
    """两阶段 MILP 兜底（HiGHS 内核）。

    在 LP 基础上引入二元变量 ``z_t`` 与互斥约束：
    ``C_t <= Ebar*z_t``、``D_t <= Ebar*(1-z_t)``。
    """
    price = np.asarray(price, dtype=float)
    load_e = np.asarray(load_e, dtype=float)
    pv_e = np.asarray(pv_e, dtype=float)

    # 变量顺序：[G, C, D, R, S, z]，z 共 T 个
    z_off = N_VAR
    n_var = N_VAR + T
    c1 = np.zeros(n_var, dtype=float)
    c1[_OFF_G:_OFF_G + T] = price
    c2 = np.zeros(n_var, dtype=float)
    c2[_OFF_C:_OFF_C + T] = 1.0
    c2[_OFF_D:_OFF_D + T] = 1.0

    integrality = np.zeros(n_var, dtype=np.uint8)
    integrality[z_off:z_off + T] = 1

    lb = np.zeros(n_var, dtype=float)
    ub = np.full(n_var, np.inf, dtype=float)
    for t in range(T):
        ub[_idx_c(t)] = ebar
        ub[_idx_d(t)] = ebar
        ub[_idx_r(t)] = pv_e[t]
        ub[z_off + t] = 1.0
    lb[_OFF_S:_OFF_S + T + 1] = s_min
    ub[_OFF_S:_OFF_S + T + 1] = s_max

    # 等式约束（同 LP）
    n_eq = 2 * T + 2
    A_eq = np.zeros((n_eq, n_var), dtype=float)
    b_eq = np.zeros(n_eq, dtype=float)
    for t in range(T):
        A_eq[t, _idx_g(t)] = 1.0
        A_eq[t, _idx_d(t)] = 1.0
        A_eq[t, _idx_c(t)] = -1.0
        A_eq[t, _idx_r(t)] = -1.0
        b_eq[t] = load_e[t] - pv_e[t]
    for t in range(T):
        row = T + t
        A_eq[row, _idx_s(t + 1)] = 1.0
        A_eq[row, _idx_s(t)] = -1.0
        A_eq[row, _idx_c(t)] = -eta_c
        A_eq[row, _idx_d(t)] = 1.0 / eta_d
        b_eq[row] = 0.0
    A_eq[2 * T, _idx_s(0)] = 1.0
    b_eq[2 * T] = s0
    A_eq[2 * T + 1, _idx_s(T)] = 1.0
    b_eq[2 * T + 1] = s_t

    # 不等式约束：互斥 + 费用锁定（第二阶段）
    n_mutex = 2 * T
    A_mutex = np.zeros((n_mutex, n_var), dtype=float)
    lb_mutex = np.full(n_mutex, -np.inf, dtype=float)
    ub_mutex = np.zeros(n_mutex, dtype=float)
    for t in range(T):
        # C_t - Ebar*z_t <= 0
        A_mutex[t, _idx_c(t)] = 1.0
        A_mutex[t, z_off + t] = -ebar
        # D_t + Ebar*z_t <= Ebar  =>  D_t + Ebar*z_t - Ebar <= 0
        A_mutex[T + t, _idx_d(t)] = 1.0
        A_mutex[T + t, z_off + t] = ebar
        ub_mutex[T + t] = ebar

    cost_row = np.zeros((1, n_var), dtype=float)
    cost_row[0, _OFF_G:_OFF_G + T] = price

    def _run(c, cost_ub):
        # 合并等式（能量平衡 / SOC 递推 / 初末 SOC）与不等式（互斥 + 费用锁定）
        A_all = np.vstack([A_eq, A_mutex, cost_row])
        lb_all = np.concatenate([b_eq, lb_mutex, np.array([-np.inf])])
        ub_all = np.concatenate([b_eq, ub_mutex, np.array([cost_ub])])
        constraints = LinearConstraint(A_all, lb_all, ub_all)
        return milp(
            c,
            integrality=integrality,
            bounds=Bounds(lb, ub),
            constraints=constraints,
            options={"mip_rel_gap": 0.0, "presolve": True},
        )

    # 第一阶段：无费用锁定，费用行上界取 +inf
    res1 = _run(c1, np.inf)
    status1 = int(res1.status)
    if not res1.success or res1.x is None:
        return {
            "status": "not_optimal",
            "phase1_status": status1,
            "phase1_message": res1.message,
            "J1_star": None,
            "J_actual": None,
            "method": "milp",
        }

    j1_star = float(res1.fun)
    res2 = _run(c2, j1_star + eps_j)
    status2 = int(res2.status)
    if not res2.success or res2.x is None:
        return {
            "status": "not_optimal",
            "phase1_status": status1,
            "phase2_status": status2,
            "phase2_message": res2.message,
            "J1_star": j1_star,
            "J_actual": None,
            "method": "milp",
        }

    comp = _unpack(res2.x[:N_VAR])
    j_actual = float(np.dot(price, comp["G"]))
    _lock = j1_star + eps_j
    if j_actual > _lock and (j_actual - _lock) <= 1e-9 * max(1.0, abs(j1_star)):
        j_actual = _lock
    h = float(np.sum(comp["C"] + comp["D"]))
    return {
        "status": "optimal",
        "phase1_status": status1,
        "phase2_status": status2,
        "phase1_message": res1.message,
        "phase2_message": res2.message,
        "mip_gap": float(res2.mip_gap) if res2.mip_gap is not None else None,
        "J1_star": j1_star,
        "J_actual": j_actual,
        "H": h,
        "components": comp,
        "method": "milp",
    }
