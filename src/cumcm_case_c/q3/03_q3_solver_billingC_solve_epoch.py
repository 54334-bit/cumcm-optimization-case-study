def solve_epoch(N: np.ndarray, price: np.ndarray, s_init: float, G0: np.ndarray | None,
                lam: float, c0: int, PV_e: np.ndarray | None = None) -> dict:
    """解一个决策时刻的 LP。

    Parameters
    ----------
    N : (T,) 净负荷电量（kWh）= (负荷 − 光伏)·dt，未观测区间由调用方按规则填好；
        已观测区间（t < c0）的值会被忽略（那里 A 已冻结）。
    price : (T,) 元/kWh
    s_init : 该时刻区间前的实际 SOC（kWh）
    G0 : (T,) 已承诺的 0:00 计划购电量；θ=0 时传 None
    lam : 终端边际价值（元/kWh）
    c0 : 该时刻对应的起始区间索引（0/36/72/108）
    PV_e : (T,) 该时刻可用预报的光伏**电量**（kWh）= PV_kW·dt；用于给弃光 R 设上界
           （R_t ≤ PV_e_t）。缺省视为 0（即该段不可弃光）。

    Returns
    -------
    dict(A, C, D, S, obj, status)
        A/C/D 长度 T（t<c0 处为 0，调用方自行拼接）；S 长度 T+1，S[0]=s_init。
    """
    Tn = T
    adj = G0 is not None                    # θ>0 才有调整项
    # 变量块（按序，唯一定义在 block_layout）：
    #   A(T) [ , Gm(T) , Gp(T) ] , C(T) , D(T) , R(T) , S(T+1)
    off = block_layout(adj, Tn)
    oA, oC, oD, oR, oS = off["A"], off["C"], off["D"], off["R"], off["S"]
    oGm, oGp = off.get("Gm"), off.get("Gp")
    n = oS + Tn + 1

    free = np.zeros(Tn, dtype=bool)
    free[c0:] = True

    c = np.zeros(n)
    c[oA:oA + Tn] = price
    c[oS + Tn] = -lam
    if adj:
        # ★ 与 q3_solver.py 的唯一数值差异：下调罚系数 1.5p → 0.5p（读法 C）
        c[oGm:oGm + Tn] = 0.5 * price
        c[oGp:oGp + Tn] = 0.5 * price

    rows, rhs = [], []
    for t in range(Tn):
        if t < c0:
            continue          # 已过去区间：流量已实现，只冻结 A，不进平衡/递推约束
        # 平衡：A + D = N + C + R，即 A + D − C − R = N
        #   （R 是弃光，落在需求侧；Gm/Gp 不出现，它们只进 A 的分解式）
        r = np.zeros(n)
        r[oA + t] = 1.0
        r[oD + t] = 1.0
        r[oR + t] = -1.0
        r[oC + t] = -1.0
        rows.append(r)
        rhs.append(N[t])
        # SOC 递推
        r = np.zeros(n)
        r[oS + t + 1] = 1.0
        r[oS + t] = -1.0
        r[oC + t] = -ETA
        r[oD + t] = 1.0 / ETA
        rows.append(r)
        rhs.append(0.0)
        if adj:
            # 楔形链接：A + Gm − Gp = G⁰
            #   其中 Gm = (G⁰−A)⁺（下调量，读法 C 系数 0.5p）、Gp = (A−G⁰)⁺（系数 0.5p）。
            #   ⚠️ 符号方向写反会让 LP 目标偏离报账现金（实测全年 A3 差 76.7 万元），
            #      这是监工与公式审计各自独立抓到的同一处 bug；改动前务必先过
            #      `q3_audit_s1_check.py` 与 `q3_smoke.py` 的 C1 golden test。
            r = np.zeros(n)
            r[oA + t] = 1.0
            r[oGm + t] = 1.0
            r[oGp + t] = -1.0
            rows.append(r)
            rhs.append(G0[t])
    # 状态链锚定：
    #   递推 S_t = S_{t-1} + ηC_t − D_t/η 只对 t ≥ c0 施加（过去段流量已实现），
    #   因此 t = c0 的递推会引用 S[c0−1]。为让链头闭合，统一锚定 **S[c0] = s_init**，
    #   并把 S[c0] 的界同时钉死（避免界与等式在浮点边界上打架）。
    r = np.zeros(n)
    r[oS + c0] = 1.0
    rows.append(r)
    rhs.append(s_init)
    Aeq = np.array(rows)
    beq = np.array(rhs)

    bd = []
    for t in range(Tn):
        if free[t]:
            # 自由区间：A 不设上界 —— 计划量 G⁰ 是**计费基准**，不是物理上限；
            # A 与 G⁰ 的差由调整费（Gm/Gp）承接。
            bd.append((0.0, None))
        else:
            v = float(G0[t]) if adj else 0.0
            bd.append((v, v))              # 已过去区间：A 固定为已承诺值
    if adj:
        bd += [(0.0, None)] * Tn           # Gm
        bd += [(0.0, None)] * Tn           # Gp
    for t in range(Tn):
        w = EBAR if free[t] else 0.0
        bd.append((0.0, w))                # C
    for t in range(Tn):
        w = EBAR if free[t] else 0.0
        bd.append((0.0, w))                # D
    # R = 弃光（成本 0），**必须**有上界 PV_e_t，否则求解器会用"无限丢弃"绕开所有约束
    if PV_e is None:
        pv_e = np.zeros(Tn)
    else:
        pv_e = np.asarray(PV_e, dtype=float).copy()
        pv_e[~np.isfinite(pv_e)] = 0.0
    for t in range(Tn):
        bd.append((0.0, pv_e[t] if free[t] else 0.0))
    bd.append((s_init if c0 == 0 else None, s_init if c0 == 0 else None))   # S[0]
    for t in range(1, Tn + 1):
        if c0 > 0 and t < c0:
            bd.append((None, None))        # t<c0 的节点不在链上，界自由
        elif c0 > 0 and t == c0:
            bd.append((s_init, s_init))    # 链头：锚定实际 SOC
        else:
            bd.append((SMIN, SMAX))
    # 断言式自检：变量块偏移 / bd 分块 / bd 语义三者必须严格一致
    check_layout(bd, adj, Tn, c0=c0, G0=G0, pv_e=pv_e, s_init=s_init)

    res = linprog(c, A_eq=Aeq, b_eq=beq, bounds=bd, method="highs", options=_OPTS)
    if not res.success:
        return {"status": int(res.status), "ok": False, "msg": res.message}
    x = res.x
    return {
        "ok": True,
        "status": int(res.status),
        "A": x[oA:oA + Tn].copy(),
        "C": x[oC:oC + Tn].copy(),
        "D": x[oD:oD + Tn].copy(),
        "R": x[oR:oR + Tn].copy(),
        "S": x[oS:oS + Tn + 1].copy(),
        "obj": float(res.fun),
    }


