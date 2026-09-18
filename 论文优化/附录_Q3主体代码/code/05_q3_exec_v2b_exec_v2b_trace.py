def exec_v2b_trace(A, La_kW, Pa_kW, s0, C_plan=None, D_plan=None,
                   absorb_all: bool = True):
    """v2b 执行器主体（含逐段账本 ``recs``，供平衡/约束自查用）。

    Parameters
    ----------
    A : (T,) 已承诺购电量（kWh）；执行器**不改 A**（A 由计划层与滚动链决定）
    La_kW, Pa_kW : (T,) 结算用实际的负荷/光伏（kW，附件2）
    s0 : 当日区间前的实际 SOC（kWh）
    C_plan, D_plan : (T,) 计划层给出的充/放电计划（kWh）；None 视为 0
    absorb_all : True = v2b（富余把电池吸满）；False = v2a（只充到计划充电量）

    Returns
    -------
    (H, R_PV, R_G, S, Cx, Dx, recs)
        与 ``q3_solver.exec_E1`` 同序同义的前六项 + 逐段账本（每段记
        ``net/cp/dp/c/d/gap/H/R_PV/R_G/s_out/res``）。
    """
    A = np.asarray(A, dtype=float)
    La = np.asarray(La_kW, dtype=float)
    Pa = np.asarray(Pa_kW, dtype=float)
    cp_src = np.zeros(T) if C_plan is None else np.asarray(C_plan, dtype=float)
    dp_src = np.zeros(T) if D_plan is None else np.asarray(D_plan, dtype=float)

    S = np.zeros(T + 1)
    H = np.zeros(T)
    R_PV = np.zeros(T)
    R_G = np.zeros(T)
    Cx = np.zeros(T)
    Dx = np.zeros(T)
    recs: list = []
    s = float(s0)
    S[0] = s
    for t in range(T):
        # 1) 计划动作先过物理钳制，并取净额（同 E1：计划同充同放时保留净额）
        cp = min(float(cp_src[t]), EBAR, max(0.0, (SMAX - s) / ETA))
        dp = min(float(dp_src[t]), EBAR, max(0.0, ETA * (s - SMIN)))
        if cp > 0.0 and dp > 0.0:
            if cp >= dp:
                cp, dp = cp - dp, 0.0
            else:
                cp, dp = 0.0, dp - cp
        room = max(0.0, min(EBAR, (SMAX - s) / ETA))
        drain = max(0.0, min(EBAR, ETA * (s - SMIN)))
        # 2) 实测净量（**不含**计划动作）：>0 缺口、<0 富余
        pv_e = float(Pa[t]) * DT
        net = float(La[t]) * DT - pv_e - float(A[t])
        if net < 0.0:                      # ① 实测富余
            surplus = -net
            d = 0.0                        # ★ 回退计划放电：能量留在电池里，不白放
            c = min(room, surplus) if absorb_all else min(cp, room, surplus)
        else:                              # ② 实测缺口
            c = 0.0                        # ★ 不执行"要靠 5 倍价紧急电才完得成"的充电
            d = min(dp, drain, net)
        # 3) H/R 由实际缺口反解（唯一记账入口 ⇒ 逐段平衡是恒等式）
        gap = net + c - d
        H[t] = max(gap, 0.0)
        R = max(-gap, 0.0)
        R_PV[t] = min(pv_e, R)             # 先弃光伏
        R_G[t] = R - R_PV[t]               # 再弃已购电（恒 ≤ A，见模块 docstring）
        Cx[t], Dx[t] = c, d
        s = s + ETA * c - d / ETA
        S[t + 1] = s
        recs.append({"t": t, "net": net, "cp": cp, "dp": dp, "room": room,
                     "drain": drain, "c": c, "d": d, "gap": gap, "H": H[t],
                     "R_PV": R_PV[t], "R_G": R_G[t], "s_out": s,
                     "res": float(A[t]) + pv_e + d + H[t]
                            - (float(La[t]) * DT + c + R_PV[t] + R_G[t])})
    return H, R_PV, R_G, S, Cx, Dx, recs
