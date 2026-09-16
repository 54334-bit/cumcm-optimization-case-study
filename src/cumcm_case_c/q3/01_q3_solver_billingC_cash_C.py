def cash_C(A: np.ndarray, G0: np.ndarray, price: np.ndarray, H: np.ndarray) -> dict:
    """读法 C 报账：`cash = Σ p·min(G⁰,A) + Σ[0.5p·(G⁰−A)⁺ + 1.5p·(A−G⁰)⁺] + Σ 5p·H`。

    与读法 A 的唯一区别是计划费基准：A 用 take-or-pay 的 `p·G⁰`，C 用 `p·min(G⁰,A)`。
    调整费（下调 0.5p / 上调 1.5p）与紧急购电（5p）两读法一致。
    返回键名与 `cash_cost` 相同，便于并排对照。

    Parameters
    ----------
    A, G0, price, H : (T,) 最终执行购电量 / 0:00 计划购电量 / 电价 / 紧急购电量
    """
    down = np.maximum(G0 - A, 0.0)
    up = np.maximum(A - G0, 0.0)
    j_plan = float((price * np.minimum(G0, A)).sum())
    j_adj = float((0.5 * price * down + 1.5 * price * up).sum())
    j_emg = float((5.0 * price * H).sum())
    return {"J_plan": j_plan, "J_adj": j_adj, "J_emg": j_emg,
            "J_cash": j_plan + j_adj + j_emg}


