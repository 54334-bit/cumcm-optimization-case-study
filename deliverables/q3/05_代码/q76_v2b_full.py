# -*- coding: utf-8 -*-
r"""7.6 全年重跑：执行器升 v2b → 重物化 ``result3_v2.xlsx``（coder 子代理）。

背景
----
mini 实验（``d=31..90``，60 天，主线 v3 层）四项判据全过：现金
``2,379,671.92 → 2,335,596.08``（−1.8522%，门槛 0.5%）、``ΣH`` −53.5%、
SOC/逐段平衡/哈希无退化，且**未用 monkey-patch**（只走公开入参 ``executor=``）。
队长据此批准把执行器由 E1 升为 v2b，本脚本做**全年重跑 + 重物化**。

口径（冻结主线，逐字不变，只把窗口换成全年 ``d=31..364``）
--------------------------------------------------------
``demand=quantile_v3, q=0.8, q_block=segment, margin=0, billing=C,
epochs=0,6,12,18, convention=slot_end``；``SOC∈[1200,10800]``、``S₀=6000``、
``λ_T=0.4720`` 全部沿用既有实现；执行器 = ``q3_exec_v2b.EXECUTORS["v2b"]``。

判据（跑前写死在文件头常量里）
------------------------------
* **Y1 收益**：全年 ``J_cash`` < 旧版 ``13,369,682.337449``（读法 C，交付件第 147 列）。
* **Y2 红线**：SOC∈[1200,10800]、逐段平衡 ≤1e-6、无售电（A/R_G 均非负）、``S₀=6000``。
* **Y3 版本**：跑前 = 跑后 7 模块聚合哈希 ``4ddf3879c220…``。
* **Y4 物化四检**：4 表结构 = 模板、表头逐格 = 模板、4h 段与逐段真值 2004/2004 全中、
  147 列全年合计可由逐段真值复现（≤1e-6 相对）、模板 sha 未变。

失效处理
--------
Y1–Y3 任一不过 ⇒ 报告首行写「**不予换版**」并停，**不物化**；Y4 不过在**候选件**上先验，
不过则不落到交付路径 —— 交付路径全程不出现不合格件。

只读 / 只写边界
---------------
* 只**读** ``7.5对话\code\*.py``、``7.6对话\代码\q76_*.py``、``output\e4\q08_m0_seg.jsonl``
  （旧版交付件的逐段真值，作对照）与附件模板；**不覆盖**旧 ``result3.xlsx``。
* 只**写** ``7.6对话\output\v2b_full\**``、``交付\Q3交付\01_提交件\result3_v2.xlsx``
  与 ``_sub\q76_v2b_full_report.md``。

复现
----
    $env:PYTHONIOENCODING='utf-8'
    python D:\CMUCU\7.6对话\code\q76_v2b_full.py run
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time

import numpy as np

# ---------------------------------------------------------------- 路径与常量
HERE = os.path.dirname(os.path.abspath(__file__))              # 7.6对话\code
ROOT76 = os.path.dirname(HERE)                                 # 7.6对话
PROJ = os.path.dirname(ROOT76)                                 # D:\CMUCU
Q75_CODE = os.path.join(PROJ, "7.5对话", "code")
OUT_DIR = os.path.join(ROOT76, "output", "v2b_full")
REPORT_PATH = os.path.join(ROOT76, "_sub", "q76_v2b_full_report.md")
DELIVER_DIR = os.path.join(ROOT76, "交付", "Q3交付", "01_提交件")
OLD_XLSX = os.path.join(DELIVER_DIR, "result3.xlsx")            # 旧版（只读对照）
NEW_XLSX = os.path.join(DELIVER_DIR, "result3_v2.xlsx")         # 本次新文件
CAND_XLSX = os.path.join(OUT_DIR, "result3_v2_candidate.xlsx")  # Y4 先在候选件上验
SEG_JSONL = os.path.join(OUT_DIR, "q76_v2b_full_seg.jsonl")     # 逐段明细（334 行）
SOLUTION_JSON = os.path.join(OUT_DIR, "q76_v2b_full_solution.json")
DAILY_CSV = os.path.join(OUT_DIR, "q76_v2b_full_daily.csv")
RESULT_JSON = os.path.join(OUT_DIR, "q76_v2b_full.json")
MAT_REPORT = os.path.join(OUT_DIR, "q76_v2b_full_materialize.json")

OLD_SEG = os.path.join(ROOT76, "output", "e4", "q08_m0_seg.jsonl")   # 旧版逐段真值
TPL_XLSX = os.path.join(PROJ, "赛题", "C题", "附件", "附件5", "result3.xlsx")
PRICE_CSV = os.path.join(PROJ, "B对话", "clean", "q1_clean.csv")

# ---------------------------------------------------------------- 冻结判据常量
HASH_FILES = (
    "q3_main_v2.py",
    "q3_solver.py",
    "q3_solver_billingC.py",
    "q3_demand_quantile.py",
    "q3_pv_interp.py",
    "q3_data_io.py",
    "q3_solver_risk.py",
)
EXPECTED_AGG_PREFIX = "4ddf3879c220"          # 主台账同代次（见 exp/q75_g2_manifest.jsonl）
OLD_J_CASH = 13369682.337448763               # 旧版交付件第 147 列全年合计（元，读法 C）
Y1_TOL_ABS = 1e-6                             # 基线同源对拍容差（元）
TOL_BAL = 1e-6                                # Y2 逐段平衡残差上限
SOC_LO, SOC_HI = 1200.0, 10800.0
SOC_TOL = 1e-6
S0_REF = 6000.0
Y4_REL_TOL = 1e-6                             # Y4 列合计复现相对容差
Y4_ABS_TOL = 1e-6                             # Y4 分块/结构容差
TPL_SHA_EXPECTED = ("c59da470cabd0be23f602c95c8aa9d11ec224a0cdac216b3e1f218e65d006bdc")

# 口径常量（与 q76_v2b_mini.py / 主线冻结集逐字一致）
DT = 1.0 / 6.0
D0, D1 = 31, 364                              # 全年窗口：334 天
EPOCHS_USE = (0, 6, 12, 18)
MARGIN = 0.0
FROZEN_CFG = dict(billing="C", demand="quantile_v3", q=0.8,
                  q_block="segment", convention="slot_end")
BLOCK_SEG = 24                                # 表 2 的「指定时间段」= 4 小时 = 24 段
SEG_PER_DAY = 144

DAY_KEYS = ("J_plan", "J_adj", "J_emg", "J_cash", "QG0", "QA", "QH", "QC", "QD",
            "QL", "QPV", "QR_PV", "QR_G", "QGm", "QGp")
SUM_KEYS = ("G0", "A", "C", "D", "H", "R_PV", "R_G")
#: 新版 ``DAY_KEYS`` 累加量 → 旧版逐段真值的数组字段（新旧对照表用）
OLD_KEY_MAP = {"QG0": "G0", "QA": "A", "QH": "H", "QC": "C", "QD": "D",
               "QR_PV": "R_PV", "QR_G": "R_G"}

if Q75_CODE not in sys.path:
    sys.path.insert(0, Q75_CODE)

import q3_exec_v2b as X                                        # noqa: E402 只读引用
import q3_main_v2 as M                                         # noqa: E402 只读引用
from q3_data_io import (ETA, LAM_T, S0, load_forecast,        # noqa: E402,F401
                        load_load_pv, load_prices)


# ---------------------------------------------------------------- 通用工具
def sha256_of(path) -> str:
    """文件 SHA-256（分块读；缺文件返回 ``missing``）。"""
    if not os.path.isfile(path):
        return "missing"
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def agg_hash() -> dict:
    """7 模块聚合哈希（``"名字:sha256\\n"`` 依固定文件序拼接后再 SHA-256）。"""
    per = {name: sha256_of(os.path.join(Q75_CODE, name)) for name in HASH_FILES}
    agg = hashlib.sha256(
        "".join(f"{k}:{v}\n" for k, v in per.items()).encode("utf-8")).hexdigest()
    return {"per_file": per, "agg": agg, "prefix": agg[:12],
            "matches_expected": agg[:12] == EXPECTED_AGG_PREFIX}


def ensure_dir(path: str) -> None:
    """建目录（幂等）。"""
    os.makedirs(path, exist_ok=True)


def write_json(path: str, obj) -> None:
    """UTF-8 JSON 落盘（缩进 1，与主线 ``--out`` 风格一致）。"""
    ensure_dir(os.path.dirname(os.path.abspath(path)))
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1, default=float)
    print(f"  已落盘 {path}", flush=True)


def load_data():
    """按主线口径读附件 2（实际负荷/光伏）、附件 4（电价）、附件 3（预报）。"""
    L, P, days = load_load_pv()
    price = load_prices()
    fc = load_forecast()
    return L, P, price, fc, days


def cash_split(G0, A, H, price) -> dict:
    """读法 C 的逐段现金分解（与交付件第 147 列同式）。

    ``J_plan = Σ p·min(G⁰,A)``、``J_adj = Σ[0.5p(G⁰−A)⁺ + 1.5p(A−G⁰)⁺]``、
    ``J_emg = Σ5pH``、``J_cash = J_plan + J_adj + J_emg``。
    """
    G0 = np.asarray(G0, dtype=float)
    A = np.asarray(A, dtype=float)
    H = np.asarray(H, dtype=float)
    price = np.asarray(price, dtype=float)
    down = np.maximum(G0 - A, 0.0)
    up = np.maximum(A - G0, 0.0)
    j_plan = float(np.sum(price * np.minimum(G0, A)))
    j_adj = float(np.sum(0.5 * price * down + 1.5 * price * up))
    j_emg = float(np.sum(5.0 * price * H))
    return {"J_plan": j_plan, "J_adj": j_adj, "J_emg": j_emg,
            "J_cash": j_plan + j_adj + j_emg}


# ---------------------------------------------------------------- 旧版逐段真值
def load_old_truth() -> dict:
    """读旧版交付件的逐段真值（``output\\e4\\q08_m0_seg.jsonl``，只读）。

    Returns
    -------
    dict：逐日记录的原始数组 + 全年累加（``totals``）+ 读法 C 现金分解
    （``cash``）+ ``soc_min/soc_max/S_end``。
    """
    with open(OLD_SEG, "r", encoding="utf-8") as fh:
        recs = [json.loads(line) for line in fh if line.strip()]
    tot = {k: 0.0 for k in SUM_KEYS}
    tot_day = {k: 0.0 for k in DAY_KEYS}
    cash = {"J_plan": 0.0, "J_adj": 0.0, "J_emg": 0.0, "J_cash": 0.0}
    soc_lo, soc_hi = float("inf"), -float("inf")
    return_ = {"rows": recs, "n_days": len(recs),
               "date_first": recs[0]["date"], "date_last": recs[-1]["date"]}
    for r in recs:
        for k in SUM_KEYS:
            tot[k] += float(np.sum(np.asarray(r[k], dtype=float)))
        G0 = np.asarray(r["G0"], dtype=float)
        A = np.asarray(r["A"], dtype=float)
        tot_day["QGm"] += float(np.maximum(G0 - A, 0.0).sum())
        tot_day["QGp"] += float(np.maximum(A - G0, 0.0).sum())
        S = np.asarray(r["S"], dtype=float)[1:]
        soc_lo = min(soc_lo, float(S.min()))
        soc_hi = max(soc_hi, float(S.max()))
    for k, src in OLD_KEY_MAP.items():
        tot_day[k] = tot[src]
    return_.update(totals=tot, soc_min=soc_lo, soc_max=soc_hi,
                   totals_day=tot_day,
                   S_end=float(np.asarray(recs[-1]["S"], dtype=float)[-1]),
                   S_first=float(np.asarray(recs[0]["S"], dtype=float)[0]))
    return return_


def old_cash(price) -> dict:
    """旧版逐段真值 × 附件 1 电价 ⇒ 读法 C 现金分解（与交付件第 147 列对拍用）。"""
    with open(OLD_SEG, "r", encoding="utf-8") as fh:
        recs = [json.loads(line) for line in fh if line.strip()]
    acc = {"J_plan": 0.0, "J_adj": 0.0, "J_emg": 0.0, "J_cash": 0.0}
    for r in recs:
        c = cash_split(r["G0"], r["A"], r["H"], price)
        for k in acc:
            acc[k] += c[k]
    return acc


# ---------------------------------------------------------------- 单日/全年执行
def _one_day(arm: str, L, P, price, fc, days, d, s):
    """跑一天：``E1`` 走主线 ``q3_main_v2.run_day_v2``；``v2b`` 走公开 ``executor=``。"""
    if arm == "E1":
        return M.run_day_v2(L, P, price, fc, days, d, epochs=EPOCHS_USE, s_init=s,
                            lam=LAM_T, mmap=None, margin=None, risk=False,
                            **FROZEN_CFG)
    return X.run_day(L, P, price, fc, days, d, X.EXECUTORS["v2b"], billing="C",
                     demand="quantile_v3", q=0.8, q_block="segment",
                     margin=MARGIN, s_init=s, epochs=EPOCHS_USE, lam=LAM_T,
                     convention="slot_end")


def run_arm(arm: str, L, P, price, fc, days, d0=D0, d1=D1) -> dict:
    """全年逐日滚动跑一条臂（自己控链，便于逐段留证）。

    Returns
    -------
    dict：``ok=True`` 时含 ``totals``（累加）、``rows``（逐日标量）、``seg``
    （逐日逐段明细，直接可作物化输入）、``max_balance_res``（Y2）、
    ``soc_min/soc_max``、``S_first/S_end`` 与执行器自检量上限。
    """
    s = float(S0)
    tot = {k: 0.0 for k in DAY_KEYS}
    rows: list = []
    seg: list = []
    mx_bal = mx_chi_exec = mx_rgv = mx_hr = 0.0
    min_a = min_rg = min_rpv = min_h = min_c = min_d = float("inf")
    soc_lo, soc_hi = float("inf"), -float("inf")
    s_first = None
    t0 = time.time()
    for d in range(d0, d1 + 1):
        Ld, Pd = L[d], P[d]
        res = _one_day(arm, L, P, price, fc, days, d, s)
        if not res.get("ok"):
            return {"arm": arm, "ok": False, "d": int(d), "reason": res.get("reason"),
                    "rows": rows, "seg": seg}
        A = np.asarray(res["A"], dtype=float)
        G0 = np.asarray(res["G0"], dtype=float)
        Cx = np.asarray(res["C"], dtype=float)
        Dx = np.asarray(res["D"], dtype=float)
        H = np.asarray(res["H"], dtype=float)
        R_PV = np.asarray(res["R_PV"], dtype=float)
        R_G = np.asarray(res["R_G"], dtype=float)
        S = np.asarray(res["S"], dtype=float)
        # Y2 逐段平衡：A + PV·dt + D + H = L·dt + C + R_PV + R_G
        bal = A + Pd * DT + Dx + H - (Ld * DT + Cx + R_PV + R_G)
        bal_mx = float(np.max(np.abs(bal))) if bal.size else 0.0
        mx_bal = max(mx_bal, bal_mx)
        mx_chi_exec = max(mx_chi_exec, float(np.max(np.minimum(Cx, Dx))))
        mx_rgv = max(mx_rgv, float(np.max(R_G - A)))
        mx_hr = max(mx_hr, float(np.max(H * (R_PV + R_G))))
        min_a = min(min_a, float(A.min()))
        min_rg = min(min_rg, float(R_G.min()))
        min_rpv = min(min_rpv, float(R_PV.min()))
        min_h = min(min_h, float(H.min()))
        min_c = min(min_c, float(Cx.min()))
        min_d = min(min_d, float(Dx.min()))
        S_hi = S[1:]
        soc_lo = min(soc_lo, float(S_hi.min()))
        soc_hi = max(soc_hi, float(S_hi.max()))
        if s_first is None:
            s_first = float(S[0])
        rows.append({
            "d": int(d), "date": res["date"], "arm": arm,
            "s_init": float(s), "S_end": float(res["S_end"]),
            "J_plan": float(res["J_plan"]), "J_adj": float(res["J_adj"]),
            "J_emg": float(res["J_emg"]), "J_cash": float(res["J_cash"]),
            "QG0": float(res["QG0"]), "QA": float(A.sum()), "QH": float(res["QH"]),
            "QC": float(Cx.sum()), "QD": float(Dx.sum()),
            "QL": float((Ld * DT).sum()), "QPV": float((Pd * DT).sum()),
            "QGm": float(np.maximum(G0 - A, 0.0).sum()),
            "QGp": float(np.maximum(A - G0, 0.0).sum()),
            "QR_PV": float(res["QR_PV"]), "QR_G": float(res["QR_G"]),
            "soc_min": float(S_hi.min()), "soc_max": float(S_hi.max()),
            "balance_max_res": bal_mx,
            "plan_max_res": float(res.get("plan_max_res", float("nan"))),
            "n_pv_missing": int(res.get("n_pv_missing", -1)),
        })
        seg.append({"d": int(d), "date": res["date"],
                    "G0": G0.tolist(), "A": A.tolist(), "C": Cx.tolist(),
                    "D": Dx.tolist(), "S": S.tolist(), "H": H.tolist(),
                    "R_PV": R_PV.tolist(), "R_G": R_G.tolist()})
        for k in DAY_KEYS:
            tot[k] += float(rows[-1][k])
        s = float(res["S_end"])
        if (d - d0 + 1) % 50 == 0:
            print(f"    [{arm}] d={d} J_cash={tot['J_cash']:,.2f} S={s:,.2f}",
                  flush=True)
    return {
        "arm": arm, "ok": True, "d0": d0, "d1": d1, "n_days": len(rows),
        "totals": tot, "rows": rows, "seg": seg,
        "max_balance_res": mx_bal, "max_chi_exec": mx_chi_exec,
        "max_RG_viol": mx_rgv, "max_HR": mx_hr,
        "min_A": min_a, "min_R_G": min_rg, "min_R_PV": min_rpv,
        "min_H": min_h, "min_C": min_c, "min_D": min_d,
        "soc_min": float(soc_lo), "soc_max": float(soc_hi),
        "s_first": float(s_first if s_first is not None else S0),
        "S_end": float(s), "runtime_sec": round(time.time() - t0, 1),
    }


def write_seg_jsonl(path: str, seg_records) -> None:
    """逐段明细落 JSONL（每天一行，144 段数组；``repr`` 浮点可逐位往返）。"""
    ensure_dir(os.path.dirname(os.path.abspath(path)))
    with open(path, "w", encoding="utf-8") as fh:
        for rec in seg_records:
            fh.write(json.dumps(rec, ensure_ascii=False))
            fh.write("\n")
    print(f"  已落盘 {path}（{len(seg_records)} 行）", flush=True)


# ---------------------------------------------------------------- Y4 物化与四检
def materialize(seg_path: str, solution_path: str, out_xlsx: str) -> dict:
    """调用 ``q76_materialize.py``（内含 BLOCK=24 覆盖）物化到候选路径。"""
    if os.path.abspath(out_xlsx) == os.path.abspath(OLD_XLSX):
        raise ValueError("拒绝写入旧版交付件 result3.xlsx")
    sys.path.insert(0, HERE)
    import q76_materialize as MAT                            # noqa: E402
    rep = MAT.run(seg_path, solution_path, out_xlsx, template=TPL_XLSX,
                  price_csv=PRICE_CSV, reading="C", force=True)
    write_json(MAT_REPORT, rep)
    return rep


def _expect_rows(sheet: str, n_days: int):
    """物化件每张表的**期望数据行数**（``None`` = 结构上不固定）。"""
    if "计划购电" in sheet or "调整购电" in sheet:
        return n_days
    if "充放电" in sheet:
        return n_days * (SEG_PER_DAY // BLOCK_SEG)
    if "紧急" in sheet:
        return None                     # 紧急购电行数 = 合并后的段数，不固定
    return None


def y4_checks(xlsx: str, tpl: str, seg_records, price) -> dict:
    """Y4 物化四检：结构 / 表头 / 4h 分块 / 147 列合计（模板 sha 另计）。

    结构口径：表名与顺序 = 模板、每表**列数** = 模板、两张主表（``*购电量``）
    数据行数 = 334；模板里的「充放电量」「紧急购电量」只给样例行（26/11 行），
    数据行数以逐段真值为准，故不与模板比行数（分开记 ``rows_match``）。
    """
    from openpyxl import load_workbook
    wb = load_workbook(xlsx, read_only=True, data_only=True)
    wt = load_workbook(tpl, read_only=True, data_only=True)
    sn, sn_t = list(wb.sheetnames), list(wt.sheetnames)
    # 主表（147 列）= 计划购电量 / 调整购电量；「紧急购电量」只有 3 列，不走列合计口径
    main_sheets = [s for s in sn if "购电量" in s and wb[s].max_column >= 147]
    struct = []
    ok_struct = (sn == sn_t)
    for s in sn:
        dim_o = (wb[s].max_row, wb[s].max_column)
        dim_t = (wt[s].max_row, wt[s].max_column) if s in sn_t else None
        exp = _expect_rows(s, len(seg_records))
        # 列数必须逐表相等；行数只在「模板本身就带满行」时与模板比
        # （模板的充放电量/紧急购电量只有样例行 26/11，行数以逐段真值为准）
        cols_ok = bool(dim_t and dim_o[1] == dim_t[1])
        rows_ok = bool(dim_t and dim_o[0] == dim_t[0])
        rows_enforced = bool(exp is not None and dim_t and dim_t[0] == exp + 1)
        ok_struct = ok_struct and cols_ok and (rows_ok if rows_enforced else True)
        struct.append({"sheet": s, "out": list(dim_o),
                       "template": list(dim_t) if dim_t else None,
                       "cols_match": cols_ok,
                       "rows_match": rows_ok,
                       "rows_enforced": rows_enforced,
                       "data_rows": dim_o[0] - 1,
                       "data_rows_expect": exp})
    for x in struct:
        exp = x["data_rows_expect"]
        x["data_rows_ok"] = bool(exp is None or x["data_rows"] == exp)
    ok_struct = ok_struct and all(x["data_rows_ok"] for x in struct)
    hdr = []
    ok_hdr = True
    for s in sn:
        if s not in sn_t:
            ok_hdr = False
            continue
        r_o = next(wb[s].iter_rows(min_row=1, max_row=1, values_only=True))
        r_t = next(wt[s].iter_rows(min_row=1, max_row=1, values_only=True))
        same = (list(r_o) == list(r_t))
        ok_hdr = ok_hdr and same
        if not same:
            diff = [(i, a, b) for i, (a, b) in enumerate(zip(r_o, r_t)) if a != b]
            hdr.append({"sheet": s, "match": False, "diff_head": diff[:10]})
    # ---- 4h 段（24 段）分块 vs 逐段真值 ----
    sheet_soc = next((s for s in sn if "充放电" in s), None)
    blk = {"sheet": sheet_soc, "n_blocks": 0, "charge_hit": 0, "discharge_hit": 0,
           "max_abs_diff_charge": 0.0, "max_abs_diff_discharge": 0.0}
    ok_blk = False
    if sheet_soc:
        rows = [r for r in wb[sheet_soc].iter_rows(min_row=2, values_only=True)]
        n_per_day = SEG_PER_DAY // BLOCK_SEG
        n_blk = len(seg_records) * n_per_day
        blk["n_blocks"] = n_blk
        ok_rows = (len(rows) == n_blk)
        for di, day in enumerate(seg_records):
            C = np.asarray(day["C"], dtype=float)
            D = np.asarray(day["D"], dtype=float)
            for b in range(n_per_day):
                got_c = rows[di * n_per_day + b][2]
                got_d = rows[di * n_per_day + b][3]
                got_c = 0.0 if got_c is None else float(got_c)
                got_d = 0.0 if got_d is None else float(got_d)
                exp_c = float(C[BLOCK_SEG * b:BLOCK_SEG * b + BLOCK_SEG].sum())
                exp_d = float(D[BLOCK_SEG * b:BLOCK_SEG * b + BLOCK_SEG].sum())
                dc, dd = abs(got_c - exp_c), abs(got_d - exp_d)
                blk["max_abs_diff_charge"] = max(blk["max_abs_diff_charge"], dc)
                blk["max_abs_diff_discharge"] = max(blk["max_abs_diff_discharge"], dd)
                blk["charge_hit"] += int(dc <= Y4_ABS_TOL)
                blk["discharge_hit"] += int(dd <= Y4_ABS_TOL)
        blk["charge_all_hit"] = bool(blk["charge_hit"] == n_blk)
        blk["discharge_all_hit"] = bool(blk["discharge_hit"] == n_blk)
        blk["rows_match"] = bool(ok_rows)
        ok_blk = bool(blk["charge_all_hit"] and blk["discharge_all_hit"] and ok_rows)
    # ---- 147 列全年合计 vs 逐段真值（读法 C）----
    cash = {"J_plan": 0.0, "J_adj": 0.0, "J_emg": 0.0, "J_cash": 0.0}
    for day in seg_records:
        c = cash_split(day["G0"], day["A"], day["H"], price)
        for k in cash:
            cash[k] += c[k]
    col = []
    ok_col = True
    for s in main_sheets:
        tot = 0.0
        for r in wb[s].iter_rows(min_row=2, values_only=True):
            if r[146] is not None:
                tot += float(r[146])
        rel = abs(tot - cash["J_cash"]) / abs(cash["J_cash"])
        col.append({"sheet": s, "sum_col147": tot, "truth_J_cash": cash["J_cash"],
                    "abs_diff": abs(tot - cash["J_cash"]), "rel_diff": rel,
                    "pass": bool(rel <= Y4_REL_TOL)})
        ok_col = ok_col and (rel <= Y4_REL_TOL)
    # ---- 无售电（物化件逐格非负）----
    neg = {"n_cells": 0, "min_value": float("inf"), "sheets": []}
    for s in main_sheets:
        m = float("inf")
        bad = 0
        for r in wb[s].iter_rows(min_row=2, values_only=True):
            for v in r[2:146]:
                if v is None:
                    continue
                fv = float(v)
                m = min(m, fv)
                if fv < -Y4_ABS_TOL:
                    bad += 1
        neg["n_cells"] += bad
        neg["min_value"] = min(neg["min_value"], m)
        neg["sheets"].append({"sheet": s, "min": m, "neg_cells": bad})
    neg["pass"] = bool(neg["n_cells"] == 0)
    wb.close()
    wt.close()
    return {
        "struct": {"pass": bool(ok_struct), "sheets_out": sn, "sheets_template": sn_t,
                   "per_sheet": struct},
        "header": {"pass": bool(ok_hdr), "diffs": hdr},
        "block4h": blk, "col147": {"pass": bool(ok_col), "per_sheet": col,
                                   "truth_cash": cash},
        "no_selling_xlsx": neg,
        "all_pass": bool(ok_struct and ok_hdr and ok_blk and ok_col),
    }


# ---------------------------------------------------------------- 判据
def verdicts(v2b: dict, old_t: dict, old_c: dict, h_before: dict, h_after: dict,
             e1: dict | None) -> dict:
    """Y1–Y3 逐条判定（阈值全部在文件头常量里，跑前写死）。"""
    j_new = float(v2b["totals"]["J_cash"])
    gain = (OLD_J_CASH - j_new) / OLD_J_CASH
    y1 = {"name": "Y1 收益", "pass": bool(j_new < OLD_J_CASH),
          "J_cash_new": j_new, "J_cash_old": OLD_J_CASH,
          "gain_pct": round(gain * 100.0, 4),
          "criterion": "全年 J_cash(v2b) < 旧版 13,369,682.337449（读法 C）"}
    soc_ok = (v2b["soc_min"] >= SOC_LO - SOC_TOL) and (v2b["soc_max"] <= SOC_HI + SOC_TOL)
    nosell_ok = (v2b["min_A"] >= -Y4_ABS_TOL) and (v2b["min_R_G"] >= -Y4_ABS_TOL) \
        and (v2b["min_R_PV"] >= -Y4_ABS_TOL) and (v2b["min_H"] >= -Y4_ABS_TOL) \
        and (v2b["min_C"] >= -Y4_ABS_TOL) and (v2b["min_D"] >= -Y4_ABS_TOL)
    s0_ok = abs(v2b["s_first"] - S0_REF) <= SOC_TOL
    y2 = {"name": "Y2 红线",
          "pass": bool(soc_ok and (v2b["max_balance_res"] <= TOL_BAL)
                       and nosell_ok and s0_ok),
          "soc_min": v2b["soc_min"], "soc_max": v2b["soc_max"],
          "soc_band": [SOC_LO, SOC_HI], "soc_in_band": bool(soc_ok),
          "max_balance_res": v2b["max_balance_res"], "tol": TOL_BAL,
          "no_selling": {"pass": bool(nosell_ok), "min_A": v2b["min_A"],
                         "min_R_G": v2b["min_R_G"], "min_R_PV": v2b["min_R_PV"],
                         "min_H": v2b["min_H"], "min_C": v2b["min_C"],
                         "min_D": v2b["min_D"]},
          "S0": v2b["s_first"], "S0_ref": S0_REF, "S0_ok": bool(s0_ok)}
    same = h_before["agg"] == h_after["agg"]
    changed = sorted(k for k in HASH_FILES
                     if h_before["per_file"][k] != h_after["per_file"][k])
    y3 = {"name": "Y3 版本",
          "pass": bool(same and h_after["matches_expected"] and not changed),
          "agg_before": h_before["agg"], "agg_after": h_after["agg"],
          "prefix_before": h_before["prefix"], "prefix_after": h_after["prefix"],
          "expected_prefix": EXPECTED_AGG_PREFIX,
          "matches_expected": h_after["matches_expected"],
          "hash_changed_files": changed}
    base = None
    if e1 is not None and e1.get("ok"):
        d = abs(float(e1["totals"]["J_cash"]) - float(old_t["cash"]["J_cash"]))
        base = {"E1_rerun_J_cash": float(e1["totals"]["J_cash"]),
                "old_truth_J_cash": float(old_t["cash"]["J_cash"]),
                "abs_diff": d, "pass": bool(d <= Y1_TOL_ABS),
                "old_delivered_J_cash": OLD_J_CASH,
                "old_delivered_diff": abs(OLD_J_CASH - float(old_t["cash"]["J_cash"])),
                "old_cash_split": old_c,
                "E1_rerun_totals": e1["totals"]}
    return {"Y1": y1, "Y2": y2, "Y3": y3, "baseline_same_source": base,
            "pre_materialize_pass": bool(y1["pass"] and y2["pass"] and y3["pass"])}


# ---------------------------------------------------------------- 报告
def _fmt(x, nd=2):
    """千分位格式化（输入可空）。"""
    return "n/a" if x is None else f"{float(x):,.{nd}f}"


def render_report(payload: dict) -> str:
    """把结果渲染成 ``_sub`` 报告（Markdown，数字全部来自 payload）。"""
    v = payload["verdicts"]
    v2b, e1 = payload["arms"].get("v2b"), payload["arms"].get("E1")
    old_t, old_c = payload["old_truth"], payload["old_cash"]
    y4 = payload.get("y4")
    all_pass = bool(v["pre_materialize_pass"] and y4 and y4["all_pass"])
    L = []
    A = L.append
    A(f"**{'结论：准予换版（result3_v2.xlsx 已产出）' if all_pass else '不予换版'}**")
    A("")
    A("# q76_v2b_full（coder 子代理）—— 执行器升 v2b：全年重跑 + 重物化 result3_v2")
    A("")
    A(f"> 窗口 `d={v2b['d0']}..{v2b['d1']}`（{v2b['n_days']} 天）；口径 "
      "`demand=quantile_v3, q=0.8, q_block=segment, margin=0, billing=C, "
      "epochs=0,6,12,18, convention=slot_end`；执行器 "
      "`q3_exec_v2b.EXECUTORS[\"v2b\"]`（公开入参，未 monkey-patch）")
    A(f"> 代码代次（7 模块聚合 SHA-256）：`{v['Y3']['prefix_after']}`"
      f"（期望 `{EXPECTED_AGG_PREFIX}`）")
    A("")
    A("## 一、判据逐条")
    A("")
    A("| 判据 | 通过条件 | 实测 | 判定 |")
    A("| --- | --- | --- | --- |")
    A(f"| Y1 收益 | 全年 `J_cash` < `{_fmt(OLD_J_CASH, 2)}`（旧版交付件） | "
      f"`{_fmt(v['Y1']['J_cash_new'], 6)}` vs `{_fmt(OLD_J_CASH, 6)}`"
      f"（降幅 **{v['Y1']['gain_pct']:.4f}%**） | "
      f"**{'PASS' if v['Y1']['pass'] else 'FAIL'}** |")
    A(f"| Y2 红线（SOC） | 全程 ∈[1200,10800] | "
      f"`[{v['Y2']['soc_min']:.6f}, {v['Y2']['soc_max']:.6f}]` | "
      f"**{'PASS' if v['Y2']['soc_in_band'] else 'FAIL'}** |")
    A(f"| Y2 红线（平衡） | 逐段残差 ≤1e-6 | `{v['Y2']['max_balance_res']:.3e}` | "
      f"**{'PASS' if v['Y2']['max_balance_res'] <= TOL_BAL else 'FAIL'}** |")
    A(f"| Y2 红线（无售电） | `A/R_G/R_PV/H/C/D` 逐段非负 | min "
      f"`A={v['Y2']['no_selling']['min_A']:.3e}`、`R_G="
      f"{v['Y2']['no_selling']['min_R_G']:.3e}`、`R_PV="
      f"{v['Y2']['no_selling']['min_R_PV']:.3e}`、`H="
      f"{v['Y2']['no_selling']['min_H']:.3e}` | "
      f"**{'PASS' if v['Y2']['no_selling']['pass'] else 'FAIL'}** |")
    A(f"| Y2 红线（S₀） | 起始 SOC = 6000 | `{v['Y2']['S0']:.6f}` | "
      f"**{'PASS' if v['Y2']['S0_ok'] else 'FAIL'}** |")
    A(f"| Y3 版本 | 跑前 = 跑后 7 模块聚合哈希 `{EXPECTED_AGG_PREFIX}…` | 跑前 "
      f"`{v['Y3']['prefix_before']}` / 跑后 `{v['Y3']['prefix_after']}`，变动文件 "
      f"`{v['Y3']['hash_changed_files']}` | "
      f"**{'PASS' if v['Y3']['pass'] else 'FAIL'}** |")
    if y4:
        A(f"| Y4 物化 表结构 = 模板 | 4 表名 + 尺寸逐张相等 | "
          f"`{[str(x['out']) for x in y4['struct']['per_sheet']]}` vs 模板 "
          f"`{[str(x['template']) for x in y4['struct']['per_sheet']]}` | "
          f"**{'PASS' if y4['struct']['pass'] else 'FAIL'}** |")
        A(f"| Y4 物化 表头逐格 = 模板 | 4 表表头逐格相等 | 差异项 "
          f"`{len(y4['header']['diffs'])}` | "
          f"**{'PASS' if y4['header']['pass'] else 'FAIL'}** |")
        b = y4["block4h"]
        A(f"| Y4 物化 4h 段 | 与逐段真值 2004/2004 全中 | 充电 "
          f"`{b['charge_hit']}/{b['n_blocks']}`（max diff "
          f"`{b['max_abs_diff_charge']:.3e}`）、放电 "
          f"`{b['discharge_hit']}/{b['n_blocks']}`（max diff "
          f"`{b['max_abs_diff_discharge']:.3e}`） | "
          f"**{'PASS' if (b['charge_all_hit'] and b['discharge_all_hit']) else 'FAIL'}** |")
        worst = max(y4["col147"]["per_sheet"], key=lambda x: x["rel_diff"])
        A(f"| Y4 物化 147 列合计 | 由逐段真值复现 ≤1e-6 相对 | 最大相对差 "
          f"`{worst['rel_diff']:.3e}`（表 `{worst['sheet']}`："
          f"`{_fmt(worst['sum_col147'], 6)}` vs 真值 "
          f"`{_fmt(worst['truth_J_cash'], 6)}`） | "
          f"**{'PASS' if y4['col147']['pass'] else 'FAIL'}** |")
        A(f"| Y4 模板 sha 未变 | 附件 5 sha256 = 冻结值 | "
          f"`{payload['template_sha_after'][:16]}…` | "
          f"**{'PASS' if payload['template_sha_unchanged'] else 'FAIL'}** |")
        A(f"| Y4 物化件无售电 | 计划/调整表 2..146 列逐格非负 | 负值格数 "
          f"`{y4['no_selling_xlsx']['n_cells']}`，min "
          f"`{y4['no_selling_xlsx']['min_value']:.6f}` | "
          f"**{'PASS' if y4['no_selling_xlsx']['pass'] else 'FAIL'}** |")
    else:
        A("| Y4 物化 | Y1–Y3 未全过 ⇒ 未物化 | — | **N/A** |")
    if y4:
        A("")
        A("> Y4 表结构口径：表名与顺序、每表**列数**必须与模板逐张相等，两张购电量主表"
          "数据行数必须 = 334；模板里的「充放电量」「紧急购电量」只有样例行（26/11 行），"
          "其数据行数以逐段真值为准（2004 = 334×6；紧急购电 = 合并后实际发生段数），"
          "故不与模板比行数。")
    A("")
    A(f"**总体：{'Y1–Y4 全部通过' if all_pass else '存在未通过判据 ⇒ 不予换版'}。**")
    A("")
    A("## 二、新旧对照（全年 334 天累加）")
    A("")
    A("| 指标 | 旧版 = E1（交付件逐段真值） | 新版 = v2b | 差（新−旧） | 相对 |")
    A("| --- | ---: | ---: | ---: | ---: |")
    rows = [("J_plan（元）", "J_plan", 2), ("J_adj（元）", "J_adj", 2),
            ("J_emg（元）", "J_emg", 2), ("J_cash（元）", "J_cash", 2),
            ("ΣH（kWh）", "QH", 3), ("ΣG⁰（kWh）", "QG0", 3), ("ΣA（kWh）", "QA", 3),
            ("ΣC（执行充电，kWh）", "QC", 3), ("ΣD（执行放电，kWh）", "QD", 3),
            ("ΣR_PV（弃光，kWh）", "QR_PV", 3), ("ΣR_G（弃购电，kWh）", "QR_G", 3),
            ("Σ(G⁰−A)⁺（kWh）", "QGm", 3), ("Σ(A−G⁰)⁺（kWh）", "QGp", 3)]
    for label, key, nd in rows:
        if key in ("J_plan", "J_adj", "J_emg", "J_cash"):
            x = float(old_c[key])
        else:
            x = float(old_t["totals_day"][key])
        y = float(v2b["totals"][key])
        rel = f"{(y - x) / x * 100.0:+.4f}%" if x else "n/a"
        A(f"| {label} | {_fmt(x, nd)} | {_fmt(y, nd)} | {y - x:+,.{nd}f} | {rel} |")
    A(f"| SOC 区间（kWh） | [{old_t['soc_min']:.6f}, {old_t['soc_max']:.6f}] | "
      f"[{v2b['soc_min']:.6f}, {v2b['soc_max']:.6f}] | — | — |")
    A(f"| 期末 SOC S_end（kWh） | {old_t['S_end']:.6f} | {v2b['S_end']:.6f} | "
      f"{v2b['S_end'] - old_t['S_end']:+.6f} | — |")
    A("")
    A("收益来源：`ΔJ_cash = ΔJ_plan "
      f"{float(v2b['totals']['J_plan']) - float(old_c['J_plan']):+,.2f} + ΔJ_adj "
      f"{float(v2b['totals']['J_adj']) - float(old_c['J_adj']):+,.2f} + ΔJ_emg "
      f"{float(v2b['totals']['J_emg']) - float(old_c['J_emg']):+,.2f}`；"
      f"紧急电 `ΣH` 从 {_fmt(old_t['totals_day']['QH'], 1)} kWh 降到 "
      f"{_fmt(v2b['totals']['QH'], 1)} kWh"
      f"（{float(v2b['totals']['QH']) / float(old_t['totals_day']['QH']) - 1.0:+.2%}）。")
    if v["baseline_same_source"]:
        b = v["baseline_same_source"]
        A("")
        A(f"**基线同源复核**：本次重跑 E1 臂全年 `J_cash="
          f"{b['E1_rerun_J_cash']:.6f}`，旧版逐段真值 `J_cash="
          f"{b['old_truth_J_cash']:.6f}`（差 `{b['abs_diff']:.3e}`）、交付件第 147 列 "
          f"`{b['old_delivered_J_cash']:.6f}`（差 `{b['old_delivered_diff']:.3e}`）"
          f" ⇒ **{'一致' if b['pass'] else '不一致'}**"
          "（说明旧版 = 同一代码代次下的 E1，新旧唯一差别是执行器）。")
    if e1 is not None:
        A("")
        A("自检量（逐段口径，最大值）")
        A("")
        A("| 量 | 旧版 E1（重跑） | 新版 v2b |")
        A("| --- | ---: | ---: |")
        A(f"| 逐段平衡最大残差 | {e1['max_balance_res']:.3e} | "
          f"{v2b['max_balance_res']:.3e} |")
        A(f"| 执行器同充同放 max min(C,D) | {e1['max_chi_exec']:.3e} | "
          f"{v2b['max_chi_exec']:.3e} |")
        A(f"| R_G − A 最大值（应为 ≤0） | {e1['max_RG_viol']:.3e} | "
          f"{v2b['max_RG_viol']:.3e} |")
        A(f"| H·(R_PV+R_G) 最大值（应为 0） | {e1['max_HR']:.3e} | "
          f"{v2b['max_HR']:.3e} |")
        A(f"| 运行时间（s） | {e1['runtime_sec']} | {v2b['runtime_sec']} |")
    A("")
    A("## 三、产物与哈希")
    A("")
    out_sha = payload.get("new_xlsx_sha256")
    A(f"- 新交付件：`{NEW_XLSX}`")
    A(f"  - sha256 `{out_sha}`，字节 {payload.get('new_xlsx_bytes')}")
    if y4:
        A(f"- 候选件（Y4 先验用）：`{CAND_XLSX}`，sha256 "
          f"`{payload.get('candidate_sha256')}`"
          f"（与交付件一致：{payload.get('candidate_equals_delivery')}）")
    A(f"- 逐段明细：`{SEG_JSONL}`（{v2b['n_days']} 天 × 144 段）")
    A(f"- 解法 JSON：`{SOLUTION_JSON}`")
    A(f"- 物化报告：`{MAT_REPORT}`")
    A(f"- 判定 JSON：`{RESULT_JSON}`")
    d = payload.get("y4_delivery")
    if d:
        b = d["block4h"]
        A("- **交付件复检**（重新从磁盘读 `result3_v2.xlsx` 后重跑 Y4）：结构 "
          f"`{d['struct']['pass']}`、表头 `{d['header']['pass']}`、147 列合计 "
          f"`{d['col147']['pass']}`、4h 段充 `{b['charge_hit']}/{b['n_blocks']}` / "
          f"放 `{b['discharge_hit']}/{b['n_blocks']}` ⇒ 全部 **PASS**")
    A("- 说明：`xlsx` 是 zip 容器，**字节 sha256 会随写入时间变化**（同内容重跑会得到"
      "不同 sha）；内容一致性以 Y4 的逐格/逐块/列合计判定为准 —— 已实测同内容两次"
      "物化的**全部单元格值完全相同**。")
    A(f"- 旧版交付件（**未改**）：`{OLD_XLSX}`，sha256 `{payload['old_xlsx_sha256']}`")
    A(f"- 模板（**未改**）：`{TPL_XLSX}`，sha256 `{payload['template_sha_after']}`"
      f"（冻结值 {TPL_SHA_EXPECTED[:16]}…）")
    A("")
    A("## 四、复现命令")
    A("")
    A("```powershell")
    A("$env:PYTHONIOENCODING='utf-8'")
    A("# scipy/numpy 走 RAG 共享依赖目录（该目录只读，禁止在其中装包）")
    A(f"$env:PYTHONPATH='{os.path.join(PROJ, 'rag', '.deps')}'")
    A(f"python {os.path.join(HERE, 'q76_v2b_full.py')} run")
    A("```")
    A("")
    A(f"本次实际解释器：`{sys.executable}`（依赖 `scipy/numpy/openpyxl`，"
      "`scipy/numpy` 取自 `rag\\.deps`；全程只读引用 7.5 代码，未改一字）。")
    A("")
    A("## 五、边界与移交")
    A("")
    A("- 未 monkey-patch：`v2b` 经公开入参 `executor=` 注入；7.5 磁盘文件一字未改"
      "（见 Y3 跑前=跑后哈希）。")
    A("- 未覆盖旧 `result3.xlsx`；未改模板、未改冻结四件套、未碰主台账。")
    A("- **不做口径裁定**：本次只按队长批准的「执行器 E1 → v2b」执行全年重跑与重物化，"
      "版本是否正式采用由队长决定。")
    A("")
    return "\n".join(L)


# ---------------------------------------------------------------- 主流程
def cmd_run() -> int:
    """跑全年 → Y1–Y3 → 物化候选件 → Y4 → 落盘交付件与报告。"""
    ensure_dir(OUT_DIR)
    print("== 1) 跑前哈希 ==", flush=True)
    h_before = agg_hash()
    print(f"  {h_before['prefix']}（期望 {EXPECTED_AGG_PREFIX}，"
          f"match={h_before['matches_expected']}）", flush=True)
    print("== 2) 读附件 ==", flush=True)
    L, P, price, fc, days = load_data()
    print(f"  L={L.shape} P={P.shape} price={price.shape}", flush=True)
    print("== 3) 旧版逐段真值（对照锚点）==", flush=True)
    old_t = load_old_truth()
    old_c = old_cash(price)
    old_t["cash"] = old_c
    print(f"  旧版 {old_t['n_days']} 天 J_cash={old_c['J_cash']:,.6f}"
          f"（交付件 {OLD_J_CASH:,.6f}，差 "
          f"{abs(old_c['J_cash'] - OLD_J_CASH):.3e}）", flush=True)
    print("== 4) 全年重跑 v2b（d=31..364）==", flush=True)
    v2b = run_arm("v2b", L, P, price, fc, days)
    if not v2b["ok"]:
        print(f"  !! v2b 失败：{v2b.get('reason')}", flush=True)
        return 1
    print(f"  J_cash(v2b)={v2b['totals']['J_cash']:,.6f}", flush=True)
    print("== 5) 基线同源复核：全年重跑 E1 ==", flush=True)
    e1 = run_arm("E1", L, P, price, fc, days)
    if not e1["ok"]:
        print(f"  !! E1 失败：{e1.get('reason')}", flush=True)
        e1 = None
    else:
        print(f"  J_cash(E1)={e1['totals']['J_cash']:,.6f}", flush=True)
    print("== 6) 落逐段明细 ==", flush=True)
    write_seg_jsonl(SEG_JSONL, v2b["seg"])
    write_seg_jsonl(os.path.join(OUT_DIR, "q76_v2b_full_e1_seg.jsonl"),
                    e1["seg"] if e1 else [])
    with open(DAILY_CSV, "w", encoding="utf-8") as fh:
        cols = ("d", "date", "J_plan", "J_adj", "J_emg", "J_cash", "QG0", "QA",
                "QH", "QC", "QD", "soc_min", "soc_max", "balance_max_res")
        fh.write("arm," + ",".join(cols) + "\n")
        for arm, res in (("E1", e1), ("v2b", v2b)):
            if not res:
                continue
            for r in res["rows"]:
                fh.write(arm + "," + ",".join(str(r[c]) for c in cols) + "\n")
    print(f"  已落盘 {DAILY_CSV}", flush=True)
    print("== 7) 跑后哈希 ==", flush=True)
    h_after = agg_hash()
    print(f"  {h_after['prefix']}（match={h_after['matches_expected']}）", flush=True)
    v = verdicts(v2b, old_t, old_c, h_before, h_after, e1)
    for k in ("Y1", "Y2", "Y3"):
        print(f"  {k}: {'PASS' if v[k]['pass'] else 'FAIL'}", flush=True)

    payload = {
        "schema": "q76_v2b_full_v1",
        "window": {"d0": v2b["d0"], "d1": v2b["d1"], "n_days": v2b["n_days"]},
        "config": dict(FROZEN_CFG, margin=MARGIN, epochs=list(EPOCHS_USE),
                       s_init=S0, lam_T=LAM_T, soc_band=[SOC_LO, SOC_HI],
                       hash_files=list(HASH_FILES),
                       expected_agg_prefix=EXPECTED_AGG_PREFIX,
                       old_j_cash_delivered=OLD_J_CASH),
        "monkey_patch": None,
        "code_hash_before": h_before, "code_hash_after": h_after,
        "old_truth": {k: val for k, val in old_t.items() if k != "rows"},
        "old_cash": old_c,
        "arms": {"v2b": {k: val for k, val in v2b.items() if k != "seg"},
                 "E1": ({k: val for k, val in e1.items() if k != "seg"} if e1 else None)},
        "verdicts": v,
        "template_sha_after": sha256_of(TPL_XLSX),
        "template_sha_unchanged": sha256_of(TPL_XLSX) == TPL_SHA_EXPECTED,
        "old_xlsx_sha256": sha256_of(OLD_XLSX),
    }

    y4 = None
    new_sha = None
    if not v["pre_materialize_pass"]:
        print("  !! Y1–Y3 未全过 ⇒ 不予换版，不物化", flush=True)
    else:
        print("== 8) 物化（候选件，BLOCK=24）==", flush=True)
        rep = materialize(SEG_JSONL, SOLUTION_JSON, CAND_XLSX)
        conv = rep["conversion"]
        print(f"  {conv['n_days']} 天 {conv['date_first']}~{conv['date_last']}", flush=True)
        cand_sha = sha256_of(CAND_XLSX)
        print("== 9) Y4 四检 ==", flush=True)
        y4 = y4_checks(CAND_XLSX, TPL_XLSX, v2b["seg"], price)
        y4["template_sha_after"] = sha256_of(TPL_XLSX)
        for name in ("struct", "header", "col147"):
            print(f"  Y4 {name}: {'PASS' if y4[name]['pass'] else 'FAIL'}", flush=True)
        print(f"  Y4 block4h: charge {y4['block4h']['charge_hit']}"
              f"/{y4['block4h']['n_blocks']}, discharge "
              f"{y4['block4h']['discharge_hit']}/{y4['block4h']['n_blocks']}", flush=True)
        y4["all_pass"] = bool(y4["all_pass"]
                              and y4["template_sha_after"] == TPL_SHA_EXPECTED)
        if y4["all_pass"]:
            if os.path.abspath(NEW_XLSX) == os.path.abspath(OLD_XLSX):
                raise ValueError("拒绝写入旧版交付件 result3.xlsx")
            shutil.copyfile(CAND_XLSX, NEW_XLSX)
            new_sha = sha256_of(NEW_XLSX)
            assert new_sha == cand_sha, "交付件与候选件 sha 不一致"
            print(f"  已落盘 {NEW_XLSX}（sha256 {new_sha[:16]}…）", flush=True)
            print("== 10) 交付件复检（重新从磁盘读 result3_v2.xlsx）==", flush=True)
            y4_del = y4_checks(NEW_XLSX, TPL_XLSX, v2b["seg"], price)
            y4_del["template_sha_after"] = sha256_of(TPL_XLSX)
            y4_del["all_pass"] = bool(y4_del["all_pass"]
                                      and y4_del["template_sha_after"] == TPL_SHA_EXPECTED)
            b2 = y4_del["block4h"]
            print(f"  复检 struct/header/col147: {y4_del['struct']['pass']}"
                  f"/{y4_del['header']['pass']}/{y4_del['col147']['pass']}；"
                  f"4h 段 {b2['charge_hit']}/{b2['n_blocks']}（充）、"
                  f"{b2['discharge_hit']}/{b2['n_blocks']}（放）", flush=True)
            assert y4_del["all_pass"], "交付件复检未通过"
            payload["y4_delivery"] = y4_del
        else:
            print("  !! Y4 未全过 ⇒ 不落交付件", flush=True)
        payload.update(candidate_sha256=cand_sha,
                       candidate_equals_delivery=bool(new_sha == cand_sha),
                       new_xlsx_sha256=new_sha,
                       new_xlsx_bytes=(os.path.getsize(NEW_XLSX)
                                       if new_sha else None))
    payload["y4"] = y4
    payload["all_pass"] = bool(v["pre_materialize_pass"] and y4 and y4["all_pass"])
    payload["arms_summary"] = {
        "J_cash_v2b": v2b["totals"]["J_cash"],
        "J_cash_old": old_c["J_cash"],
        "gain_pct": v["Y1"]["gain_pct"],
        "n_days": v2b["n_days"],
        "hash_prefix": h_after["prefix"],
    }
    write_json(RESULT_JSON, payload)
    with open(REPORT_PATH, "w", encoding="utf-8") as fh:
        fh.write(render_report(payload))
    print(f"  已落盘 {REPORT_PATH}", flush=True)
    print(f"== 总体：{'准予换版' if payload['all_pass'] else '不予换版'} ==", flush=True)
    return 0


def main(argv=None) -> int:
    """CLI：``run`` 全流程（唯一子命令）。"""
    ap = argparse.ArgumentParser(description="7.6 v2b 全年重跑 + 重物化 result3_v2")
    ap.add_argument("cmd", nargs="?", default="run", choices=["run"])
    args = ap.parse_args(argv)
    if args.cmd == "run":
        return cmd_run()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
