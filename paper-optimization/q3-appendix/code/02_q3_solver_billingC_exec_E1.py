def exec_E1(A: np.ndarray, La_kW: np.ndarray, Pa_kW: np.ndarray, s0: float,
            C_plan: np.ndarray | None = None, D_plan: np.ndarray | None = None):
    """因果执行器 E1：**执行计划层的充放电计划**，再按实测处理缺口/富余。

    与 Q2 的 E1 同优先级，但补上"计划动作要被执行"这一层（此前版本漏了它，导致 SOC 崩）：
      1. 按计划充放电，但受当前 SOC 的物理可行性钳制
           C_exec = min(C_plan, EBAR, (SMAX − s)/η)
           D_exec = min(D_plan, EBAR, η·(s − SMIN))
      2. 之后看实测缺口 gap = L·dt − PV·dt − A + C_exec − D_exec
           gap > 0 ⇒ H = gap（紧急购电）
           gap ≤ 0 ⇒ 富余先弃光伏 R_PV，再弃计划购电 R_G
      3. SOC 按实际动作递推

    Parameters
    ----------
    A : 已承诺购电量（kWh）
    C_plan, D_plan : 计划层给出的充/放电计划（kWh）；None 视为 0
    """
    dt = 1.0 / 6.0
    if C_plan is None:
        C_plan = np.zeros(T)
    if D_plan is None:
        D_plan = np.zeros(T)
    S = np.zeros(T + 1)
    H = np.zeros(T)
    R_PV = np.zeros(T)
    R_G = np.zeros(T)
    Cx = np.zeros(T)
    Dx = np.zeros(T)
    s = float(s0)
    S[0] = s
    for t in range(T):
        # 1) 执行计划动作（物理钳制）
        c = min(float(C_plan[t]), EBAR, max(0.0, (SMAX - s) / ETA))
        d = min(float(D_plan[t]), EBAR, max(0.0, ETA * (s - SMIN)))
        if c > 0 and d > 0:                      # 计划同充同放时保留净额
            if c >= d:
                c, d = c - d, 0.0
            else:
                c, d = 0.0, d - c
        Cx[t], Dx[t] = c, d
        # 2) 实测缺口/富余
        gap = La_kW[t] * dt - Pa_kW[t] * dt - A[t] + c - d
        if gap > 0:
            H[t] = gap
        else:
            rest = -gap
            R_PV[t] = min(Pa_kW[t] * dt, rest)
            R_G[t] = rest - R_PV[t]
        # 3) SOC
        s = s + ETA * c - d / ETA
        S[t + 1] = s
    return H, R_PV, R_G, S, Cx, Dx
