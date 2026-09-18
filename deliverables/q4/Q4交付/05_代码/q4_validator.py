# -*- coding: utf-8 -*-
"""Q4-2 result4-2.xlsx 独立校验器。

数据来源（全部只读）：
  - 成品：D:\\CMUCU\\8对话\\output\\result4-2.xlsx
  - 原始附件2：D:\\CMUCU\\赛题\\C题\\附件\\附件2.xlsx（实际负荷 / 实际光伏）
  - 原始附件4：D:\\CMUCU\\赛题\\C题\\附件\\附件4.xlsx（Q4 波动电价）
  - checkpoint D:\\CMUCU\\8对话\\output\\q4_cp2_checkpoint.json
      仅用于任务书 §4.5 明确要求的“列映射抽检”，以及参考性对账；
      不参与任何数值的生成或修正。

本脚本不 import 求解器、不 import q4_det_seq / q4_materialize；执行层 E1 规则
（缺口先放电、余量先充电、再弃光伏、不足 5 倍价紧急购电）在本文件内独立重实现。

输出：D:\\CMUCU\\8对话\\output\\q4_validator_result.json
结构：{"checks":[{"name":..., "pass":true/false, "max_abs":...}], "errors":[...]}
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta

import numpy as np
import openpyxl

ROOT = r"D:\CMUCU\8对话"
XLSX = os.path.join(ROOT, "output", "result4-2.xlsx")
A2 = r"D:\CMUCU\赛题\C题\附件\附件2.xlsx"
A4 = r"D:\CMUCU\赛题\C题\附件\附件4.xlsx"
CP_JSON = os.path.join(ROOT, "output", "q4_cp2_checkpoint.json")
OUT_JSON = os.path.join(ROOT, "output", "q4_validator_result.json")

T = 144
DT = 1.0 / 6.0
S0 = 6000.0
SMIN = 1200.0
SMAX = 10800.0
EBAR = 5000.0 * DT          # 833.3333333333333 kWh / 10 min
ETA = 0.9
N_EMG_MULT = 5.0
DAYS = list(range(31, 365))  # 2025-02-01 ~ 2025-12-31，共 334 天

TOL_BAL = 1e-6
TOL_SOC = 1e-3
TOL_COST = 1e-4
TOL_SEG = 1e-6
TOL_CHI = 1e-9
TOL_FLOW = 1e-9

SHEET_PLAN = "计划购电量"
SHEET_SOC = "充放电量"
SHEET_EMG = "紧急购电量"
BLOCK_LABELS = ["0:00-4:00", "4:00-8:00", "8:00-12:00",
                "12:00-16:00", "16:00-20:00", "20:00-24:00"]


def as_date(v):
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    txt = str(v).strip().replace("/", "-").split(" ")[0]
    y, m, d = (int(x) for x in txt.split("-")[:3])
    return date(y, m, d)


def date_of(day_index: int) -> date:
    return date(2025, 1, 1) + timedelta(days=day_index)


def parse_span(txt):
    if txt is None:
        return None
    s = str(txt).strip().replace(" ", "")
    if "-" not in s:
        return None
    a, b = s.split("-", 1)

    def _min(x):
        hh, mm = x.split(":")
        return int(hh) * 60 + int(mm)

    try:
        return _min(a), _min(b)
    except Exception:
        return None


def load_attach(path: str) -> np.ndarray:
    """读官方附件的 365 x 144 数值矩阵（日期在表头之外，按行对应 1 月 1 日起）。"""
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    arr = np.asarray([[float(v) for v in r[1:1 + T]] for r in rows[1:]], dtype=float)
    assert arr.shape == (365, T), "%s 形状 %s != (365,144)" % (path, arr.shape)
    return arr


def load_attach2_sheet(path: str, sheet_name: str) -> np.ndarray:
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb[sheet_name]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    arr = np.asarray([[float(v) for v in r[1:1 + T]] for r in rows[1:]], dtype=float)
    assert arr.shape == (365, T), "%s[%s] 形状 %s != (365,144)" % (path, sheet_name, arr.shape)
    return arr


def read_deliverable(path: str) -> dict:
    wb = openpyxl.load_workbook(path, data_only=True)
    for sh in (SHEET_PLAN, SHEET_SOC, SHEET_EMG):
        if sh not in wb.sheetnames:
            wb.close()
            raise ValueError("成品缺少工作表 %s（现有 %s）" % (sh, wb.sheetnames))

    out = {"path": path, "sheets": list(wb.sheetnames)}

    # 表1：计划购电量 + 全天购电量/购电费
    ws = wb[SHEET_PLAN]
    dates, G, qty, cost = [], [], [], []
    for r in range(2, ws.max_row + 1):
        dh = ws.cell(r, 1).value
        row = [ws.cell(r, 2 + t).value for t in range(T)]
        if dh is None and all(v is None for v in row):
            continue
        if dh is None:
            wb.close()
            raise ValueError("[%s] 第 %d 行有时间序列但缺日期" % (SHEET_PLAN, r))
        dates.append(as_date(dh))
        G.append([np.nan if v is None else float(v) for v in row])
        qv = ws.cell(r, 146).value
        cv = ws.cell(r, 147).value
        qty.append(np.nan if qv is None else float(qv))
        cost.append(np.nan if cv is None else float(cv))
    out["dates"] = dates
    out["G"] = np.asarray(G, dtype=float)
    out["day_qty"] = np.asarray(qty, dtype=float)
    out["day_cost"] = np.asarray(cost, dtype=float)

    # 表2：充放电量（每天 6 行块） + 0:00 / 24:00 SOC 锚点
    ws = wb[SHEET_SOC]
    data_rows = []
    for r in range(2, ws.max_row + 1):
        vals = [ws.cell(r, c).value for c in range(1, 7)]
        if all(v is None for v in vals):
            continue
        data_rows.append((r, vals))
    blocks = []
    i = 0
    while i < len(data_rows):
        r0, v0 = data_rows[i]
        if v0[0] is None:
            wb.close()
            raise ValueError("[%s] 第 %d 行缺日期（数据块必须 6 行一组、日期在块首行）"
                             % (SHEET_SOC, r0))
        if i + 6 > len(data_rows):
            wb.close()
            raise ValueError("[%s] 日期 %s 的数据块不足 6 行" % (SHEET_SOC, v0[0]))
        chunk = data_rows[i:i + 6]
        if any(c[1][0] is not None for c in chunk[1:]):
            wb.close()
            raise ValueError("[%s] 第 %d 行起的 6 行块内出现重复日期" % (SHEET_SOC, r0))
        labels = [c[1][1] for c in chunk]
        c_blk = np.array([float(c[1][2]) if c[1][2] is not None else 0.0 for c in chunk])
        d_blk = np.array([float(c[1][3]) if c[1][3] is not None else 0.0 for c in chunk])
        soc0 = chunk[0][1][5]
        soc24 = chunk[1][1][5]
        blocks.append(dict(row0=r0, date=as_date(v0[0]), labels=labels,
                           charge=c_blk, discharge=d_blk,
                           soc_0=None if soc0 is None else float(soc0),
                           soc_24=None if soc24 is None else float(soc24)))
        i += 6
    out["soc_blocks"] = blocks
    out["C_block"] = np.asarray([b["charge"] for b in blocks], dtype=float)
    out["D_block"] = np.asarray([b["discharge"] for b in blocks], dtype=float)
    out["soc_dates"] = [b["date"] for b in blocks]
    out["soc_0"] = np.asarray([np.nan if b["soc_0"] is None else b["soc_0"] for b in blocks])
    out["soc_24"] = np.asarray([np.nan if b["soc_24"] is None else b["soc_24"] for b in blocks])

    # 表3：紧急购电量（日期列只在当日首段写一次，其余行继承）
    ws = wb[SHEET_EMG]
    emg = []
    cur_date = None
    raw_date_rows = []
    for r in range(2, ws.max_row + 1):
        dh = ws.cell(r, 1).value
        span = ws.cell(r, 2).value
        q = ws.cell(r, 3).value
        if dh is None and span is None and q is None:
            continue
        if dh is not None:
            cur_date = as_date(dh)
            raw_date_rows.append(r)
        if span is None or q is None:
            wb.close()
            raise ValueError("[%s] 第 %d 行时间段或购电量缺失" % (SHEET_EMG, r))
        ps = parse_span(span)
        if ps is None:
            wb.close()
            raise ValueError("[%s] 第 %d 行时间段无法解析：%r" % (SHEET_EMG, r, span))
        if cur_date is None:
            wb.close()
            raise ValueError("[%s] 第 %d 行缺日期且无上一条可继承" % (SHEET_EMG, r))
        emg.append(dict(row=r, date=cur_date, span=(str(span).strip(), ps[0], ps[1]),
                        qty=float(q)))
    out["emergency_rows"] = emg
    out["emergency_date_rows"] = raw_date_rows
    wb.close()
    return out


def recompute_e1(G, L, PV, P4):
    """独立重实现执行层 E1，返回逐 10 分钟流量（kWh/段）。"""
    n = G.shape[0]
    C = np.zeros_like(G)
    D = np.zeros_like(G)
    H = np.zeros_like(G)
    R_PV = np.zeros_like(G)
    R_G = np.zeros_like(G)
    S = np.zeros((n, T + 1))
    s = S0
    for i in range(n):
        S[i, 0] = s
        for t in range(T):
            la = L[i, t] * DT
            pa = PV[i, t] * DT
            gap = la - pa - G[i, t]
            if gap > 1e-12:
                dd = max(0.0, min(EBAR, ETA * (s - SMIN), gap))
                s -= dd / ETA
                D[i, t] = dd
                H[i, t] = gap - dd
            else:
                room = max(0.0, min(EBAR, (SMAX - s) / ETA, -gap))
                s += ETA * room
                C[i, t] = room
                rest = max(0.0, -gap - room)
                R_PV[i, t] = min(pa, rest)
                R_G[i, t] = rest - R_PV[i, t]
            S[i, t + 1] = s
    return dict(C=C, D=D, H=H, R_PV=R_PV, R_G=R_G, S=S)


def segments_of(values, threshold=1e-9):
    """把一日 H 向量切成 (t0, t1, qty) 段；相邻正区间合并，跨日不合并。

    独立复算时 G 保留 8 位小数，缺电边界会产生 ~1e-13..1e-9 的浮点噪声；
    对 H 用 1e-6 kWh/段（≈1e-5 kW）作为“真实发生”阈值，可剔除噪声而不影响
    真实紧急段（checkpoint 中最小的真实正段为 1.07e-6 kWh）。
    """
    out = []
    t = 0
    n = len(values)
    while t < n:
        if values[t] > threshold:
            t0 = t
            q = 0.0
            while t < n and values[t] > threshold:
                q += float(values[t])
                t += 1
            out.append((t0, t, q))
        else:
            t += 1
    return out


def mk_check(name, ok, max_abs, **extra):
    d = {"name": name, "pass": bool(ok), "max_abs": float(max_abs)}
    d.update(extra)
    return d


def main() -> int:
    errors = []
    checks = []
    d = read_deliverable(XLSX)
    L_all = load_attach2_sheet(A2, "小区负载")
    PV_all = load_attach2_sheet(A2, "光伏发电实际功率")
    P4_all = load_attach(A4)

    L = L_all[DAYS[0]:DAYS[-1] + 1]
    PV = PV_all[DAYS[0]:DAYS[-1] + 1]
    P4 = P4_all[DAYS[0]:DAYS[-1] + 1]

    n = len(d["dates"])
    G = d["G"]
    # ---------- C0 表结构与块合计对账 ----------
    ok_struct = True
    struct_msg = []
    if n != len(DAYS):
        ok_struct = False
        struct_msg.append("表1 天数 %d != 334" % n)
    if d["G"].shape != (len(DAYS), T):
        ok_struct = False
        struct_msg.append("表1 G 形状 %s != (334,144)" % (d["G"].shape,))
    if len(d["soc_blocks"]) != len(DAYS):
        ok_struct = False
        struct_msg.append("表2 天数 %d != 334" % len(d["soc_blocks"]))
    if len(d["emergency_rows"]) == 0:
        ok_struct = False
        struct_msg.append("表3 没有任何紧急购电行")
    if [as_date(x) for x in d["dates"]] != [date_of(x) for x in DAYS]:
        ok_struct = False
        struct_msg.append("表1 日期序列与 2025-02-01..2025-12-31 不一致")
    if d["soc_dates"] != d["dates"]:
        ok_struct = False
        struct_msg.append("表2 日期序列与表1 不一致")
    for i, b in enumerate(d["soc_blocks"]):
        if b["labels"] != BLOCK_LABELS:
            ok_struct = False
            struct_msg.append("表2 第 %d 天块标签 %s" % (i, b["labels"]))
            break
        if b["soc_0"] is None or b["soc_24"] is None:
            ok_struct = False
            struct_msg.append("表2 第 %d 天缺 SOC 锚点" % i)
            break
    checks.append(mk_check("C0_structure_and_block_totals", ok_struct,
                           0.0 if ok_struct else 1.0, issues=struct_msg[:10]))
    if not ok_struct:
        errors.append("表结构检查失败：" + "; ".join(struct_msg[:3]))

    # 独立执行层复算
    rec = recompute_e1(G, L, PV, P4)
    C, D, H = rec["C"], rec["D"], rec["H"]
    R_PV, R_G, S = rec["R_PV"], rec["R_G"], rec["S"]

    # 块合计对账（成品只有 4 小时块合计，逐段形状由独立复算给出）
    C_blk_ind = C.reshape(n, 6, 24).sum(axis=2) if n == len(DAYS) else np.zeros((0, 6))
    D_blk_ind = D.reshape(n, 6, 24).sum(axis=2) if n == len(DAYS) else np.zeros((0, 6))
    C_blk_dev = float(np.max(np.abs(d["C_block"] - C_blk_ind))) if n == len(DAYS) else float("inf")
    D_blk_dev = float(np.max(np.abs(d["D_block"] - D_blk_ind))) if n == len(DAYS) else float("inf")
    ok_blk = C_blk_dev <= TOL_BAL and D_blk_dev <= TOL_BAL
    checks.append(mk_check("C0b_xlsx_block_sums_vs_independent_recompute", ok_blk,
                           max(C_blk_dev, D_blk_dev),
                           max_abs_C=C_blk_dev, max_abs_D=D_blk_dev, tol=TOL_BAL))
    if not ok_blk:
        errors.append("表2 的 4 小时块合计与独立执行层复算不一致")

    # ---------- C1 逐区间能量平衡（完整物理式，含紧急购电与两种弃电） ----------
    resid_full = G + PV * DT + D + H - L * DT - C - R_PV - R_G
    max_bal_full = float(np.max(np.abs(resid_full))) if resid_full.size else 0.0
    ok_full = max_bal_full <= TOL_BAL
    checks.append(mk_check("C1_interval_energy_balance_full", ok_full, max_bal_full,
                           formula="G + PV_actual*dt + D + H - C - R_PV - R_G - L*dt = 0",
                           tol=TOL_BAL))
    if not ok_full:
        errors.append("逐区间完整能量平衡残差超过 %g" % TOL_BAL)

    # 任务书 §4.1 的写法用有符号净余量 R = R_PV + R_G - H 表示（缺电段 R<0）。
    R_net = R_PV + R_G - H
    resid_spec = G + D + PV * DT - C - R_net - L * DT
    max_bal_spec = float(np.max(np.abs(resid_spec))) if resid_spec.size else 0.0
    ok_spec = max_bal_spec <= TOL_BAL
    checks.append(mk_check("C1b_interval_balance_spec_signed_R", ok_spec, max_bal_spec,
                           formula="G + D + PV_actual*dt - C - R - L*dt = 0, R=R_PV+R_G-H",
                           R_min=float(R_net.min()), R_max=float(R_net.max()),
                           R_positive_kwh=float(R_net[R_net > 0].sum()),
                           tol=TOL_BAL))
    if not ok_spec:
        errors.append("任务书 §4.1 写法的逐区间能量平衡残差超过 %g" % TOL_BAL)

    # ---------- C2 SOC 链式递推一致性 + 边界 ----------
    soc_chain_dev = 0.0
    if n:
        soc_chain_dev = max(soc_chain_dev, abs(float(d["soc_0"][0]) - S0))
        for i in range(1, n):
            soc_chain_dev = max(soc_chain_dev,
                                abs(float(d["soc_0"][i]) - float(d["soc_24"][i - 1])))
    s_rec = S0
    soc_recalc_dev = 0.0
    for i in range(n):
        s_rec += ETA * float(d["C_block"][i].sum()) - float(d["D_block"][i].sum()) / ETA
        if np.isfinite(d["soc_24"][i]):
            soc_recalc_dev = max(soc_recalc_dev, abs(s_rec - float(d["soc_24"][i])))
    all_soc_rep = np.concatenate([d["soc_0"], d["soc_24"]])
    all_soc_rep = all_soc_rep[np.isfinite(all_soc_rep)]
    soc_bounds_dev = max(0.0, float(SMIN - all_soc_rep.min()) if all_soc_rep.size else 0.0,
                         float(all_soc_rep.max() - SMAX) if all_soc_rep.size else 0.0)
    soc_ind_bounds_dev = max(0.0, float(SMIN - S.min()), float(S.max() - SMAX))
    max_soc = max(soc_chain_dev, soc_recalc_dev, soc_bounds_dev, soc_ind_bounds_dev)
    ok_soc = max_soc <= TOL_SOC
    checks.append(mk_check("C2_soc_chain_and_bounds", ok_soc, max_soc,
                           chain_dev=soc_chain_dev, reported_vs_block_recalc=soc_recalc_dev,
                           reported_bounds_dev=soc_bounds_dev,
                           independent_bounds_dev=soc_ind_bounds_dev,
                           soc_min_ind=float(S.min()), soc_max_ind=float(S.max()),
                           soc_end_ind=float(S[-1, -1]), tol=TOL_SOC))
    if not ok_soc:
        errors.append("SOC 链式递推或边界检查失败，max_abs=%g" % max_soc)

    # ---------- C3 费用恒等式：表1 全天购电费 = p4·G（只含计划购电） ----------
    cost_dev = float(np.max(np.abs(d["day_cost"] - (P4 * G).sum(axis=1)))) if n else float("inf")
    qty_dev = float(np.max(np.abs(d["day_qty"] - G.sum(axis=1)))) if n else float("inf")
    ok_cost = cost_dev <= TOL_COST and qty_dev <= 1e-6
    checks.append(mk_check("C3_plan_cost_identity", ok_cost, max(cost_dev, qty_dev),
                           max_abs_cost=cost_dev, max_abs_qty=qty_dev,
                           J_plan_from_xlsx=float(np.nansum(d["day_cost"])),
                           QG_from_xlsx=float(np.nansum(d["day_qty"])),
                           J_plan_independent=float((P4 * G).sum()),
                           tol_cost=TOL_COST))
    if not ok_cost:
        errors.append("表1 全天购电费/购电量与 p4·G 不一致")

    # ---------- C3b 表3 紧急电量 = 独立复算 H 的合并段；计费按 5*p4 ----------
    exp_segments = []
    for i in range(n):
        for (t0, t1, q) in segments_of(H[i], 1e-6):
            exp_segments.append(dict(date=d["dates"][i], t0=t0, t1=t1, qty=q))
    got_segments = d["emergency_rows"]
    seg_msg = []
    if len(exp_segments) != len(got_segments):
        seg_msg.append("段数 %d != 复算 %d" % (len(got_segments), len(exp_segments)))
    seg_qty_dev = 0.0
    seg_span_dev = 0
    for j, (e, g) in enumerate(zip(exp_segments, got_segments)):
        if e["date"] != g["date"]:
            seg_msg.append("第 %d 段日期 %s != %s" % (j + 1, g["date"], e["date"]))
            continue
        if (g["span"][1] // 10, g["span"][2] // 10) != (e["t0"], e["t1"]):
            seg_msg.append("第 %d 段区间 %s != [%d,%d)" % (j + 1, g["span"][0], e["t0"], e["t1"]))
            seg_span_dev += 1
        seg_qty_dev = max(seg_qty_dev, abs(g["qty"] - e["qty"]))
    # 日期列只在当日首段写一次：表3 中重复出现的日期不允许
    reused = len(d["emergency_date_rows"]) - len(set(d["emergency_date_rows"]))
    ok_seg = (not seg_msg and seg_qty_dev <= TOL_SEG and seg_span_dev == 0)
    emg_cost = float((N_EMG_MULT * P4 * H).sum())
    checks.append(mk_check("C3b_emergency_segments_and_5x_billing", ok_seg,
                           max(seg_qty_dev, 1.0 if seg_msg else 0.0),
                           n_segments_xlsx=len(got_segments),
                           n_segments_independent=len(exp_segments),
                           max_abs_segment_qty=seg_qty_dev,
                           span_mismatches=seg_span_dev,
                           date_column_repeats=reused,
                           emg_kwh_sheet3=float(sum(r["qty"] for r in got_segments)),
                           emg_kwh_independent=float(H.sum()),
                           emg_cost_yuan_5x=emg_cost,
                           multiplier=N_EMG_MULT,
                           issues=seg_msg[:5], tol=TOL_SEG))
    if not ok_seg:
        errors.append("表3 紧急购电段与独立复算不一致")

    # ---------- C4 物理边界 ----------
    viol = [
        max(0.0, -float(G.min())) if n else 0.0,
        max(0.0, -float(C.min())),
        max(0.0, float(C.max()) - EBAR),
        max(0.0, -float(D.min())),
        max(0.0, float(D.max()) - EBAR),
        max(0.0, float(SMIN - S.min())),
        max(0.0, float(S.max() - SMAX)),
        max(0.0, float((R_PV - PV * DT).max())),
        max(0.0, -float(H.min())),
        max(0.0, -float(R_PV.min())),
        max(0.0, -float(R_G.min())),
        max(0.0, -float(d["C_block"].min())),
        max(0.0, float(d["C_block"].max()) - EBAR * 24),
        max(0.0, -float(d["D_block"].min())),
        max(0.0, float(d["D_block"].max()) - EBAR * 24),
    ]
    max_viol = float(max(viol))
    ok_bounds = max_viol <= TOL_FLOW
    checks.append(mk_check("C4_physical_bounds", ok_bounds, max_viol,
                           G_min=float(G.min()) if n else None,
                           C_min=float(C.min()), C_max=float(C.max()), EBAR=EBAR,
                           D_min=float(D.min()), D_max=float(D.max()),
                           S_min=float(S.min()), S_max=float(S.max()),
                           max_R_PV_minus_PV=float((R_PV - PV * DT).max()),
                           R_net_min=float(R_net.min()),
                           R_net_max=float(R_net.max()),
                           block_C_max=float(d["C_block"].max()),
                           block_D_max=float(d["D_block"].max()),
                           block_bound=EBAR * 24,
                           note="R<=PV*dt 的对象是物理弃光 R_PV；R_net=R_PV+R_G-H 含弃计划购电，"
                                "可超过 PV*dt（R_G 来自已接受但未消纳的计划购电）",
                           tol=TOL_FLOW))
    if not ok_bounds:
        errors.append("物理边界检查失败，最大越界 %g" % max_viol)

    # ---------- C5 列映射自检（按任务书 §4.5，与 checkpoint 的 G[0]/G[143] 抽检） ----------
    cp = json.load(open(CP_JSON, "r", encoding="utf-8"))
    cp_days = cp["days"]
    sample = [0, 100, 200, 333]
    map_dev = 0.0
    map_detail = []
    for i in sample:
        if i >= len(cp_days) or i >= n:
            map_detail.append("样本 %d 超界" % i)
            map_dev = float("inf")
            continue
        gcp = np.asarray(cp_days[i]["G"], dtype=float)
        dev0 = abs(float(G[i, 0]) - float(gcp[0]))
        dev1 = abs(float(G[i, T - 1]) - float(gcp[T - 1]))
        map_dev = max(map_dev, dev0, dev1)
        map_detail.append(dict(day=i, date=str(date_of(DAYS[i])),
                               col2_vs_G0=dev0, col145_vs_G143=dev1))
    if n and (d["dates"][0] != date(2025, 2, 1) or d["dates"][-1] != date(2025, 12, 31)):
        map_dev = float("inf")
        map_detail.append("首末日 %s / %s 不等于 2025-02-01 / 2025-12-31"
                          % (d["dates"][0], d["dates"][-1]))
    ok_map = map_dev <= TOL_BAL
    checks.append(mk_check("C5_column_mapping_col2_is_t0", ok_map, map_dev,
                           samples=map_detail,
                           note="checkpoint 仅用作任务书要求的列映射抽检参照",
                           tol=TOL_BAL))
    if not ok_map:
        errors.append("列映射自检失败：第 2 列 ≠ [0:00,0:10) 的 G[0]")

    # ---------- C6 执行层同充同放禁止 χ = Σ min(C,D) = 0 ----------
    chi_ind = float(np.minimum(C, D).sum())
    chi_blk = float(np.minimum(d["C_block"], d["D_block"]).sum())
    ok_chi = abs(chi_ind) <= TOL_CHI
    checks.append(mk_check("C6_no_simultaneous_charge_discharge", ok_chi, abs(chi_ind),
                           chi_independent_intervals=chi_ind, chi_block_level=chi_blk,
                           note="成品表2 只存 4 小时块合计；逐段 χ 由独立执行层复算给出。"
                                "块级 min(C,D)>0 不算违规：同一 4 小时块内允许不同 10 分钟段"
                                "分别充、放；χ 的物理对象是逐段动作", tol=TOL_CHI))
    if not ok_chi:
        errors.append("存在同充同放，χ=%g" % chi)

    # ---------- C7 无售电/无反送 ----------
    min_flow = float(min(G.min() if n else 0.0, C.min(), D.min(), H.min(),
                         R_PV.min(), R_G.min()))
    max_balance = max_bal_full
    backfeed = max(0.0, -min_flow, max_balance - TOL_BAL)
    ok_no_sell = backfeed <= TOL_FLOW and max_balance <= TOL_BAL
    checks.append(mk_check("C7_no_selling_no_backfeed", ok_no_sell, backfeed,
                           min_all_flows=min_flow, worst_balance_resid=max_balance,
                           note="所有流向非负且逐区间守恒；模型无售电/反送变量", tol=TOL_FLOW))
    if not ok_no_sell:
        errors.append("无售电/无反送检查失败")

    # ---------- 参考性对账（不作为独立性的来源） ----------
    annual_ref = cp.get("annual", {})
    details = {
        "J_plan_xlsx": float(np.nansum(d["day_cost"])),
        "J_plan_independent": float((P4 * G).sum()),
        "J_emg_independent_5x": emg_cost,
        "J_total_independent": float((P4 * G).sum() + emg_cost),
        "QG_xlsx": float(np.nansum(d["day_qty"])),
        "QG_independent": float(G.sum()),
        "QH_sheet3": float(sum(r["qty"] for r in got_segments)),
        "QH_independent": float(H.sum()),
        "n_emg_days_sheet3": len(set(r["date"] for r in got_segments)),
        "n_emg_segments_sheet3": len(got_segments),
        "soc_end_reported": float(d["soc_24"][-1]) if n else None,
        "soc_end_independent": float(S[-1, -1]) if n else None,
        "checkpoint_annual_reference": annual_ref,
        "recompute_vs_checkpoint_max_abs": {
            "G": float(max((np.max(np.abs(G[i] - np.asarray(cp_days[i]["G"], float)))
                            for i in range(min(n, len(cp_days)))), default=0.0)) if n else None,
            "C": float(max((np.max(np.abs(C[i] - np.asarray(cp_days[i]["C"], float)))
                            for i in range(min(n, len(cp_days)))), default=0.0)) if n else None,
            "D": float(max((np.max(np.abs(D[i] - np.asarray(cp_days[i]["D"], float)))
                            for i in range(min(n, len(cp_days)))), default=0.0)) if n else None,
            "H": float(max((np.max(np.abs(H[i] - np.asarray(cp_days[i]["H"], float)))
                            for i in range(min(n, len(cp_days)))), default=0.0)) if n else None,
        },
        "notes": [
            "独立复算只读成品 xlsx + 原始附件2/附件4；不 import 求解器。",
            "checkpoint 仅用于任务书 §4.5 要求的列映射抽检与参考性对账。",
            "表2 只存 4 小时块合计，逐段 C/D、χ、SOC 内点由独立执行层复算给出。",
            "任务书 §4.1 的单式 G+D+PV-C-R-L 未显式出现紧急购电 H 与弃计划购电 R_G；"
            "本校验器以完整物理式为准，同时按有符号净余量 R=R_PV+R_G-H 复算任务书写法。",
        ],
    }

    payload = {
        "task": "q4_validator",
        "generated_by": os.path.abspath(__file__),
        "xlsx": XLSX,
        "sources": {"attachment2": A2, "attachment4": A4, "checkpoint_reference": CP_JSON},
        "constants": {"T": T, "DT": DT, "S0": S0, "SMIN": SMIN, "SMAX": SMAX,
                      "EBAR": EBAR, "ETA": ETA, "emg_multiplier": N_EMG_MULT},
        "checks": checks,
        "errors": errors,
        "details": details,
    }

    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    for c in checks:
        print("%-52s %s  max_abs=%.6g" % (c["name"], "PASS" if c["pass"] else "FAIL", c["max_abs"]))
    print("errors:", errors if errors else "[]")
    print("wrote:", OUT_JSON)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
