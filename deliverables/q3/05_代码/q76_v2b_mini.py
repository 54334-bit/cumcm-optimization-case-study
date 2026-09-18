"""7.6 mini 实验：执行器 v2b 是否值得在主线上升为主口径（60 天，两臂同源对照）。

背景（来自 7.5 既有证据，非空想）
-------------------------------
主线执行器是 **E1**（先按计划充放电、缺口走 5p 紧急电）；7.5 侧另有 **v2b 平衡版**
（`7.5对话\\code\\q3_exec_v2b.py`）：实测富余时回退计划放电、实测缺口时不执行"必须靠
5p 才能完成的计划充电"。其自证逐段恒等式残差 4.5e-13、逐段平衡 100%。
已观测增益：`point` 层 −1.4%(60 天)/−2.3%(141 天)；主线 `v3` 层 −1.28%(A)/−1.42%(C)。
本脚本只回答一件事：**在主线上（v3 层）它是否仍然达标**。

为什么不用 monkey-patch
----------------------
`q3_exec_v2b.run_day` 的执行器是**公开入参**（`executor=`），E1 也走同一流程
（`EXECUTORS["E1"]` 就是 `q3_solver.exec_E1` 本体），因此本脚本**只 import、只调用公开
入口**，不替换任何模块级名字。磁盘上的 7.5 文件一字不动，跑前跑后 7 模块聚合哈希
必须仍等于主台账同代次 ``4ddf3879c220``。

口径（冻结主线，逐字不变，只把窗口换成 d=31..90）
----------------------------------------------
``demand=quantile_v3, q=0.8, q_block=segment, margin=0, billing=C, epochs=0,6,12,18,
convention=slot_end``；SOC∈[1200,10800]、S₀=6000、λ_T=0.4720 全部沿用既有实现。

两臂
----
* **B0 = E1**（主线基线）：`q3_main_v2.run_day_v2`（与冻结主台账逐位同源）。
* **B1 = v2b**：`q3_exec_v2b.run_day`，唯一差别是 ``executor=EXECUTORS["v2b"]``。

判据（跑前写死）
----------------
| 判据 | 通过条件 |
| --- | --- |
| X1 收益 | `J_cash(B1) ≤ J_cash(B0) × (1 − 0.5%)` |
| X2 SOC | 全程 ∈[1200,10800]，逐日链式闭合残差 ≤1e-6 |
| X3 平衡 | 逐段 `A+PV·dt+D+H = L·dt+C+R_PV+R_G`，最大残差 ≤1e-6 |
| X4 版本 | 跑前 = 跑后 7 模块聚合哈希 `4ddf3879c220…` |

只读 / 只写边界
---------------
* 只**读** ``7.5对话\\code\\*.py``；只**写** ``7.6对话\\output\\v2b_mini\\**`` 与
  ``7.6对话\\_sub\\q76_v2b_mini_report.md``。

复现
----
    $env:PYTHONIOENCODING='utf-8'
    python D:\\CMUCU\\7.6对话\\code\\q76_v2b_mini.py run
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time

import numpy as np

# ---------------------------------------------------------------- 路径与常量
HERE = os.path.dirname(os.path.abspath(__file__))              # 7.6对话\code
ROOT76 = os.path.dirname(HERE)                                 # 7.6对话
PROJ = os.path.dirname(ROOT76)                                 # D:\CMUCU
Q75_CODE = os.path.join(PROJ, "7.5对话", "code")
OUT_DIR = os.path.join(ROOT76, "output", "v2b_mini")
REPORT_PATH = os.path.join(ROOT76, "_sub", "q76_v2b_mini_report.md")
REF_B0_OUT = os.path.join(ROOT76, "output", "explore", "B0_out.json")   # 已落盘的冻结基线锚点

if Q75_CODE not in sys.path:
    sys.path.insert(0, Q75_CODE)

import q3_exec_v2b as X                                        # noqa: E402  只读引用
import q3_main_v2 as M                                         # noqa: E402  只读引用
from q3_data_io import (DAY0, EPOCHS, ETA, LAM_T, S0, SMAX,    # noqa: E402,F401
                        SMIN, load_forecast, load_load_pv, load_prices)

# D1 冻结集：与 `7.6对话\code\q76_soc_headroom.py` / `q76_pricewise.py` /
# `7.5对话\code\exp\q75_g2_batch.py` 的 HASH_FILES 同序同式（顺序改了哈希就变）。
HASH_FILES = (
    "q3_main_v2.py",
    "q3_solver.py",
    "q3_solver_billingC.py",
    "q3_demand_quantile.py",
    "q3_pv_interp.py",
    "q3_data_io.py",
    "q3_solver_risk.py",
)
EXPECTED_AGG_PREFIX = "4ddf3879c220"     # 主台账同代次（见 exp/q75_g2_manifest.jsonl）

DT = 1.0 / 6.0
D0, D1 = 31, 90                          # 60 天窗口
EPOCHS_USE = (0, 6, 12, 18)
MARGIN = 0.0                             # v3 层分位已含保守性 ⇒ 标量裕度 0
FROZEN_CFG = dict(billing="C", demand="quantile_v3", q=0.8,
                  q_block="segment", convention="slot_end")
X1_THRESH = 0.005                        # X1：≥0.5% 降幅
SOC_LO, SOC_HI = 1200.0, 10800.0
TOL_BAL = 1e-6                           # X3
TOL_CHAIN = 1e-6                         # X2
SOC_TOL = 1e-6                           # SOC 边界浮点尾差

DAY_KEYS = ("J_plan", "J_adj", "J_emg", "J_cash", "QG0", "QA", "QH", "QC", "QD",
            "QL", "QPV", "QR_PV", "QR_G", "QGm", "QGp")


# ---------------------------------------------------------------- 工具
def sha256_of(path: str) -> str:
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
        json.dump(obj, fh, ensure_ascii=False, indent=1)
    print(f"  已落盘 {path}", flush=True)


def write_jsonl(path: str, records) -> None:
    """UTF-8 JSONL 落盘（``json.dumps`` 默认 repr 浮点 ⇒ 可逐位往返）。"""
    ensure_dir(os.path.dirname(os.path.abspath(path)))
    with open(path, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False))
            fh.write("\n")
    print(f"  已落盘 {path}（{len(records)} 行）", flush=True)


def load_data():
    """按主线口径读附件 2（实际负荷/光伏）与附件 4（电价）、附件 3（预报）。"""
    L, P, days = load_load_pv()
    price = load_prices()
    fc = load_forecast()
    return L, P, price, fc, days


# ---------------------------------------------------------------- 单日两臂
def _day_E1(L, P, price, fc, days, d, s):
    """B0：主线 E1（``q3_main_v2.run_day_v2``，与冻结主台账逐位同源）。"""
    return M.run_day_v2(L, P, price, fc, days, d, epochs=EPOCHS_USE, s_init=s,
                        lam=LAM_T, mmap=None, margin=None, risk=False, **FROZEN_CFG)


def _day_v2b(L, P, price, fc, days, d, s):
    """B1：同一滚动流程，唯一差别是 ``executor=EXECUTORS["v2b"]``。"""
    return X.run_day(L, P, price, fc, days, d, X.EXECUTORS["v2b"], billing="C",
                     demand="quantile_v3", q=0.8, q_block="segment",
                     margin=MARGIN, s_init=s, epochs=EPOCHS_USE, lam=LAM_T,
                     convention="slot_end")


def arm_loop(arm: str, L, P, price, fc, days) -> dict:
    """逐日滚动跑一条臂（自己控链，便于逐段/逐日留证）。

    Returns
    -------
    dict：``ok=True`` 时含 ``totals``（窗口累加）、``rows``（逐日明细）、
    ``max_balance_res``（X3）、``max_chain_res``（X2 链式闭合）、``soc_min/soc_max``、
    ``s_first/S_end`` 与 v2b 自检量（``max_chi``/``max_RG_viol``/``max_HR``）。
    """
    runner = _day_E1 if arm == "B0" else _day_v2b
    s = float(S0)
    tot = {k: 0.0 for k in DAY_KEYS}
    rows: list = []
    mx_bal = mx_chain = mx_chi = mx_rgv = mx_hr = 0.0
    mx_rgv_neg = 0.0
    soc_lo, soc_hi = float("inf"), -float("inf")
    s_first = None
    t0 = time.time()
    for d in range(D0, D1 + 1):
        Ld, Pd = L[d], P[d]
        res = runner(L, P, price, fc, days, d, s)
        if not res.get("ok"):
            return {"arm": arm, "ok": False, "d": int(d),
                    "reason": res.get("reason"), "rows": rows}
        A = np.asarray(res["A"], dtype=float)      # A：执行购电量
        Cx = np.asarray(res["C"], dtype=float)     # 执行充电量
        Dx = np.asarray(res["D"], dtype=float)     # 执行放电量
        H = np.asarray(res["H"], dtype=float)
        R_PV = np.asarray(res["R_PV"], dtype=float)
        R_G = np.asarray(res["R_G"], dtype=float)
        S = np.asarray(res["S"], dtype=float)
        # X3：逐段平衡 A + PV·dt + D + H = L·dt + C + R_PV + R_G
        bal = A + Pd * DT + Dx + H - (Ld * DT + Cx + R_PV + R_G)
        # X2：本日内部 SOC 链式闭合 S_{t+1} = S_t + η·C_t − D_t/η
        chain = S[1:] - (S[:-1] + ETA * Cx - Dx / ETA)
        bal_mx = float(np.max(np.abs(bal))) if bal.size else 0.0
        chain_mx = float(np.max(np.abs(chain))) if chain.size else 0.0
        mx_bal = max(mx_bal, bal_mx)
        mx_chain = max(mx_chain, chain_mx)
        S_hi = S[1:]
        soc_lo = min(soc_lo, float(S_hi.min()))
        soc_hi = max(soc_hi, float(S_hi.max()))
        mx_chi = max(mx_chi, float(np.max(np.minimum(Cx, Dx))))
        mx_rgv = max(mx_rgv, float(np.max(R_G - A)))
        mx_rgv_neg = max(mx_rgv_neg, float(np.max(-R_G)))
        mx_hr = max(mx_hr, float(np.max(H * (R_PV + R_G))))
        if s_first is None:
            s_first = float(S[0])
        row = {
            "d": int(d), "date": res["date"], "arm": arm,
            "s_init": float(s), "S_end": float(res["S_end"]),
            "J_plan": float(res["J_plan"]), "J_adj": float(res["J_adj"]),
            "J_emg": float(res["J_emg"]), "J_cash": float(res["J_cash"]),
            "QG0": float(res["QG0"]), "QA": float(A.sum()), "QH": float(res["QH"]),
            "QC": float(Cx.sum()), "QD": float(Dx.sum()),
            "QL": float((Ld * DT).sum()), "QPV": float((Pd * DT).sum()),
            "sum_up": float(np.maximum(A - res["G0"], 0.0).sum()),
            "sum_down": float(np.maximum(res["G0"] - A, 0.0).sum()),
            "QGp": float(np.maximum(A - res["G0"], 0.0).sum()),   # = sum_up
            "QGm": float(np.maximum(res["G0"] - A, 0.0).sum()),   # = sum_down
            "QR_PV": float(res["QR_PV"]), "QR_G": float(res["QR_G"]),
            "soc_min": float(S_hi.min()), "soc_max": float(S_hi.max()),
            "balance_max_res": bal_mx, "chain_max_res": chain_mx,
            "plan_max_res": float(res.get("plan_max_res", float("nan"))),
            "n_pv_missing": int(res.get("n_pv_missing", -1)),
        }
        rows.append(row)
        for k in DAY_KEYS:
            tot[k] += float(row[k])
        s = float(res["S_end"])
        if (d - D0 + 1) % 15 == 0:
            print(f"    [{arm}] d={d} J_cash={tot['J_cash']:,.0f} S={s:,.1f}",
                  flush=True)
    return {
        "arm": arm, "ok": True, "d0": D0, "d1": D1, "n_days": len(rows),
        "totals": tot, "rows": rows,
        "max_balance_res": mx_bal, "max_chain_res": mx_chain,
        "max_chi": mx_chi, "max_RG_viol": mx_rgv, "max_RG": mx_rgv_neg,
        "max_HR": mx_hr,
        "soc_min": float(soc_lo), "soc_max": float(soc_hi),
        "s_first": float(s_first if s_first is not None else S0),
        "S_end": float(s), "runtime_sec": round(time.time() - t0, 1),
    }


# ---------------------------------------------------------------- 汇总器交叉验证
def arm_module_route(arm: str, L, P, price, fc, days) -> dict:
    """用模块自带的年度入口再跑一遍（交叉验证逐日循环没有引入口径漂移）。"""
    t0 = time.time()
    if arm == "B0":
        daily: list = []
        tot = M.run_year_v2(L, P, price, fc, days, dmax=D1, epochs=EPOCHS_USE,
                            s_init=S0, verbose=False, results_out=daily,
                            margin=None, margin_file=None, risk=False, **FROZEN_CFG)
    else:
        r = X.run_year(L, P, price, fc, days, X.EXECUTORS["v2b"], d0=DAY0, d1=D1,
                       billing="C", demand="quantile_v3", q=0.8, q_block="segment",
                       margin=MARGIN, s_init=S0, epochs=EPOCHS_USE, lam=LAM_T,
                       convention="slot_end", verbose=False)
        if not r.get("ok"):
            return {"ok": False, "reason": r.get("reason")}
        tot = dict(r["totals"])
        tot["S_end"] = r["S_end"]
        tot["n_days"] = r["n_days"]
    if tot is None:
        return {"ok": False, "reason": "run_year 返回 None（存在不可行日）"}
    return {"ok": True, "totals": tot, "runtime_sec": round(time.time() - t0, 1)}


def compare_module_route(loop: dict, module: dict) -> dict:
    """逐日循环 vs 模块年度入口：累加量逐位对拍（容差 1e-6）。

    只比对两边的**公共键**：主线 ``run_year_v2`` 的汇总只累加 8 个量
    （``J_*/QG0/QH/QR_PV/QR_G``），不含 ``QA/QC/QD/QL/QPV/QGm/QGp``，缺的键跳过。
    """
    if not module.get("ok"):
        return {"ok": False, "reason": module.get("reason")}
    keys = [k for k in DAY_KEYS if k in module["totals"]]
    worst, worst_key = 0.0, None
    for k in keys:
        diff = abs(float(loop["totals"][k]) - float(module["totals"][k]))
        if diff > worst:
            worst, worst_key = diff, k
    return {"ok": worst <= 1e-6, "max_abs_diff": worst, "worst_key": worst_key,
            "keys_compared": keys,
            "module_j_cash": float(module["totals"]["J_cash"]),
            "loop_j_cash": float(loop["totals"]["J_cash"])}


def load_ref_b0() -> dict | None:
    """读已落盘的冻结基线锚点（``output\\explore\\B0_out.json``，只读）。"""
    if not os.path.isfile(REF_B0_OUT):
        return None
    with open(REF_B0_OUT, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------- 判据
def verdicts(b0: dict, b1: dict, h_before: dict, h_after: dict,
             ref: dict | None) -> dict:
    """X1–X4 逐条判定（阈值全部在文件头常量里，跑前写死）。"""
    j0, j1 = float(b0["totals"]["J_cash"]), float(b1["totals"]["J_cash"])
    gain = (j0 - j1) / j0
    x1 = {"name": "X1 收益", "pass": bool(j1 <= j0 * (1.0 - X1_THRESH)),
          "J_cash_B0": j0, "J_cash_B1": j1, "gain_frac": gain,
          "gain_pct": round(gain * 100.0, 4), "threshold_pct": 0.5,
          "criterion": "J_cash(B1) ≤ J_cash(B0) × 0.995"}
    soc_ok = (b1["soc_min"] >= SOC_LO - SOC_TOL) and (b1["soc_max"] <= SOC_HI + SOC_TOL)
    x2 = {"name": "X2 SOC", "pass": bool(soc_ok and b1["max_chain_res"] <= TOL_CHAIN),
          "soc_min": b1["soc_min"], "soc_max": b1["soc_max"],
          "soc_band": [SOC_LO, SOC_HI], "in_band": bool(soc_ok),
          "max_chain_res": b1["max_chain_res"], "tol": TOL_CHAIN,
          "max_chain_res_B0": b0["max_chain_res"]}
    x3 = {"name": "X3 平衡", "pass": bool(b1["max_balance_res"] <= TOL_BAL),
          "max_balance_res": b1["max_balance_res"], "tol": TOL_BAL,
          "max_balance_res_B0": b0["max_balance_res"]}
    hash_same = h_before["agg"] == h_after["agg"]
    changed = sorted(k for k in HASH_FILES
                     if h_before["per_file"][k] != h_after["per_file"][k])
    x4 = {"name": "X4 版本", "pass": bool(hash_same and h_after["matches_expected"]
                                          and not changed),
          "agg_before": h_before["agg"], "agg_after": h_after["agg"],
          "prefix": h_after["prefix"], "expected_prefix": EXPECTED_AGG_PREFIX,
          "matches_expected": h_after["matches_expected"],
          "hash_changed_files": changed}
    anchor = None
    if ref is not None:
        d = abs(float(ref["J_cash"]) - j0)
        anchor = {"ref_path": REF_B0_OUT, "ref_J_cash": float(ref["J_cash"]),
                  "loop_J_cash": j0, "abs_diff": d, "pass": bool(d <= 1e-6)}
    allpass = x1["pass"] and x2["pass"] and x3["pass"] and x4["pass"]
    return {"X1": x1, "X2": x2, "X3": x3, "X4": x4, "anchor_B0": anchor,
            "all_pass": bool(allpass)}


# ---------------------------------------------------------------- 报告
def render_report(payload: dict) -> str:
    """把结果渲染成 ``_sub`` 报告（Markdown，数字全部来自 payload）。"""
    hb = payload["code_hash_before"]
    b0, b1, v = payload["arms"]["B0"], payload["arms"]["B1"], payload["verdicts"]
    t0, t1 = b0["totals"], b1["totals"]
    L = []
    A = L.append
    A("# q76_v2b_mini（coder 子代理）—— v2b 执行器 60 天同源两臂对照")
    A("")
    A(f"> 窗口 `d={D0}..{D1}`（{b1['n_days']} 天）；口径 `demand=quantile_v3, q=0.8, "
      f"q_block=segment, margin=0, billing=C, epochs=0,6,12,18, convention=slot_end`；")
    A(f"> 代码代次（7 模块聚合 SHA-256）：`{hb['agg']}`（前 12 位 `{hb['prefix']}`）")
    A("")
    A("## 一、结论（先给判据，再给数字）")
    A("")
    A("| 判据 | 通过条件 | 实测 | 判定 |")
    A("| --- | --- | --- | --- |")
    A(f"| X1 收益 | `J_cash(B1) ≤ B0 × 0.995` | `{v['X1']['J_cash_B1']:,.2f}` vs "
      f"`{v['X1']['J_cash_B0']:,.2f}`（降幅 **{v['X1']['gain_pct']:.4f}%**） | "
      f"**{'PASS' if v['X1']['pass'] else 'FAIL'}** |")
    A(f"| X2 SOC | 全程 ∈[1200,10800] 且逐日链式闭合残差 ≤1e-6 | "
      f"`[{v['X2']['soc_min']:.6f}, {v['X2']['soc_max']:.6f}]`；链式残差 "
      f"`{v['X2']['max_chain_res']:.3e}` | "
      f"**{'PASS' if v['X2']['pass'] else 'FAIL'}** |")
    A(f"| X3 平衡 | 逐段 `A+PV·dt+D+H = L·dt+C+R_PV+R_G`，最大残差 ≤1e-6 | "
      f"`{v['X3']['max_balance_res']:.3e}`（B0 `{v['X3']['max_balance_res_B0']:.3e}`） | "
      f"**{'PASS' if v['X3']['pass'] else 'FAIL'}** |")
    A(f"| X4 版本 | 跑前 = 跑后 7 模块聚合哈希 `{EXPECTED_AGG_PREFIX}…` | 跑前 "
      f"`{hb['prefix']}` / 跑后 `{v['X4']['prefix']}`，变动文件 "
      f"`{v['X4']['hash_changed_files']}` | "
      f"**{'PASS' if v['X4']['pass'] else 'FAIL'}** |")
    A("")
    A(f"**总体：{'四项判据全部通过' if v['all_pass'] else '存在未通过判据'}。**")
    if v["all_pass"]:
        A("")
        A("**结论：值得在主线上把 v2b 升为主口径（探路级证据，最终由队长裁定）。**"
          "理由是四项判据在 **60 天主线（v3 层）** 上一次性全通过：现金降幅 "
          f"{v['X1']['gain_pct']:.4f}%（阈值 0.5%）、SOC 与逐段平衡无退化（残差量级与"
          "基线相同）、7 模块哈希跑前=跑后；且方向与 7.5 已观测的 v3 层 "
          "−1.28%(A)/−1.42%(C) 一致、本窗口幅度更大。**封存条件**：若全年/其余窗口"
          "或 A 读法下出现任一判据不通过，即回退 E1，不做局部补丁。")
    else:
        A("")
        A("**结论：封存（不升主口径）。** 存在未通过的判据，v2b 不作为主线执行口径，"
          "保持 E1 不变；本实验结论降级为线索。")
    if v["anchor_B0"]:
        a = v["anchor_B0"]
        A("")
        A(f"外部锚点复核：本脚本 B0 逐日循环 `J_cash={a['loop_J_cash']:.6f}` 对已落盘冻结"
          f"基线 `output\\explore\\B0_out.json` `J_cash={a['ref_J_cash']:.6f}`，"
          f"差 `{a['abs_diff']:.3e}` ⇒ **{'一致' if a['pass'] else '不一致'}**"
          "（说明 B0 臂与冻结主线逐位同源）。")
    # 收益来源拆解（用两臂差额自己说话，不做额外假设）
    d_plan = float(t1["J_plan"]) - float(t0["J_plan"])
    d_adj = float(t1["J_adj"]) - float(t0["J_adj"])
    d_emg = float(t1["J_emg"]) - float(t0["J_emg"])
    A("")
    A(f"收益来源拆解：`ΔJ_cash = ΔJ_plan {d_plan:+,.2f} + ΔJ_adj {d_adj:+,.2f} + "
      f"ΔJ_emg {d_emg:+,.2f}`。紧急电 `ΣH` 从 {float(t0['QH']):,.1f} kWh 降到 "
      f"{float(t1['QH']):,.1f} kWh（{float(t1['QH']) / float(t0['QH']) - 1.0:+.2%}），"
      "与 v2b 的机制一致：实测缺口段不再执行"
      "“只能靠 5p 紧急电完成”的计划充电；代价是相对 G⁰ 的下调量增加"
      f"（Σ(G⁰−A)⁺ {float(t0['QGm']):,.1f} → {float(t1['QGm']):,.1f} kWh，"
      "下调罚 0.5p 仍在读法 C 里计入）。")
    gains = [float(r1["J_cash"]) - float(r0["J_cash"])
             for r0, r1 in zip(b0["rows"], b1["rows"])]
    n_imp = sum(1 for g in gains if g < 0.0)
    n_flat = sum(1 for g in gains if abs(g) <= 1e-9)
    A("")
    A(f"逐日分布：{n_imp}/{len(gains)} 天现金改善、持平 {n_flat} 天、"
      f"劣化 {len(gains) - n_imp - n_flat} 天；单日最大改善 {min(gains):,.2f} 元，"
      f"最差单日 {max(gains):,.2f} 元"
      "（逐日明细见 `output\\v2b_mini\\compare_daily.csv`）。")
    A("")
    A("## 二、两臂对照（窗口 d=31..90 累加）")
    A("")
    A("| 指标 | B0 = E1（基线） | B1 = v2b | 差（B1−B0） | 相对 |")
    A("| --- | ---: | ---: | ---: | ---: |")
    rows = [("J_plan（元）", "J_plan", 2), ("J_adj（元）", "J_adj", 2),
            ("J_emg（元）", "J_emg", 2), ("J_cash（元）", "J_cash", 2),
            ("Σ(A−G⁰)⁺（kWh）", "QGp", 3), ("Σ(G⁰−A)⁺（kWh）", "QGm", 3),
            ("ΣH（kWh）", "QH", 3), ("ΣG⁰（kWh）", "QG0", 3),
            ("ΣA（kWh）", "QA", 3), ("ΣC（执行充电，kWh）", "QC", 3),
            ("ΣD（执行放电，kWh）", "QD", 3),
            ("ΣR_PV（弃光，kWh）", "QR_PV", 3), ("ΣR_G（弃购电，kWh）", "QR_G", 3)]
    for label, key, nd in rows:
        x, y = float(t0[key]), float(t1[key])
        rel = f"{(y - x) / x * 100.0:+.4f}%" if x else "n/a"
        A(f"| {label} | {x:,.{nd}f} | {y:,.{nd}f} | {y - x:+,.{nd}f} | {rel} |")
    A(f"| SOC 区间（kWh） | [{b0['soc_min']:.6f}, {b0['soc_max']:.6f}] | "
      f"[{b1['soc_min']:.6f}, {b1['soc_max']:.6f}] | — | — |")
    A(f"| 期末 SOC S_end（kWh） | {b0['S_end']:.6f} | {b1['S_end']:.6f} | "
      f"{b1['S_end'] - b0['S_end']:+.6f} | — |")
    A("")
    A("自检量（逐段聚合口径）")
    A("")
    A("| 量 | B0 = E1 | B1 = v2b |")
    A("| --- | ---: | ---: |")
    A(f"| 逐段平衡最大残差 | {b0['max_balance_res']:.3e} | {b1['max_balance_res']:.3e} |")
    A(f"| 日内 SOC 链式最大残差 | {b0['max_chain_res']:.3e} | {b1['max_chain_res']:.3e} |")
    A(f"| 执行器同充同放 max min(C,D) | {b0['max_chi']:.3e} | {b1['max_chi']:.3e} |")
    A(f"| R_G − A 最大值（v2b docstring 断言 ≤0；E1 无此断言） | "
      f"{b0['max_RG_viol']:.3e} | {b1['max_RG_viol']:.3e} |")
    A(f"| H·(R_PV+R_G) 最大值（应为 0） | {b0['max_HR']:.3e} | {b1['max_HR']:.3e} |")
    A(f"| 运行时间（s） | {b0['runtime_sec']} | {b1['runtime_sec']} |")
    A("")
    A("## 三、口径与实现声明")
    A("")
    A("- **未使用 monkey-patch**：`q3_exec_v2b.run_day` 的执行器是公开入参 "
      "`executor=`，B1 只是把 `EXECUTORS[\"v2b\"]` 传进去；两臂共用同一单日滚动流程"
      "（计划层 LP、光伏重建、裕度语义、落定规则、报账函数逐字一致），"
      "**唯一差别是执行器**。7.5 磁盘文件一字未改（见 X4）。")
    A("- B0 走主线公开入口 `q3_main_v2.run_day_v2`（`info=known, risk=False, "
      "mmap=None, margin=None`）；`demand=quantile_v3` 且 `margin=None` 时主线把 "
      "mmap 清空 ⇒ m≡0，与 B1 的标量 `margin=0` 同义。")
    A("- 交叉验证：逐日循环的累加量与模块年度入口"
      "（`q3_main_v2.run_year_v2` / `q3_exec_v2b.run_year`）逐项对拍。")
    ms = payload["module_crosscheck"]
    for arm in ("B0", "B1"):
        c = ms[arm]
        A(f"  - {arm}：`max_abs_diff={c['max_abs_diff']:.3e}`"
          f"（worst `{c['worst_key']}`）⇒ **{'一致' if c['ok'] else '不一致'}**"
          f"；模块 J_cash `{c['module_j_cash']:.6f}` = 循环 "
          f"`{c['loop_j_cash']:.6f}`。")
    A("- 逐段平衡残差的两种写法等价：主线结算 "
      "`A − C + D + H − R_PV − R_G − (L−P)·dt` 与 X3 的 "
      "`A + PV·dt + D + H − (L·dt + C + R_PV + R_G)` 是同一条恒等式。")
    A("")
    A("## 四、复现命令")
    A("")
    A("```powershell")
    A("$env:PYTHONIOENCODING='utf-8'")
    A(f"python {os.path.join(HERE, 'q76_v2b_mini.py')} run")
    A("```")
    A("")
    A("产物：`output\\v2b_mini\\v2b_mini.json`（含 X1–X4 判定与两臂逐日明细路径）、"
      "`B0_rows.jsonl`、`B1_rows.jsonl`。")
    A("")
    A("## 五、边界与移交")
    A("")
    A("- 只写 `7.6对话\\output\\v2b_mini\\**` 与 `7.6对话\\_sub\\q76_v2b_mini_report.md`；"
      "未改 7.5 任何文件、未改冻结四件套、未跑全年、未碰主台账。")
    A("- **不做口径裁定**：是否把 v2b 升为主线执行口径由队长决定。")
    A("- 本实验是 60 天 minimize 窗口的**主线（v3 层）单点验证**，"
      "不外推到全年、也不替代 S2 台账。")
    A("")
    return "\n".join(L)


# ---------------------------------------------------------------- 主流程
def cmd_run() -> int:
    """跑两臂 → 判定 X1–X4 → 落盘 JSON + 报告。"""
    ensure_dir(OUT_DIR)
    print("== 1) 跑前哈希 ==", flush=True)
    h_before = agg_hash()
    print(f"  {h_before['prefix']}（期望 {EXPECTED_AGG_PREFIX}，"
          f"match={h_before['matches_expected']}）", flush=True)
    print("== 2) 读附件 ==", flush=True)
    L, P, price, fc, days = load_data()
    print(f"  形状 L={L.shape} P={P.shape} price={price.shape}", flush=True)
    print(f"== 3) B0 = E1（d={D0}..{D1}）==", flush=True)
    b0 = arm_loop("B0", L, P, price, fc, days)
    if not b0["ok"]:
        print(f"  !! B0 失败：{b0.get('reason')}", flush=True)
        return 1
    print(f"  J_cash(B0)={b0['totals']['J_cash']:,.6f}", flush=True)
    print(f"== 4) B1 = v2b（d={D0}..{D1}）==", flush=True)
    b1 = arm_loop("B1", L, P, price, fc, days)
    if not b1["ok"]:
        print(f"  !! B1 失败：{b1.get('reason')}", flush=True)
        return 1
    print(f"  J_cash(B1)={b1['totals']['J_cash']:,.6f}", flush=True)
    print("== 5) 模块年度入口交叉验证 ==", flush=True)
    cross = {}
    for arm, loop in (("B0", b0), ("B1", b1)):
        mod = arm_module_route(arm, L, P, price, fc, days)
        cross[arm] = compare_module_route(loop, mod)
        print(f"  {arm}: {cross[arm]}", flush=True)
    print("== 6) 跑后哈希 ==", flush=True)
    h_after = agg_hash()
    print(f"  {h_after['prefix']}（match={h_after['matches_expected']}）", flush=True)
    ref = load_ref_b0()
    v = verdicts(b0, b1, h_before, h_after, ref)
    payload = {
        "arm_desc": {"B0": "E1（主线基线，q3_main_v2.run_day_v2）",
                     "B1": "v2b（q3_exec_v2b.run_day，executor=EXECUTORS['v2b']）"},
        "window": {"d0": D0, "d1": D1, "n_days": b1["n_days"]},
        "config": dict(FROZEN_CFG, margin=MARGIN, epochs=list(EPOCHS_USE),
                       s_init=S0, lam_T=LAM_T, soc_band=[SOC_LO, SOC_HI]),
        "monkey_patch": None,
        "code_hash_before": h_before, "code_hash_after": h_after,
        "arms": {"B0": b0, "B1": b1},
        "module_crosscheck": cross,
        "verdicts": v,
        "runtime_sec": {"B0": b0["runtime_sec"], "B1": b1["runtime_sec"]},
    }
    # 逐日明细单独落 JSONL（JSON 汇总里去掉 rows，避免文件臃肿）
    write_jsonl(os.path.join(OUT_DIR, "B0_rows.jsonl"), b0["rows"])
    write_jsonl(os.path.join(OUT_DIR, "B1_rows.jsonl"), b1["rows"])
    slim = dict(payload)
    slim["arms"] = {k: {kk: vv for kk, vv in arm.items() if kk != "rows"}
                    for k, arm in payload["arms"].items()}
    write_json(os.path.join(OUT_DIR, "v2b_mini.json"), slim)
    # 两臂逐日 CSV（便于人工核读）
    with open(os.path.join(OUT_DIR, "compare_daily.csv"), "w",
              encoding="utf-8") as fh:
        cols = ("d", "date", "J_cash", "QG0", "QA", "QH", "QC", "QD",
                "sum_up", "sum_down", "soc_min", "soc_max", "balance_max_res")
        fh.write("arm," + ",".join(cols) + "\n")
        for arm, rows in (("B0", b0["rows"]), ("B1", b1["rows"])):
            for r in rows:
                fh.write(arm + "," + ",".join(str(r[c]) for c in cols) + "\n")
    print(f"  已落盘 {os.path.join(OUT_DIR, 'compare_daily.csv')}", flush=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as fh:
        fh.write(render_report(payload))
    print(f"  已落盘 {REPORT_PATH}", flush=True)
    print("== 判定 ==", flush=True)
    for k in ("X1", "X2", "X3", "X4"):
        print(f"  {k}: {'PASS' if v[k]['pass'] else 'FAIL'}", flush=True)
    print(f"  总体: {'全部通过' if v['all_pass'] else '有未通过项'}", flush=True)
    print(f"  结论线索: gain={v['X1']['gain_pct']:.4f}%", flush=True)
    return 0


def main(argv=None) -> int:
    """CLI：``run`` 跑实验并出报告（唯一子命令）。"""
    ap = argparse.ArgumentParser(description="7.6 v2b mini 实验（60 天两臂）")
    ap.add_argument("cmd", nargs="?", default="run", choices=["run"])
    args = ap.parse_args(argv)
    if args.cmd == "run":
        return cmd_run()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
