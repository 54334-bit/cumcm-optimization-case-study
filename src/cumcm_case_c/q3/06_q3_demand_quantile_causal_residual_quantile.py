def causal_residual_quantile(L: np.ndarray, P: np.ndarray, fc: dict, days: list,
                             d: int, tau: int, q: float = DEFAULT_Q,
                             q_block: str = "segment",
                             convention: str = "slot_end",
                             dt: float = DT) -> np.ndarray:
    """返回 τ 版预报的因果残差分位修正 ``delta_tau(d, ·)``（kWh，144 段）。

    残差定义（逐段，全部为电量 kWh）::

        r[d', t] = (L[d', t] - P[d', t]) * dt
                   - (L[d', t] - PV_hat[tau, d', t]) * dt

    窗口 ``d' ∈ [d - 28, d - 1]``，同 τ、同插值口径。``q_block="segment"``
    时每段独立取 ``Q_q``；``q_block="block"`` 时按 6 小时块汇总块内所有段后
    取一个标量。``t < 6*tau`` 的修正保持 0（主线不会使用这些已过去段）。
    """
    if q_block not in Q_BLOCK_CHOICES:
        raise ValueError(f"未知 q_block={q_block!r}，只支持 {list(Q_BLOCK_CHOICES)}")
    qf = float(q)
    if not (0.0 <= qf <= 1.0):
        raise ValueError(f"q 必须在 [0,1]，实得 {q}")
    d, tau = int(d), int(tau)
    if d < 1:
        raise ValueError(f"v3 残差窗要求 d>=1，实得 d={d}")
    # 残差依赖具体的 P/L 实现，缓存键带上数组身份；生产路径固定数组，
    # 前视自检会传入修改副本，必须避免误命中旧窗口。
    key = (id(L), id(P), id(fc), id(days), d, tau, qf,
           str(q_block), str(convention))
    cached = _DELTA_CACHE.get(key)
    if cached is not None:
        return cached

    stack, c0 = _residual_window(L, P, fc, days, d, tau,
                                 convention=convention, dt=dt)
    delta = _delta_from_window(stack, c0, qf, q_block)
    _DELTA_CACHE[key] = delta
    return delta


