"""Q2 建模方案 v2 微型实验（对话 5）。

验证范围：
  1) 物理：计划层/执行层能量平衡、SOC 递推、互斥、跨日连续、首日 6000
  2) 经济：J 恒等式、W_grid、加储能不变差、报童 q0.8、信息泄漏扰动、残值锚点
  3) 终端口径对照：残值 vs 自由 vs 周期
  4) λ 敏感性（复用附录 A 结果，本脚本只重算主线与对照）
输出：D:\\CMUCU\\5对话\\output\\q2_v2_micro.json
只读输入，不写任何他人目录。
"""
from __future__ import annotations
import json, csv, time
import numpy as np
from scipy.optimize import linprog

LOAD = r"D:\CMUCU\B对话\clean\attachment2_load.csv"
PV   = r"D:\CMUCU\B对话\clean\attachment2_pv.csv"
PRC  = r"D:\CMUCU\B对话\clean\q1_clean.csv"
OUT  = r"D:\CMUCU\5对话\output\q2_v2_micro.json"

T = 144; DT = 1/6; EBAR = 5000*DT; SMIN, SMAX, ETA = 1200.0, 10800.0, 0.9
S0 = 6000.0; K_DEF = 7; LAM = 0.4706
PAPER_DATES = {"2025-03-20": 78, "2025-06-21": 171, "2025-09-23": 265, "2025-12-21": 354}
FIRST = 31   # 2025-02-01
PRICE = None  # 由 load_all() 设为模块级电价（144,）


def load_all():
    L = np.loadtxt(LOAD, delimiter=",", skiprows=1, usecols=range(1, 145))
    P = np.loadtxt(PV, delimiter=",", skiprows=1, usecols=range(1, 145))
    global PRICE
    price = np.array([float(r["price_元_kWh"]) for r in
                      csv.DictReader(open(PRC, encoding="utf-8-sig"))])
    PRICE = price
    return L, P, price


def plan_layer(L, P, d, s0, lam=LAM, K=K_DEF, terminal="value", no_storage=False, Lmax=None):
    """0:00 日前计划层：两阶段随机 LP，返回 (G_plan, diag)。

    变量块（每情景 k，偏移 off = T + k*nk，nk = 6*T+1）：
      块0 off+0*T : C_k     充电量     平衡式系数 -1
      块1 off+1*T : D_k     放电量     平衡式系数 +1
      块2 off+2*T : R_PV_k  弃光伏     平衡式系数 -1
      块3 off+3*T : R_G_k   弃计划购电 平衡式系数 +1
      块4 off+4*T : e_k     紧急购电   平衡式系数 +1
      块5 off+5*T : S_k[0..T]           共 T+1 个
    平衡（全部 kWh）：G_plan + PV*dt + D + e = L*dt + C + R_PV + R_G
    语义约束：0 <= R_G_k[t] <= G_plan[t]
    """
    ks = list(range(max(0, d-K), d))
    Le = (Lmax if Lmax is not None else L)[ks]*DT
    Pe = P[ks]*DT
    Kk = len(ks)
    nk = 6*T + 1
    n = T + Kk*nk
    c = np.zeros(n); c[0:T] = PRICE if PRICE is not None else price
    A = []; b = []; Aub = []; bub = []
    for k in range(Kk):
        off = T + k*nk
        for t in range(T):
            r = np.zeros(n)
            r[t] = 1
            r[off+0*T+t] = -1; r[off+1*T+t] = 1; r[off+2*T+t] = -1
            r[off+3*T+t] = -1; r[off+4*T+t] = 1
            A.append(r); b.append(Le[k][t]-Pe[k][t])
            q = np.zeros(n); q[off+3*T+t] = 1; q[t] = -1
            Aub.append(q); bub.append(0.0)          # R_G_k[t] <= G_plan[t]
        for t in range(T):
            r = np.zeros(n)
            r[off+5*T+t+1] = 1; r[off+5*T+t] = -1; r[off+0*T+t] = -ETA; r[off+1*T+t] = 1/ETA
            A.append(r); b.append(0.0)
        r = np.zeros(n); r[off+5*T] = 1; A.append(r); b.append(s0)
        if terminal == "cyclic":
            r = np.zeros(n); r[off+5*T+T] = 1; A.append(r); b.append(s0)
        c[off+4*T:off+5*T] = 5*PRICE/Kk
        if terminal == "value" and lam:
            c[off+5*T+T] = -lam/Kk
    bd = [(0, None)]*T
    for k in range(Kk):
        w = EBAR if not no_storage else 0.0
        bd += [(0, w)]*T + [(0, w)]*T + [(0, Pe[k][t]) for t in range(T)] \
              + [(0, None)]*T + [(0, None)]*T + [(SMIN, SMAX)]*(T+1)
    res = linprog(c, A_eq=np.array(A), b_eq=np.array(b), A_ub=np.array(Aub), b_ub=np.array(bub),
                  bounds=bd, method="highs")
    if not res.success:
        return None, {"success": False, "status": int(res.status), "message": res.message}
    x = res.x
    Ck = np.zeros(T); Dk = np.zeros(T); RGk = np.zeros(T)
    for k in range(Kk):
        off = T + k*nk
        Ck += x[off+0*T:off+1*T]/Kk; Dk += x[off+1*T:off+2*T]/Kk
        RGk += x[off+3*T:off+4*T]/Kk
    return x[0:T], {"success": True, "J_plan_obj": float(res.fun), "C_plan_mean": Ck,
                    "D_plan_mean": Dk, "R_G_plan_mean": RGk}

def exec_E1(G, La, Pa, s0):
    """receive-and-store 在线执行器（全额接收 G_plan）。"""
    S = s0; H = np.zeros(T); R_PV = np.zeros(T); R_G = np.zeros(T)
    C_exec = np.zeros(T); D_exec = np.zeros(T)
    for t in range(T):
        gap = La[t] - Pa[t] - G[t]
        if gap > 1e-12:
            dd = min(EBAR, ETA*(S-SMIN), gap)
            if dd < 0: dd = 0.0
            S -= dd/ETA; H[t] = gap - dd; D_exec[t] = dd
        else:
            room = min(EBAR, (SMAX-S)/ETA, -gap)
            room = max(room, 0.0)
            S += ETA*room; C_exec[t] = room
            rest = -gap - room
            R_PV[t] = min(Pa[t], max(rest, 0.0))
            R_G[t] = max(0.0, rest - R_PV[t])
    return H, R_PV, R_G, S, C_exec, D_exec


def run_year(L, P, price, lam=LAM, terminal="value", K=K_DEF, no_storage=False):
    s = S0; rows = {}
    tot = dict(J_plan=0.0, J_emg=0.0, QG=0.0, QH=0.0, Wgrid=0.0, R_PV=0.0, R_G=0.0,
               R_G_plan=0.0, n_RG_days=0)
    err = dict(bal=0.0, soc=0.0, mutex=0.0, cross=0.0, wgrid=0.0)
    prev_end = None
    smin_run = [S0]; smax_run = [S0]
    for d in range(FIRST, 365):
        G, diag = plan_layer(L, P, d, s, lam=lam, K=K, terminal=terminal, no_storage=no_storage)
        if G is None:
            return {"fatal": diag, "day": d}
        La, Pa = L[d]*DT, P[d]*DT
        H, R_PV, R_G, s_end, C_ex, D_ex = exec_E1(G, La, Pa, s)
        # 物理校验
        bal = G + Pa + H + D_ex - La - C_ex - R_PV - R_G
        err["bal"] = max(err["bal"], float(np.max(np.abs(bal))))
        # SOC 递推残差（用执行器的隐式轨迹重算）
        S2 = s; soc_err = 0.0
        for t in range(T):
            gap = La[t]-Pa[t]-G[t]
            if gap > 1e-12:
                dd = min(EBAR, ETA*(S2-SMIN), gap); dd = max(dd, 0.0)
                S2 -= dd/ETA
            else:
                cc = max(min(EBAR, (SMAX-S2)/ETA, -gap), 0.0); S2 += ETA*cc
        err["soc"] = max(err["soc"], abs(S2-s_end))
        smin_run[0] = min(smin_run[0], float(S2)); smax_run[0] = max(smax_run[0], float(S2))
        err["wgrid"] = max(err["wgrid"], float(np.max(R_G - G)))
        err["mutex"] = max(err["mutex"], float(np.max(H*R_PV)), float(np.max(H*R_G)),
                           float(np.max(C_ex*D_ex)), float(np.max(H*C_ex)))
        if prev_end is not None:
            err["cross"] = max(err["cross"], abs(s-prev_end))
        prev_end = S2   # 用独立重算轨迹的日末值，避免 prev_end==s_end 恒等式空转
        tot["J_plan"] += float((price*G).sum()); tot["J_emg"] += float((5*price*H).sum())
        tot["QG"] += float(G.sum()); tot["QH"] += float(H.sum())
        tot["R_PV"] += float(R_PV.sum()); tot["R_G"] += float(R_G.sum())
        rgl = float(np.sum(diag.get("R_G_plan_mean", np.zeros(T))))
        tot["R_G_plan"] += rgl
        if R_G.sum() > 1e-6: tot["n_RG_days"] += 1
        rows[d] = dict(G=G, H=H, R_PV=R_PV, R_G=R_G, C_exec=None, S0=s, S1=s_end)
        s = s_end
    tot["J_total"] = tot["J_plan"] + tot["J_emg"]
    tot["Wgrid"] = tot["R_G"]
    tot["SOC_min"] = smin_run[0]; tot["SOC_max"] = smax_run[0]
    tot["S_end"] = float(s)
    return {"tot": tot, "err": err, "rows": rows, "n_days": 365-FIRST}


def seg_count(h):
    n = 0; prev = False
    for v in h:
        cur = v > 1e-9
        if cur and not prev: n += 1
        prev = cur
    return n


def main():
    t0 = time.time()
    L, P, price = load_all()
    out = {"params": dict(T=T, dt=DT, Ebar=EBAR, Smin=SMIN, Smax=SMAX, eta=ETA,
                          S0=S0, K=K_DEF, lam_main=LAM,
                          csv_sha_note="read-only inputs from B对话/clean")}
    print("[1/5] 主线 残值 λ=%.4f ..." % LAM, flush=True)
    m = run_year(L, P, price, lam=LAM, terminal="value")
    out["main"] = {"tot": m["tot"], "err": m["err"], "n_days": m["n_days"]}
    print("      J_total=%.2f  紧急=%.0f kWh  W_grid=%.1f  年末SOC=%.1f" %
          (m["tot"]["J_total"], m["tot"]["QH"], m["tot"]["Wgrid"], m["tot"]["S_end"]), flush=True)
    print("[2/5] 对照：自由终值 ...", flush=True)
    f = run_year(L, P, price, lam=0.0, terminal="free")
    out["free"] = {"tot": f["tot"], "err": f["err"]}
    print("[3/5] 对照：周期终值 ...", flush=True)
    cy = run_year(L, P, price, lam=0.0, terminal="cyclic")
    out["cyclic"] = {"tot": cy["tot"], "err": cy["err"]}
    print("[4/5] 基准：无储能（报童） ...", flush=True)
    n = run_year(L, P, price, lam=0.0, terminal="free", no_storage=True)
    out["no_storage"] = {"tot": n["tot"], "err": n["err"]}
    print("[5/5] 报童 q0.8 一致性 + 信息泄漏扰动 ...", flush=True)
    qchk = []
    for d in [60, 120, 200, 300]:
        qchk.append(quantile_check(L, P, d, S0))
    out["newsvenor_q08"] = qchk
    leak = leak_check(L, P, price)
    out["leakage_check"] = leak
    # 论文日期紧急购电段数
    dates = {}
    for ds, d in PAPER_DATES.items():
        H = m["rows"][d]["H"]
        dates[ds] = dict(segments=seg_count(H), kWh=float(H.sum()))
    out["paper_dates_emergency"] = dates
    out["runtime_sec"] = round(time.time()-t0, 1)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1,
                  default=lambda o: (o.tolist() if isinstance(o, np.ndarray) else str(o)))
    print("  写出", OUT, flush=True)
    return out


def quantile_check(L, P, d, s0, K=K_DEF):
    """无储能 + 无紧急惩罚的纯报童：G* 应等于情景净需求的 0.8 经验分位数。"""
    ks = list(range(max(0, d-K), d))
    Dk = (L[ks]-P[ks])*DT
    G, _ = plan_layer(L, P, d, s0, lam=0.0, K=K, terminal="free", no_storage=True)
    nq = len(ks)
    # 经验下分位数（保守定义：最小的使 P(D<=q)>=0.8 的情景值），并按豆包第 4 条做非负截断
    q08 = np.maximum(np.quantile(Dk, 0.8, axis=0), 0.0)
    emp = np.maximum(np.sort(Dk, axis=0)[min(int(np.ceil(0.8*nq))-1, nq-1)], 0.0)
    return dict(day=d, max_abs_dev_lin=float(np.max(np.abs(G-q08))),
                max_abs_dev_emp=float(np.max(np.abs(G-emp))),
                n_scen=nq,
                n_truncated_intervals=int(np.sum(np.quantile(Dk, 0.8, axis=0) < 0)))


def leak_check(L, P, price):
    """信息泄漏：扰动当天实际值，G_plan 必须不变。"""
    d = 200; s0 = 4000.0
    G0, _ = plan_layer(L, P, d, s0, lam=LAM)
    Lp = L.copy(); Pp = P.copy()
    Lp[d] = Lp[d]*3.0 + 5000.0
    Pp[d] = Pp[d]*0.1
    G1, _ = plan_layer(Lp, Pp, d, s0, lam=LAM)
    return dict(day=d, max_abs_diff=float(np.max(np.abs(G0-G1))), zero=bool(np.allclose(G0, G1)))


if __name__ == "__main__":
    r = main()
    print(json.dumps({k: v for k, v in r.items() if k not in ("main",)}, ensure_ascii=False)[:1200])



