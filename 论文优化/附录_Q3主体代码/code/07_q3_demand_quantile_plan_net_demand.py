def plan_net_demand(point_N: np.ndarray, L: np.ndarray, P: np.ndarray, d: int,
                    tau: int, demand: str = "point", q: float = DEFAULT_Q,
                    dt: float = DT, fc: dict | None = None, days: list | None = None,
                    convention: str = "slot_end",
                    q_block: str = "segment") -> np.ndarray:
    """生成计划层 LP 使用的净需求输入。

    ``demand="point"`` 时返回 ``point_N`` 的副本（逐位不变）；
    ``demand="quantile"`` 时只替换 ``t >= 6 * tau`` 区间：

        ``N_hat[t] = np.quantile(scenario[:, t], q)``。

    ``demand="quantile_v3"`` 时保留 ``point_N`` 的 τ 版预报主体，只在
    ``t >= 6 * tau`` 上叠加 ``causal_residual_quantile`` 的 δ。

    已过去区间（``t < 6 * tau``）保持 ``point_N``，因为对应 LP 段已被冻结，
    求解器会忽略这些位置。
    """
    if demand not in DEMAND_CHOICES:
        raise ValueError(f"未知 demand={demand!r}，只支持 {DEMAND_CHOICES}")
    N = np.array(point_N, dtype=float, copy=True)
    if demand == "point":
        return N

    qf = float(q)
    if not (0.0 <= qf <= 1.0):
        raise ValueError(f"q 必须在 [0,1]，实得 {q}")
    c0 = int(tau) * 6
    if demand == "quantile":
        scen = scenario_net_demand(L, P, d, tau, dt=dt)
        N[c0:] = np.quantile(scen[:, c0:], qf, axis=0)
    else:
        if fc is None or days is None:
            raise ValueError("demand='quantile_v3' 需要同时传入 fc 与 days")
        delta = causal_residual_quantile(
            L, P, fc, days, d, tau, q=qf, q_block=q_block,
            convention=convention, dt=dt,
        )
        N[c0:] = N[c0:] + delta[c0:]
    return N
