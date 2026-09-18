def run_day(L, P, price, fc, days, d, executor, *, billing="C", demand="point",
            q=DEFAULT_Q, q_block="segment", margin=0.0, s_init=S0,
            epochs=EPOCHS, lam=LAM_T, convention="slot_end"):
    """跑一天的滚动决策：θ=0 承诺 ``G⁰`` → 6/12/18 重解剩余段 → 结算执行。

    与 ``q3_main_v2.run_day_v2`` 的**唯一差别**是执行器可换（``executor`` 入参）：
    计划层 LP、光伏重建、裕度语义、落定规则、报账函数全部逐字沿用主线；
    ``executor=EXECUTORS["E1"]`` 时结果应与 ``run_day_v2`` **逐位一致**
    （由 ``selfcheck_equiv`` 断言）。

    ``margin`` 是标量覆盖（O1 探路固定 ``0.0``：与基线同裕度），不走裕度表。

    Returns
    -------
    dict：``ok=False`` 时含 ``reason``；``ok=True`` 时含逐段数组
    （``G0/A/C/D/C_plan/D_plan/S/H/R_PV/R_G``）、费用键（``J_plan/J_adj/J_emg/
    J_cash``）与自检量（``balance_max_res``/``plan_max_res``/``chi_plan``/
    ``chi_exec``/``soc_min``/``soc_max``/``RG_viol_max``/``HR_max``）。
    """
    if billing not in SOLVER:
        raise ValueError(f"未知读法 {billing!r}，只支持 {sorted(SOLVER)}")
    if demand not in DEMAND_CHOICES:
        raise ValueError(f"未知 demand={demand!r}，只支持 {DEMAND_CHOICES}")
    if q_block not in Q_BLOCK_CHOICES:
        raise ValueError(f"未知 q_block={q_block!r}，只支持 {Q_BLOCK_CHOICES}")
    solve_epoch = SOLVER[billing]
    epochs = tuple(t for t in EPOCHS if t in set(epochs))
    if 0 not in epochs:
        return {"ok": False, "d": int(d), "reason": "epochs 必须含 0（否则无 G⁰ 承诺）"}

    day, prev = days[d], days[d - 1]
    Ld, Pd = L[d], P[d]

    # ---- θ=0：负荷已知 + 0:00 版光伏（带裕度）→ 承诺全天 G⁰ ----
    L0 = Ld.copy()
    pv0, m0, miss0 = _pv_for_epoch(fc, day, prev, 0, margin, convention)
    pv0_e = (1.0 - m0) * pv0
    N0 = plan_net_demand((L0 - pv0_e) * DT, L, P, d, 0, demand=demand, q=q,
                         fc=fc, days=days, convention=convention, q_block=q_block)
    r = solve_epoch(N0, price, s_init, None, lam, 0, PV_e=pv0_e * DT)
    if not r["ok"]:
        return {"ok": False, "d": int(d), "reason": f"θ=0 LP 失败：{r.get('msg')}"}
    G0 = r["A"].copy()
    A, C, D = G0.copy(), r["C"].copy(), r["D"].copy()
    plan_res = float(np.max(np.abs(r["A"] + r["D"] - r["R"] - N0 - r["C"])))
    n_pv_missing = miss0

    # ---- θ>0：沿已实现动作链取 SOC → 重解剩余段 → 本块落定、未落定段改用本次解 ----
    for tau in epochs:
        if tau == 0:
            continue
        c0 = tau * 6
        _, _, _, S_tmp, _, _ = executor(A, Ld, Pd, s_init, C, D)
        s_cur = float(S_tmp[c0])
        Lh = Ld.copy()                       # 负荷已知：无预测、无残差修正
        pv, m, miss = _pv_for_epoch(fc, day, prev, tau, margin, convention)
        pv_e = (1.0 - m) * pv
        Nt = plan_net_demand((Lh - pv_e) * DT, L, P, d, tau, demand=demand, q=q,
                             fc=fc, days=days, convention=convention,
                             q_block=q_block)
        rr = solve_epoch(Nt, price, s_cur, G0, lam, c0, PV_e=pv_e * DT)
        if not rr["ok"]:
            return {"ok": False, "d": int(d), "reason": f"θ={tau} LP 失败：{rr.get('msg')}"}
        n_pv_missing += miss
        plan_res = max(plan_res, float(np.max(np.abs(
            rr["A"][c0:] + rr["D"][c0:] - rr["R"][c0:] - Nt[c0:] - rr["C"][c0:]))))
        A[c0:], C[c0:], D[c0:] = rr["A"][c0:], rr["C"][c0:], rr["D"][c0:]

    # ---- 结算：附件2 实际负荷/光伏；执行计划层的充放电计划 ----
    H, R_PV, R_G, S, Cx, Dx = executor(A, Ld, Pd, s_init, C, D)
    fee = BILLING[billing](A, G0, price, H)

    # 逐段能量平衡残差（执行层）：A − Cx + Dx + H − R_PV − R_G = (L − P)·dt
    balance_res = float(np.max(np.abs(A - Cx + Dx + H - R_PV - R_G - (Ld - Pd) * DT)))
    S_hi = S[1:]
    return {
        "ok": True,
        "d": int(d),
        "date": day,
        "billing": billing,
        "demand": demand,
        "q": (None if demand == "point" else float(q)),
        "q_block": (q_block if demand == "quantile_v3" else None),
        "margin": float(margin),
        "G0": G0, "A": A, "C": Cx, "D": Dx, "C_plan": C, "D_plan": D,
        "S": S, "H": H, "R_PV": R_PV, "R_G": R_G,
        "S_end": float(S[-1]),
        "S_first": float(S[0]),
        "soc_min": float(S_hi.min()),
        "soc_max": float(S_hi.max()),
        "s_init": float(s_init),
        "balance_max_res": balance_res,
        "plan_max_res": plan_res,
        "chi_plan": float(np.max(np.minimum(C, D))),      # 计划层同充同放（净额前）
        "chi_exec": float(np.max(np.minimum(Cx, Dx))),    # 执行层同充同放（应为 0）
        "RG_viol_max": float(np.max(R_G - A)),            # 旧线 §4.1 的 R_G ≤ A 断言
        "HR_max": float(np.max(H * (R_PV + R_G))),        # H·R = 0 断言
        "n_pv_missing": int(n_pv_missing),
        "QH": float(H.sum()),
        "QG0": float(G0.sum()),
        "QA": float(A.sum()),                              # ΣG：总购电量
        "QC": float(Cx.sum()),                             # Σ执行充电量
        "QD": float(Dx.sum()),                             # Σ执行放电量
        "QL": float((Ld * DT).sum()),                      # Σ实际负荷电量
        "QPV": float((Pd * DT).sum()),                     # Σ实际光伏电量
        "QR_PV": float(R_PV.sum()),
        "QR_G": float(R_G.sum()),
        "QGm": float(np.maximum(G0 - A, 0.0).sum()),       # Σdown（相对 G⁰ 的下调量）
        "QGp": float(np.maximum(A - G0, 0.0).sum()),       # Σup（相对 G⁰ 的上调量）
        **fee,
    }
