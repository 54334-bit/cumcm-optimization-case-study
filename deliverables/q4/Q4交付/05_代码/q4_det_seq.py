# -*- coding: utf-8 -*-
"""Q4-2 主线求解：附件 4 实时波动电价下重算问题 2（逐日滚动、非预见因果口径）。

口径（逐条复刻对话 5 的 Q2 现行主口径，唯一差别 = 电价用附件 4 的当日价格）：
  每天 d（评估期 2025-02-01~2025-12-31，共 334 天，索引 31..364）：
    ks   = [d-4, d-3, d-2, d-1]
    base = mean_{k in ks}(P_k)                                   # 过去 4 天实际光伏（kW）
    margin_d = clip(-Q20(过去 28 天相对预报误差), 0, 0.35)        # 逐日重估的因果保守裕度
    P_hat = clip(base * (1 - margin_d), 0, None)                 # 日前光伏预测（非预见）
    Le = L_d（当日实际负荷）; Pe = P_hat（K=4 条相同情景）
    解 LP：min Σ_t p_t G_t + (1/K)Σ_kΣ_t 5 p_t e_{k,t} - (λ/K) Σ_k S_{k,144}
    s.t. G + PV̂_k + D_k + e_k = L_d + C_k + R_k；eta=0.9；0≤C,D≤833.333；
         0≤R_k≤PV̂_k；1200≤S≤10800；初值 S_0 = 上一天执行后实际 SOC
  执行（E1 因果在线）：gap = L_d*DT - P_actual_d*DT - G
    gap > 0  → 先放电 D = min(Ebar, eta(S-SMIN), gap)，不足 H = gap - D 计 5 倍紧急购电
    gap <= 0 → 先充电 C = min(Ebar, (SMAX-S)/eta, -gap)，余量先弃光伏 R_PV，再弃计划购电 R_G
  结算：J_plan = Σ p_t G_t；J_emg = Σ 5 p_t H_t；J = J_plan + J_emg

闸门：价格换成附件 1（典型日曲线）后同链重跑，全年费用必须 = 13,252,341.09 元。

只读复用（不复制、不改写对话 5 的代码）：
  D:\\CMUCU\\5对话\\code\\q2_milp_plan.py  → _build(Le, Pe, price, s0, lam, [])
  D:\\CMUCU\\5对话\\code\\q2_v2_micro.py    → load_all()（L, P, 附件1 电价, ...）

运行（PowerShell）：
  $env:PYTHONPATH="D:\\CMUCU\\rag\\.deps"; $env:PYTHONIOENCODING='utf-8'
  & "<python>" "D:\\CMUCU\\8对话\\code\\q4_det_seq.py" --mode all
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time

import numpy as np
from scipy.optimize import linprog

CODE_DIR = r"D:\CMUCU\8对话\code"
OUT_DIR = r"D:\CMUCU\8对话\output"
DATA_DIR = r"D:\CMUCU\B对话\clean"
ANCHOR_JSON = os.path.join(OUT_DIR, "q4_data_anchor.json")
CP_JSON = os.path.join(OUT_DIR, "q4_cp2_checkpoint.json")
GATE_JSON = os.path.join(OUT_DIR, "q4_cp2_gate.json")
Q5_CODE = r"D:\CMUCU\5对话\code"

# ---- 常量（与任务书 / q4_data_anchor.json 一致）----
T = 144
DT = 1.0 / 6.0
S0 = 6000.0
SMIN, SMAX, ETA = 1200.0, 10800.0, 0.9
EBAR = 5000.0 * DT
DAYS = list(range(31, 365))          # 2025-02-01 ~ 2025-12-31，共 334 天
K = 4                                # 情景数（4 条相同情景）
LAM = 0.4720                         # 终端 SOC 线性残值价（元/kWh）
RELQ, WIN, CAP = 0.20, 28, 0.35      # 相对误差 20% 分位 / 28 天窗口 / 裕度上限
N_EMG_MULT = 5.0                     # 紧急购电电价倍数

# 闸门期望（对话 5 Q2 现行主口径 + 附件 1 价格）
GATE_EXPECT = dict(total=13252341.09, J_plan=12891818.24, J_emg=360522.85,
                   emg_days=242, QH=55801.0, s_end=7950.0)
GATE_TOL = 0.01


def load_module(name, path):
    """按文件路径只读加载同仓模块（避免与已安装同名包冲突）。"""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_inputs():
    """读取 Q2 复用构件（负荷/光伏/附件1 电价）与附件 4 电价。"""
    sys.path.append(os.path.join(r"D:\CMUCU", "rag", ".deps"))
    sys.path.append(Q5_CODE)
    mm = load_module("q4_mm", os.path.join(Q5_CODE, "q2_v2_micro.py"))
    mp = load_module("q4_mp", os.path.join(Q5_CODE, "q2_milp_plan.py"))
    L, P, price1 = mm.load_all()
    # 附件 4 电价：复用对话 8 的数据入口（含表头/列数校验）
    dio = load_module("q4_dio", os.path.join(CODE_DIR, "q4_data_io.py"))
    _, p4 = dio.read_matrix("attachment4_clean.csv")
    if L.shape != (365, T) or P.shape != (365, T) or p4.shape != (365, T):
        raise RuntimeError("输入形状异常: L%s P%s p4%s" % (L.shape, P.shape, p4.shape))
    return dict(mm=mm, mp=mp, L=L, P=P, price1=np.asarray(price1, dtype=float), p4=p4)


def anchor_check(p4):
    """用 q4_data_anchor.json 的附件4 统计量做只读对账（可追溯性）。"""
    if not os.path.exists(ANCHOR_JSON):
        return {"present": False}
    with open(ANCHOR_JSON, "r", encoding="utf-8") as fh:
        anchor = json.load(fh)
    st = anchor.get("p4_stats", {})
    got = dict(min=float(p4.min()), max=float(p4.max()), mean=float(p4.mean()))
    dev = {k: abs(got[k] - float(st[k])) for k in got if k in st}
    return {"present": True, "anchor_all_pass": bool(anchor.get("all_pass")),
            "anchor_stats": st, "measured": got, "abs_dev": dev,
            "max_abs_dev": max(dev.values()) if dev else None,
            "match": bool(dev) and max(dev.values()) <= 1e-9}


def causal_margin(P, d):
    """因果保守裕度 margin_d = clip(-Q20(过去 28 天相对预报误差), 0, 0.35)。

    相对误差：τ ∈ [d-28, d-1]，用 τ 的实际光伏对比 τ 的"过去 4 天实际均值"，
    仅在 4 天均值 > 1 kW 的时段统计；Q20 为 20% 分位数（保守裕度）。
    """
    rels = []
    for tau in range(max(K, d - WIN), d):
        kk = [x for x in range(max(0, tau - K), tau)]
        if len(kk) != K:
            continue
        f = (P[kk] * DT).mean(axis=0)
        m = f > 1.0
        if m.any():
            rels.append((P[tau] * DT - f)[m] / f[m])
    if not rels:
        return 0.0
    rr = np.concatenate(rels)
    return float(np.clip(-np.quantile(rr, RELQ), 0.0, CAP))


def execute_day_e1(G, La, Pa, s0):
    """E1 因果在线执行层：接收并全额接受计划购电 G。

    返回 (H, R_PV, R_G, S_end, C_exec, D_exec, S_path)，单位 kWh（功率×DT）。
    放电/充电按 gap 互斥分支处理，同一时段不可能同充同放；
    余量（-gap - 充电量）先弃光伏 R_PV、再弃计划购电 R_G。
    """
    S = float(s0)
    H = np.zeros(T)
    R_PV = np.zeros(T)
    R_G = np.zeros(T)
    C = np.zeros(T)
    D = np.zeros(T)
    S_path = np.empty(T + 1)
    S_path[0] = S
    for t in range(T):
        gap = La[t] - Pa[t] - G[t]                    # kWh
        if gap > 1e-12:
            dd = max(0.0, min(EBAR, ETA * (S - SMIN), gap))
            S -= dd / ETA
            D[t] = dd
            H[t] = gap - dd
        else:
            room = max(0.0, min(EBAR, (SMAX - S) / ETA, -gap))
            S += ETA * room
            C[t] = room
            rest = max(0.0, -gap - room)
            R_PV[t] = min(Pa[t], rest)                # 先弃光伏
            R_G[t] = rest - R_PV[t]                   # 再弃计划购电（应为 0）
        S_path[t + 1] = S
    return H, R_PV, R_G, S, C, D, S_path


def run_chain(data, price_of_day, settle_of_day, tag, verbose=True):
    """逐日滚动跑完评估期，返回逐日记录与全年汇总。

    price_of_day(d)  → 计划层优化使用的 144 维电价
    settle_of_day(d) → 结算使用的 144 维电价（Q4 主线：两者同为附件 4 当日价格）
    """
    L, P = data["L"], data["P"]
    mp = data["mp"]
    s = S0
    records = []
    agg = dict(total=0.0, J_plan=0.0, J_emg=0.0, QG=0.0, QH=0.0, Q_RPV=0.0,
               Q_RG=0.0, chi=0.0, n_emg_days=0, Q_pv_actual=0.0, Q_load=0.0)
    s_min, s_max = s, s
    worst_bal, worst_soc_rec, worst_neg = 0.0, 0.0, 0.0
    max_rpv_over_pv = -np.inf
    plan_both = 0.0                                  # 计划层同充同放诊断
    t0 = time.time()
    for i, d in enumerate(DAYS):
        ks = [x for x in range(max(0, d - K), d)]
        base = (P[ks] * DT).mean(axis=0)
        margin_d = causal_margin(P, d)
        Pe_d = np.clip(base * (1.0 - margin_d), 0.0, None)
        Le = np.tile(L[d] * DT, (len(ks), 1))
        Pe = np.tile(Pe_d, (len(ks), 1))
        pk = price_of_day(d)
        c, Aeq, beq, Aub, bub, bd, integ, nk, nz = mp._build(Le, Pe, pk, s, LAM, [])
        r = linprog(c, A_eq=Aeq, b_eq=beq, A_ub=Aub, b_ub=bub, bounds=bd, method="highs")
        if not r.success:
            raise RuntimeError("day %d LP 失败: %s" % (d, r.message))
        G = np.asarray(r.x[0:T], dtype=float)
        # 计划层诊断：各情景平均 C/D 与同充同放量
        Ck = np.zeros(T)
        Dk = np.zeros(T)
        for k in range(len(ks)):
            off = T + k * nk
            Ck += r.x[off:off + T] / len(ks)
            Dk += r.x[off + T:off + 2 * T] / len(ks)
        plan_both += float(np.minimum(Ck, Dk).sum())

        La, Pa = L[d] * DT, P[d] * DT
        H, R_PV, R_G, s1, C, D, S_path = execute_day_e1(G, La, Pa, s)
        ps = settle_of_day(d)
        J_plan_d = float((ps * G).sum())
        J_emg_d = float((N_EMG_MULT * ps * H).sum())

        # 逐时恒等式残差：源 = 计划购电 + 实际光伏 + 放电 + 紧急购电
        #                   汇 = 负荷 + 充电 + 弃光伏 + 弃计划购电
        resid = G + Pa + D + H - La - C - R_PV - R_G
        worst_bal = max(worst_bal, float(np.abs(resid).max()))
        worst_neg = min(worst_neg, float(min(G.min(), C.min(), D.min(), H.min(),
                                           R_PV.min(), R_G.min())))
        max_rpv_over_pv = max(max_rpv_over_pv, float((R_PV - Pa).max()))
        s_min = min(s_min, float(S_path.min()))
        s_max = max(s_max, float(S_path.max()))
        worst_soc_rec = max(worst_soc_rec, float(np.abs(
            S_path[1:] - (S_path[:-1] - D / ETA + ETA * C)).max()))

        agg["total"] += J_plan_d + J_emg_d
        agg["J_plan"] += J_plan_d
        agg["J_emg"] += J_emg_d
        agg["QG"] += float(G.sum())
        agg["QH"] += float(H.sum())
        agg["Q_RPV"] += float(R_PV.sum())
        agg["Q_RG"] += float(R_G.sum())
        agg["chi"] += float(np.minimum(C, D).sum())
        agg["Q_pv_actual"] += float(Pa.sum())
        agg["Q_load"] += float(La.sum())
        if H.sum() > 1e-9:
            agg["n_emg_days"] += 1

        # 逐时流量落盘保留 8 位小数，使恒等式可从产物本身按 1e-6 复现
        records.append(dict(
            d=d, margin_d=round(margin_d, 8), S0=round(float(s), 6),
            S1=round(float(s1), 6), J_plan=round(J_plan_d, 6), J_emg=round(J_emg_d, 6),
            QG=round(float(G.sum()), 6), QH=round(float(H.sum()), 6),
            G=[round(float(v), 8) for v in G], C=[round(float(v), 8) for v in C],
            D=[round(float(v), 8) for v in D], H=[round(float(v), 8) for v in H],
            R_PV=[round(float(v), 8) for v in R_PV], R_G=[round(float(v), 8) for v in R_G],
            C_plan_mean=[round(float(v), 8) for v in Ck],
            D_plan_mean=[round(float(v), 8) for v in Dk],
            bal_resid_max=round(float(np.abs(resid).max()), 12),
        ))
        s = float(s1)
        if verbose and ((i + 1) % 40 == 0 or i + 1 == len(DAYS)):
            print("  [%s] %3d/%d 天 | 累计 %16.2f 元 | SOC %.1f | %.0fs"
                  % (tag, i + 1, len(DAYS), agg["total"], s, time.time() - t0), flush=True)

    agg["s_end"] = round(float(s), 6)
    agg["plan_both_charge_discharge"] = round(plan_both, 8)
    diag = dict(soc_min=s_min, soc_max=s_max, worst_bal_resid=worst_bal,
                worst_soc_recursion_resid=worst_soc_rec, worst_negative_flow=worst_neg,
                max_RPV_minus_PV=max_rpv_over_pv, elapsed_s=round(time.time() - t0, 2))
    for k in ("total", "J_plan", "J_emg", "QG", "QH", "Q_RPV", "Q_RG", "chi",
              "Q_pv_actual", "Q_load"):
        agg[k] = round(float(agg[k]), 6)
    if verbose:
        print("  [%s] 完成：合计 %.2f 元 | 计划 %.2f | 紧急 %.2f | 紧急 %d 天 %.1f kWh | "
              "年末 SOC %.1f | 用时 %.0fs"
              % (tag, agg["total"], agg["J_plan"], agg["J_emg"], agg["n_emg_days"],
                 agg["QH"], agg["s_end"], diag["elapsed_s"]), flush=True)
    return dict(records=records, agg=agg, diag=diag)


def build_assertions(res):
    """§4 防退化断言 ①~⑧（对执行层实测值判定）。"""
    recs, agg, diag = res["records"], res["agg"], res["diag"]

    def A(no, name, ok, value, criterion):
        # JSON 字段名按任务书 §3 用 "pass"（Python 关键字，故用字典字面量构造）
        return {"no": no, "name": name, "pass": bool(ok),
                "value": value, "criterion": criterion}

    checks = [
        A("①", "H_t >= 0 逐时成立", diag["worst_negative_flow"] >= -1e-9,
          dict(min_all_flows=diag["worst_negative_flow"], QH=agg["QH"]),
          "所有小时 H>=0（容差 1e-9）"),
        A("②", "R_t <= PV_actual_t*dt 逐时成立", diag["max_RPV_minus_PV"] <= 1e-9,
          dict(max_RPV_minus_PV=diag["max_RPV_minus_PV"], Q_RPV=agg["Q_RPV"],
               Q_PV_actual=agg["Q_pv_actual"]),
          "逐时 R_PV<=Pa（容差 1e-9）"),
        A("③", "全时段 1200 <= S <= 10800",
          diag["soc_min"] >= SMIN - 1e-6 and diag["soc_max"] <= SMAX + 1e-6,
          dict(soc_min=diag["soc_min"], soc_max=diag["soc_max"], soc_end=agg["s_end"]),
          "含每日 S_path 全部 145 个点"),
        A("④", "逐日能量恒等式残差 <= 1e-6 kWh", diag["worst_bal_resid"] <= 1e-6,
          dict(worst_bal_resid=diag["worst_bal_resid"],
               worst_soc_recursion_resid=diag["worst_soc_recursion_resid"]),
          "G+Pa+D+H = La+C+R_PV+R_G 且 SOC 递推一致"),
        A("⑤", "G >= 0", diag["worst_negative_flow"] >= -1e-9,
          dict(min_all_flows=diag["worst_negative_flow"], QG=agg["QG"]),
          "购电计划非负"),
        A("⑥", "无'无限弃光压成本'的解：ΣR_PV <= ΣPV",
          agg["Q_RPV"] <= agg["Q_pv_actual"] + 1e-6,
          dict(Q_RPV=agg["Q_RPV"], Q_PV_actual=agg["Q_pv_actual"],
               ratio=round(agg["Q_RPV"] / agg["Q_pv_actual"], 6),
               Q_RG=agg["Q_RG"]),
          "弃光不超过实际可用光伏"),
        A("⑦", "执行层同充同放禁止：chi = Σ_t min(C_t,D_t) = 0", abs(agg["chi"]) <= 1e-9,
          dict(chi=agg["chi"], plan_layer_both=agg["plan_both_charge_discharge"]),
          "执行层逐时互斥；计划层同充同放量另列诊断"),
        A("⑧", "无售电/无反送：购电+放电+光伏+紧急购电 = 负荷+充电+弃光",
          diag["worst_bal_resid"] <= 1e-6 and diag["worst_negative_flow"] >= -1e-9,
          dict(worst_bal_resid=diag["worst_bal_resid"],
               worst_negative_flow=diag["worst_negative_flow"]),
          "所有流向非负且逐时守恒；模型不含售电变量"),
    ]
    return checks


def make_gate(res):
    """§3 闸门：附件 1 价格下全年费用 = 13,252,341.09 元（容差 0.01）。"""
    agg = res["agg"]
    items = [
        ("total_att1", agg["total"], GATE_EXPECT["total"], GATE_TOL),
        ("J_plan", agg["J_plan"], GATE_EXPECT["J_plan"], GATE_TOL),
        ("J_emg", agg["J_emg"], GATE_EXPECT["J_emg"], GATE_TOL),
        ("emg_days", float(agg["n_emg_days"]), float(GATE_EXPECT["emg_days"]), 0.0),
        ("QH_kWh", agg["QH"], GATE_EXPECT["QH"], 0.05),
        ("s_end", agg["s_end"], GATE_EXPECT["s_end"], 0.05),
    ]
    detail = []
    for name, got, exp, tol in items:
        diff = float(got) - float(exp)
        detail.append(dict(item=name, measured=round(float(got), 6), expected=float(exp),
                           diff=round(diff, 6), tol=tol, **{"pass": bool(abs(diff) <= tol)}))
    return dict(
        task="q4_main_solve",
        gate="把价格换成附件1 后同一条链重跑，复现 Q2 现行主口径全年费用",
        **{"pass": all(x["pass"] for x in detail)},
        total_att1=round(float(agg["total"]), 6),
        diff_vs_expected=round(float(agg["total"]) - GATE_EXPECT["total"], 6),
        expected_total=GATE_EXPECT["total"],
        items=detail,
        items_flat=dict(J_plan=round(float(agg["J_plan"]), 6),
                        J_emg=round(float(agg["J_emg"]), 6),
                        emg_days=int(agg["n_emg_days"]), QH_kWh=agg["QH"],
                        s_end=agg["s_end"]),
        assertions_gate_run=build_assertions(res),
        assertions_all_pass=all(c["pass"] for c in build_assertions(res)),
        diag=res["diag"],
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["gate", "main", "all"], default="all")
    args = ap.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True)

    data = load_inputs()
    anc = anchor_check(data["p4"])
    print("数据就绪：附件4 价格 min=%.4f max=%.4f mean=%.6f | 锚点对账 %s"
          % (data["p4"].min(), data["p4"].max(), data["p4"].mean(),
             "MATCH" if anc.get("match") else "见 checkpoint"), flush=True)

    gate_res = main_res = None
    gate = None
    if args.mode in ("gate", "all"):
        print("=== 闸门：附件1 价格 + Q2 现行主口径（期望 %.2f 元）==="
              % GATE_EXPECT["total"], flush=True)
        gate_res = run_chain(data, lambda d: data["price1"], lambda d: data["price1"], "gate")
        gate = make_gate(gate_res)
        with open(GATE_JSON, "w", encoding="utf-8") as fh:
            json.dump(gate, fh, ensure_ascii=False, indent=1)
        print("闸门 pass=%s | total_att1=%.2f | diff=%+.4f | J_plan=%.2f J_emg=%.2f | "
              "%d 天 %.1f kWh | 年末SOC=%.1f"
              % (gate["pass"], gate["total_att1"], gate["diff_vs_expected"],
                 gate["items_flat"]["J_plan"], gate["items_flat"]["J_emg"],
                 gate["items_flat"]["emg_days"], gate["items_flat"]["QH_kWh"],
                 gate["items_flat"]["s_end"]), flush=True)
        print("已写 %s" % GATE_JSON, flush=True)
        if not gate["pass"]:
            print("!! 闸门未过：按任务书 §3，不据附件1 价格口径做任何调参凑数。", flush=True)

    if args.mode in ("main", "all"):
        print("=== Q4 主线：附件4 当日实时电价（计划价 = 结算价 = p4[d]）===", flush=True)
        main_res = run_chain(data, lambda d: data["p4"][d], lambda d: data["p4"][d], "main")
        checks = build_assertions(main_res)
        agg, diag = main_res["agg"], main_res["diag"]
        payload = dict(
            task="q4_main_solve",
            generated_by=os.path.abspath(__file__),
            caliber=dict(
                q="Q4-2 = Q2 现行主口径（非预见 + 因果保守裕度）下换用附件4 实时电价",
                forecast="base=mean(P_{d-4..d-1}); margin_d=clip(-Q20(rel_err,28d),0,0.35); "
                         "P_hat=clip(base*(1-margin_d),0,None)",
                price_plan="p4[d]：附件4 当日 144 点价格",
                price_settle="p4[d]：与计划价同口径",
                K=K, lam=LAM, emg_multiplier=N_EMG_MULT,
                terminal="lambda * S_{k,144} 线性残值（lambda=0.4720）",
                execution="E1 因果在线：先放电/先充电，缺口 5 倍价紧急购电，余量先弃光伏",
            ),
            constants=dict(T=T, DT=DT, S0=S0, SMIN=SMIN, SMAX=SMAX, EBAR=EBAR, ETA=ETA),
            eval_window=dict(days=[DAYS[0], DAYS[-1]], n_days=len(DAYS),
                             first_date="2025-02-01", last_date="2025-12-31"),
            data_source=dict(load=os.path.join(DATA_DIR, "attachment2_load.csv"),
                             pv=os.path.join(DATA_DIR, "attachment2_pv.csv"),
                             price=os.path.join(DATA_DIR, "attachment4_clean.csv"),
                             anchor=ANCHOR_JSON, anchor_check=anc),
            annual=agg,
            diagnostics=dict(diag, arrays_rounded_to=8,
                             note="逐时流量按 8 位小数落盘；断言在运行中按全精度判定，"
                                  "从产物复算亦可满足 1e-6"),
            assertions=checks,
            assertions_all_pass=all(c["pass"] for c in checks),
            gate=dict(json=GATE_JSON,
                      **{"pass": (gate["pass"] if gate is not None else None)},
                      note="闸门结果另存 q4_cp2_gate.json；本 checkpoint 为附件4 电价下的 Q4 主结果"),
            days=main_res["records"],
        )
        with open(CP_JSON, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=None,
                      separators=(",", ":"))
        print("--- §4 断言（Q4 主结果）---", flush=True)
        for c in checks:
            print("  %s %-40s %s  %s" % (c["no"], c["name"],
                                         "PASS" if c["pass"] else "FAIL", c["value"]),
                  flush=True)
        print("断言全过 = %s" % payload["assertions_all_pass"], flush=True)
        print("年末 SOC=%.1f | J_plan=%.2f | J_emg=%.2f | 紧急 %d 天 %.1f kWh"
              % (agg["s_end"], agg["J_plan"], agg["J_emg"], agg["n_emg_days"], agg["QH"]),
              flush=True)
        print("已写 %s" % CP_JSON, flush=True)


if __name__ == "__main__":
    main()
