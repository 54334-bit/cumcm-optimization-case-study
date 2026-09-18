# -*- coding: utf-8 -*-
r"""Q4 图件线**唯一数据入口**（交付口径：附件4 波动电价；Q4-2 用 E1、Q4-3 用 v2b 执行器）。

取数以 `D:\CMUCU\Q4交付\` 为准（队长指定）；图件清单见 `Q4交付\Q4_最终产物清单与交接.md` §六。

锚点（来自 Q4交付 索引/交付说明）：
  Q4-2 = 13,850,454.64 元（附件4 价）；Q4-3 = 13,727,033.66 元；
  Q2 基线 = 13,252,341.09；Q3 v2 基线 = 13,120,194.06（Q4-3 的 2×2 左上角复现它，差 0.00）。
  2×2：Q4-2 价格效应 +744,522.48 / 重优化 −146,408.94；Q4-3 +760,032.97 / −153,193.38。

安全：只读；不跑 Q4 主线脚本（会覆盖提交件）。
用法：$env:PYTHONPATH="D:\CMUCU\rag\.deps"; $env:PYTHONIOENCODING='utf-8'
      & $py "D:\CMUCU\6对话\code\q4_data_frozen.py"
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

T, DT, N_DAYS = 144, 1.0 / 6.0, 334
ETA = 0.9
Q4 = Path(r"D:\CMUCU\Q4交付")
EV = Q4 / "04_证据"
CKPT = EV / "q4_cp2_checkpoint.json"
CF2 = EV / "q4_counterfactual_2x2.json"
CF3 = EV / "q4_q43_2x2.json"
BLK = EV / "q4_price_block_decomp.json"
CAL = EV / "q4_probe_price_caliber_v2.json"
A4 = Path(r"D:\CMUCU\B对话\clean\attachment4_clean.csv")
A1 = Path(r"D:\CMUCU\B对话\clean\q1_clean.csv")
MANIFEST = Q4 / "manifest.sha256.json"

EXPECT = {
    "Q4_2_total": 13850454.64,
    "Q4_3_total": 13727033.66,
    "Q2_total": 13252341.09,
    "Q3v2_total": 13120194.06,
    "cf2_price_effect": 744522.48,
    "cf2_reopt_effect": -146408.94,
    "cf3_price_effect": 760032.97,
    "cf3_reopt_effect": -153193.38,
}


def sha256_of(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def check_manifest(verbose: bool = True) -> list[str]:
    """与 Q4交付 的 manifest.sha256.json 对表（只核我用到的文件）。"""
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    files = m.get("files", {})
    if isinstance(files, dict):                    # 本包 manifest 是 {路径: sha256} 映射
        reg = {k.replace("/", "\\"): v for k, v in files.items()}
    else:
        reg = {f["path"].replace("/", "\\"): f["sha256"] for f in files}
    used = [CKPT, CF2, CF3, BLK, CAL]
    bad = []
    for p in used:
        rel = str(p.relative_to(Q4))
        want = reg.get(rel)
        got = sha256_of(p)
        if want is None:
            if verbose:
                print("  %-42s 未登记（manifest 无此项）" % rel)
        elif want.lower() != got.lower():
            bad.append("%s sha 不符：登记 %s… 实际 %s…" % (rel, want[:12], got[:12]))
        elif verbose:
            print("  %-42s sha OK（%s…）" % (rel, got[:12]))
    return bad


def load_checkpoint(verbose: bool = True) -> dict:
    d = json.loads(CKPT.read_text(encoding="utf-8"))
    days = d["days"]
    if len(days) != N_DAYS:
        raise ValueError("checkpoint 天数 %d != %d" % (len(days), N_DAYS))
    out = {"meta": {k: d[k] for k in ("task", "caliber", "eval_window", "annual")
                    if k in d},
           "d": np.array([r["d"] for r in days]),
           "date": [None] * N_DAYS,
           "S0": np.array([r["S0"] for r in days], float),
           "S1": np.array([r["S1"] for r in days], float),
           "G": np.array([r["G"] for r in days], float),
           "C": np.array([r["C"] for r in days], float),
           "D": np.array([r["D"] for r in days], float),
           "H": np.array([r["H"] for r in days], float),
           "R_PV": np.array([r["R_PV"] for r in days], float),
           "R_G": np.array([r["R_G"] for r in days], float),
           "J_plan_day": np.array([r["J_plan"] for r in days], float),
           "J_emg_day": np.array([r["J_emg"] for r in days], float),
           "QH_day": np.array([r["QH"] for r in days], float),
           "margin_d": np.array([r["margin_d"] for r in days], float)}
    # 日期：d 为自 2025-01-01 起的天偏移
    import datetime as dt
    out["date"] = [(dt.date(2025, 1, 1) + dt.timedelta(days=int(x))).isoformat()
                   for x in out["d"]]
    for k in ("G", "C", "D", "H", "R_PV", "R_G"):
        if out[k].shape != (N_DAYS, T):
            raise ValueError("%s 形状 %s != (%d,%d)" % (k, out[k].shape, N_DAYS, T))
    if verbose:
        print("  checkpoint：%d 天 × %d 段（%s ~ %s）" % (N_DAYS, T, out["date"][0], out["date"][-1]))
    return out


def soc_path_1day(ck: dict, i: int) -> np.ndarray:
    """由 C/D 按 η=0.9 重建第 i 天的 145 点 SOC（checkpoint 只给日界两端）。"""
    s = np.empty(T + 1, float)
    s[0] = ck["S0"][i]
    s[1:] = s[0] + np.cumsum(ETA * ck["C"][i] - ck["D"][i] / ETA)
    return s


def load_attachment4(verbose: bool = True) -> dict:
    """附件4 实时电价：365 天 × 144 段；取 Q4 窗口 2025-02-01~12-31（索引 31..364）。"""
    rows = list(csv.reader(A4.read_text(encoding="utf-8").splitlines()))
    hdr, body = rows[0], rows[1:]
    dates = [r[0] for r in body]
    arr = np.array([[float(v) for v in r[1:1 + T]] for r in body], float)
    if arr.shape != (365, T):
        raise ValueError("附件4 形状 %s != (365,%d)" % (arr.shape, T))
    if verbose:
        print("  附件4：%d 天 × %d 段，价 %.4f~%.4f 元/kWh" % (arr.shape[0], T, arr.min(), arr.max()))
    # 分位按**时刻**聚合（对 365 天求每个时段的 5/50/95 分位）→ 形状 (3, 144)
    return {"date": dates, "price": arr, "window": arr[31:365], "window_dates": dates[31:365],
            "quantiles": np.quantile(arr, [0.05, 0.5, 0.95], axis=0)}


def load_attachment1(verbose: bool = True) -> dict:
    rows = list(csv.reader(A1.read_text(encoding="utf-8").splitlines()))
    hdr = [h.strip() for h in rows[0]]
    def col(*keys):
        for i, h in enumerate(hdr):
            if any(k.lower() in h.lower() for k in keys):
                return i
        raise KeyError(keys)
    ci_p, ci_l, ci_v = col("price", "电价"), col("load", "负载"), col("pv", "光伏")
    price = np.array([float(r[ci_p]) for r in rows[1:]], float)
    load = np.array([float(r[ci_l]) for r in rows[1:]], float)
    pv = np.array([float(r[ci_v]) for r in rows[1:]], float)
    if verbose:
        print("  附件1 典型日：价 %.4f~%.4f；负载 %.0f~%.0f kW；光伏 %.0f~%.0f kW"
              % (price.min(), price.max(), load.min(), load.max(), pv.min(), pv.max()))
    return {"price": price, "load": load, "pv": pv}


def load_evidence_json(path: Path, verbose: bool = True) -> dict:
    d = json.loads(path.read_text(encoding="utf-8"))
    if verbose:
        print("  %s：keys=%s" % (path.name, list(d.keys())[:10]))
    return d


def anchors(ck: dict, cf2: dict, cf3: dict, blk: dict, cal: dict) -> dict:
    """从证据文件现算锚点（不引用其自报的汇总字段，除对照所需）。"""
    c2 = cf2["cells"]; c3 = cf3["cells"]
    out = {
        "Q4_2_total": float(c2["G4P4"]["total"]),
        "Q4_3_total": float(c3["plan4_settle4"]["J_cash"]),
        "Q2_total": float(c2["G1P1"]["total"]),
        "Q3v2_total": float(c3["plan1_settle1"]["J_cash"]),
        # 2×2 两效应自己算：价格效应＝同计划(基线计划)换价；重优化＝同价(P4)换计划
        "cf2_price_effect": float(c2["G1P4"]["total"] - c2["G1P1"]["total"]),
        "cf2_reopt_effect": float(c2["G4P4"]["total"] - c2["G1P4"]["total"]),
        "cf3_price_effect": float(c3["plan1_settle4"]["J_cash"] - c3["plan1_settle1"]["J_cash"]),
        "cf3_reopt_effect": float(c3["plan4_settle4"]["J_cash"] - c3["plan1_settle4"]["J_cash"]),
        # 分块拆解：块级效应之和应等于总额
        "blk_price_total": float(np.sum(blk["eff_price"])),
        "blk_reopt_total": float(np.sum(blk["eff_reopt"])),
        "cal_I": float(cal.get("I", np.nan)),
    }
    # checkpoint 自洽：日界 SOC 链 + 由 C/D 重建的日末 SOC 是否等于 S1
    gap = float(np.abs(ck["S1"][:-1] - ck["S0"][1:]).max())
    rec = max(abs(soc_path_1day(ck, i)[-1] - ck["S1"][i]) for i in range(N_DAYS))
    out["soc_chain_gap_kWh"] = gap
    out["soc_recon_gap_kWh"] = rec
    out["soc_min"], out["soc_max"] = float(ck["S0"].min()), float(ck["S1"].max())
    out["sum_H_kWh"] = float(ck["H"].sum())
    out["Q4_3_price_info_pct"] = float(
        100 * (c3["plan1_settle4"]["J_cash"] / c3["plan4_settle4"]["J_cash"] - 1))
    return out


def check_anchors(got: dict, *, verbose: bool = True) -> list[str]:
    bad = []
    for k, exp in EXPECT.items():
        g = got.get(k)
        if g is None:
            bad.append("%s 缺失" % k); continue
        d = abs(g - exp)
        ok = d <= 0.01
        if not ok:
            bad.append("%s: 现算 %r vs 交付 %r（差 %r）" % (k, g, exp, g - exp))
        if verbose:
            print("  %-18s 现算 %16.4f | 交付 %16.4f | 差 %10.6f | %s"
                  % (k, g, exp, g - exp, "OK" if ok else "**FAIL**"))
    for k in ("blk_price_total", "blk_reopt_total"):
        d = abs(got[k] - EXPECT["cf2_price_effect" if "price" in k else "cf2_reopt_effect"])
        ok = d <= 0.01
        if verbose:
            print("  %-18s 分块合计 %16.4f | 2×2 %16.4f | 差 %10.6f | %s"
                  % (k, got[k], EXPECT["cf2_price_effect" if "price" in k else "cf2_reopt_effect"],
                     got[k] - EXPECT["cf2_price_effect" if "price" in k else "cf2_reopt_effect"],
                     "OK" if ok else "**FAIL**"))
        if not ok:
            bad.append("%s 与 2×2 不闭合（差 %r）" % (k, d))
    for k, tol in (("soc_chain_gap_kWh", 1e-6), ("soc_recon_gap_kWh", 1e-2)):
        ok = got[k] <= tol
        if verbose:
            print("  %-18s %16.6f | 容差 %-8.6f | %s" % (k, got[k], tol, "OK" if ok else "**FAIL**"))
        if not ok:
            bad.append("%s=%.6f 超容差 %.6f" % (k, got[k], tol))
    return bad


def main() -> int:
    print("== 与 Q4交付 manifest 对表（我用到的证据文件）==")
    bad = check_manifest()
    print("== 读证据 ==")
    ck = load_checkpoint()
    cf2 = load_evidence_json(CF2)
    cf3 = load_evidence_json(CF3)
    blk = load_evidence_json(BLK)
    cal = load_evidence_json(CAL)
    a4 = load_attachment4()
    a1 = load_attachment1()
    print("== 锚点对表（现算 vs 交付公布）==")
    got = anchors(ck, cf2, cf3, blk, cal)
    bad += check_anchors(got)
    print("  附加：ΣH=%.3f kWh；SOC∈[%.1f, %.1f]；Q4-3 价格信息价值臂 %.3f%%"
          % (got["sum_H_kWh"], got["soc_min"], got["soc_max"], got["Q4_3_price_info_pct"]))
    print("\nANCHORS:", "PASS" if not bad else "FAIL")
    for b in bad:
        print("  !", b)
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
