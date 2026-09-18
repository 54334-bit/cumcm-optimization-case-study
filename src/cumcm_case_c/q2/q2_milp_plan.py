# -*- coding: utf-8 -*-
"""计划层求解器（独立于 q2_lp.py）。三种口径：
  lp   : 线性 recourse（允许 e 与 C 同段）
  milp : 全量二元互斥 e_t ≤ M z_t, C_t ≤ M(1−z_t)（每天 1008 个二元变量，慢）
  lazy : 惰性割——先在无割 LP 上解，找出真正 e>0 且 C>0 的 (k,t)，只为这些位置引入二元互斥，重解；
         反复直到解不再违反互斥。此时该解对"全量互斥 MILP"是**精确最优**（LP 松弛 ≤ MILP ≤ 该可行解）。
返回 (G, obj, info)。
"""
import sys
sys.path.append("D:\\CMUCU\\rag\\.deps")
import numpy as np
from scipy.sparse import csr_matrix
from scipy.optimize import linprog, milp, LinearConstraint, Bounds

T = 144; DT = 1/6; EBAR = 5000*DT; SMIN, SMAX, ETA = 1200.0, 10800.0, 0.9
TOL = 1e-7


def _build(Le, Pe, price, s0, lam, cut_pairs):
    """cut_pairs: list of (k, t) —— 需要施加互斥的位置（每个占 1 个二元变量）。"""
    K, Tt = Le.shape
    nz = len(cut_pairs)
    nk = 5*Tt + 1                      # C,D,R_PV,e = 4T ; S = T+1
    n = Tt + K*nk + nz
    c = np.zeros(n); c[0:Tt] = price
    re_, ce_, ve_, be = [], [], [], []
    ru, cu, vu, bu = [], [], [], []
    ri = ai = 0
    Me = float(max(1400.0, np.max(Le)*1.05)); Mc = float(EBAR)
    for k in range(K):
        off = Tt + k*nk
        oC, oD, oP, oE, oS = off, off+Tt, off+2*Tt, off+3*Tt, off+4*Tt
        for t in range(Tt):
            re_ += [ri]*5; ce_ += [t, oC+t, oD+t, oP+t, oE+t]; ve_ += [1.0, -1.0, 1.0, -1.0, 1.0]
            be.append(Le[k, t] - Pe[k, t]); ri += 1
        for t in range(Tt):
            re_ += [ri]*4; ce_ += [oS+t+1, oS+t, oC+t, oD+t]; ve_ += [1.0, -1.0, -ETA, 1/ETA]
            be.append(0.0); ri += 1
        re_ += [ri]; ce_ += [oS]; ve_ += [1.0]; be.append(s0); ri += 1
        c[oE:oE+Tt] = 5*price/K
        c[oS+Tt] = -lam/K
    for j, (k, t) in enumerate(cut_pairs):
        off = Tt + k*nk
        oC, oE = off, off+3*Tt
        zc = Tt + K*nk + j
        Me_kt = float(max(1.0, Le[k, t]))        # 逐时段紧 big-M：e 不可能超过该时段负载电量
        ru += [ai, ai]; cu += [oE+t, zc]; vu += [1.0, -Me_kt]; bu.append(0.0); ai += 1
        ru += [ai, ai]; cu += [oC+t, zc]; vu += [1.0, Mc]; bu.append(Mc); ai += 1
    A_eq = csr_matrix((np.asarray(ve_), (np.asarray(re_), np.asarray(ce_))), shape=(ri, n))
    A_ub = csr_matrix((np.asarray(vu), (np.asarray(ru), np.asarray(cu))), shape=(ai, n)) if ai else None
    bd = [(0.0, None)]*Tt; integ = np.zeros(n)
    for k in range(K):
        off = Tt + k*nk
        bd += ([(0.0, EBAR)]*Tt + [(0.0, EBAR)]*Tt
               + [(0.0, float(Pe[k, t])) for t in range(Tt)]
               + [(0.0, None)]*Tt + [(SMIN, SMAX)]*(Tt+1))
    bd += [(0.0, 1.0)]*nz
    if nz: integ[Tt + K*nk:] = 1
    return c, A_eq, np.asarray(be), A_ub, np.asarray(bu), bd, integ, nk, nz


def _solve_once(Le, Pe, price, s0, lam, cut_pairs, time_limit=180):
    c, Aeq, beq, Aub, bub, bd, integ, nk, nz = _build(Le, Pe, price, s0, lam, cut_pairs)
    if nz == 0:
        r = linprog(c, A_eq=Aeq, b_eq=beq, A_ub=Aub, b_ub=bub, bounds=bd, method="highs")
    else:
        cons = [LinearConstraint(Aeq, beq, beq)]
        if Aub is not None: cons.append(LinearConstraint(Aub, -np.inf, bub))
        r = milp(c, constraints=cons, integrality=integ,
                 bounds=Bounds([-np.inf if b[0] is None else b[0] for b in bd],
                               [np.inf if b[1] is None else b[1] for b in bd]),
                 options={"time_limit": time_limit, "mip_rel_gap": 1e-7})
    if not r.success and r.x is None:
        return None, None, nk, dict(status=int(r.status), msg=str(r.message))
    return r.x, float(r.fun), nk, dict(status=int(r.status), msgs=str(r.message)[:80],
                                       success=bool(r.success))


def _extract(x, K, Tt, nk):
    G = x[0:Tt]; Es = np.zeros(Tt); Cs = np.zeros(Tt)
    both = []
    for k in range(K):
        off = Tt + k*nk
        e = x[off+3*Tt:off+4*Tt]; C = x[off:off+Tt]
        Es += e/K; Cs += C/K
        idx = np.where((e > TOL) & (C > TOL))[0]
        both += [(k, int(t)) for t in idx]
    return G, Es, Cs, both


def solve(Le, Pe, price, s0, lam=0.4720, mode="lazy", max_iter=40):
    K, Tt = Le.shape
    if mode == "milp":
        cuts = [(k, t) for k in range(K) for t in range(Tt)]
        x, obj, nk, info = _solve_once(Le, Pe, price, s0, lam, cuts, time_limit=300)
        if x is None: return None, None, dict(mode="milp", fail=True, **info)
        G, Es, Cs, both = _extract(x, K, Tt, nk)
        return G, obj, dict(mode="milp", cuts=len(cuts), n_viol=len(both), **info)
    cuts = []
    for it in range(max_iter):
        x, obj, nk, info = _solve_once(Le, Pe, price, s0, lam, cuts)
        if x is None:
            return None, None, dict(iters=it, cuts=len(cuts), fail=True, **info)
        G, Es, Cs, both = _extract(x, K, Tt, nk)
        if mode == "lp":
            return G, obj, dict(iters=1, cuts=0, n_viol=len(both), status=0)
        if not both:
            return G, obj, dict(iters=it+1, cuts=len(cuts), n_viol=0, status=0)
        # 只保留尚未加入的割
        new = [p for p in both if p not in set(cuts)]
        cuts += new
    return None, None, dict(iters=max_iter, cuts=len(cuts), not_converged=True)
