# -*- coding: utf-8 -*-
r"""Q2 图件线**主口径**数据入口：非预见 + 因果保守裕度（2026-09-12 13:48 封包）。

口径（唯一主口径，旧"同周4周+MILP"已降为灵敏度③）：
  0:00 计划：负荷 = 当日实际（题面未给负荷预报，视为已知）；
             光伏 = 过去 4 天实际光伏均值 × (1 − 因果裕度)，
             裕度 = clip(−Q20(过去 28 天相对预报误差), 0, 0.35)，均值 ≈7%；
  结算：用附件2 **实际**负荷与**实际**光伏，缺口按当时电价 **5 倍**紧急购电；
  储能：容量 [1200,10800] kWh、功率 ≤5000 kW、η=0.9、2025-01-01 0:00 = 6000 kWh；
  范围：334 天（2025-02-01~12-31）× 144 段/日；电价为附件1 单日曲线。

真值源（sha256 冻结，先验后用）：
  - `D:\CMUCU\5对话\output\q2_emg_detail.json`（= 交付包 `evidence/q2_emg_detail.json`）
  - 提交件 `D:\CMUCU\5对话\result2.xlsx`

表 1 映射（**本口径为"位置映射"，与旧口径的"右移一格"不同**）：
  第 2 列(1-based) = `[0:00,0:10)`，第 145 列 = `[23:50,24:00)`；即 0-based 索引 i(1..144) ↔ t = i−1。

用法：
    $env:PYTHONPATH="D:\CMUCU\rag\.deps"; $env:PYTHONIOENCODING='utf-8'
    & $py "D:\CMUCU\6对话\code\q2_data_causal.py"     # 自检 + 锚点表
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

T, DT = 144, 1.0 / 6.0
N_DAYS = 334
DAY0 = dt.date(2025, 1, 1)          # rows[].d 是自 2025-01-01 起的天偏移，d=31 → 2025-02-01
ETA = 0.9

DELIV = Path(r"D:\CMUCU\Q2交付")          # 对话5 的交付总目录（现行取数推荐入口）
D5 = Path(r"D:\CMUCU\5对话")
ART = DELIV / "04_证据" / "q2_emg_detail.json"      # 与 5对话\output 同哈希（sha 已核）
XLSX = DELIV / "01_提交件" / "result2.xlsx"          # = 5对话\result2.xlsx（同哈希）
ART_SHA256 = "15c058b7fff1bf39793338808ffc5f64fc5d241fb0306897667eee137b672b1e"

# 交付说明 §2 的对外数字（锚点；差超容差即 FAIL）
EXPECT = {
    "J_plan": 12891818.24,
    "J_emg": 360522.85,
    "total": 13252341.09,
    "QG": 21283432.62,
    "C_sum": 6684044.85,
    "D_sum": 5412321.33,
    "H_kWh": 55801.05,
    "emg_days": 242,
    "emg_spans": 375,
    "max_span_kWh": 5480.44,       # 裁决书 §三
    "s_end": 7950.0001,
    "soc_min": 6000.0,
    "soc_max": 8085.49,
}
TOL_COUNT = {"emg_days": 0, "emg_spans": 0}
TOL_LOOSE = {"max_span_kWh": 0.5, "soc_max": 0.01, "soc_min": 0.01}

# 裁决书（`6对话\Q2最终裁决与可用数字_对话5到6对话.md`）§一 的统一口径对照表：
# 基准一律为**主口径 13,252,341.09**；② 为不可执行下界；③ 为旧灵敏度（仅可出现在对照/灵敏度图并显式标注）。
CMP_RULING = [
    ("★ 主口径\n非预见+因果裕度", 13252341.09, "grid", "", "提交口径"),
    ("① 无裕度\n（同预报）", 14178004.00, "pv", "", "+6.98%"),
    ("② 完全信息\n不可执行下界", 12254696.55, "curtail", "\\\\\\\\", "−7.53%"),
    ("③ 旧灵敏度\n（仅对照）", 15238244.28, "baseline", "\\\\\\\\", "+14.99%"),
    ("④ 附件1\n典型日口径", 19043406.75, "emer", "", "+43.70%"),
    ("⑤ 无储能\n（逐区间买缺口）", 16407319.63, "soc", "", "+23.81%"),
]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def merge_spans(v_day: np.ndarray, thr: float = 1e-9) -> list[tuple[int, int, float]]:
    """把一天的 144 段按"连续正值"合并成 [(起始区间, 结束区间, 段电量)]。"""
    out, start = [], None
    for t, x in enumerate(v_day):
        pos = x > thr
        if pos and start is None:
            start = t
        elif not pos and start is not None:
            out.append((start, t - 1, float(v_day[start:t].sum())))
            start = None
    if start is not None:
        out.append((start, len(v_day) - 1, float(v_day[start:].sum())))
    return out


def load_main(*, verify_sha: bool = True) -> dict:
    """读主口径台账；默认先验 sha256（不符直接抛错，防止误用旧口径）。"""
    if verify_sha:
        got = _sha256(ART)
        if got != ART_SHA256:
            raise RuntimeError("台账 sha256 与冻结值不符，拒绝使用：\n  期望 %s\n  实际 %s"
                               % (ART_SHA256, got))
    raw = json.loads(ART.read_text(encoding="utf-8"))
    rows, res = raw["rows"], raw["res"]
    if len(rows) != N_DAYS:
        raise ValueError("台账天数 %d != %d" % (len(rows), N_DAYS))
    out = {
        "res": res,
        "dates": [dt.date.fromisoformat(r["date"]) for r in rows],
        "d": np.array([r["d"] for r in rows]),
        "G": np.array([r["G"] for r in rows], float),
        "H": np.array([r["H"] for r in rows], float),
        "C": np.array([r["C"] for r in rows], float),
        "D": np.array([r["D"] for r in rows], float),
        "R_PV": np.array([r["RP"] for r in rows], float),   # 逐区间弃光伏
        "R_G": np.array([r["RG"] for r in rows], float),    # 逐区间弃计划电
        "s0": np.array([r["s0"] for r in rows], float),
        "s1": np.array([r["s1"] for r in rows], float),
        "J_plan_day": np.array([r["J_plan"] for r in rows], float),
        "J_emg_day": np.array([r["J_emg"] for r in rows], float),
        "margin": np.array([r["margin"] for r in rows], float),
        "source": str(ART), "sha256": ART_SHA256, "caliber": res.get("caliber", ""),
    }
    for k in ("G", "H", "C", "D", "R_PV", "R_G"):
        if out[k].shape != (N_DAYS, T):
            raise ValueError("字段 %s 形状 %s != (%d,%d)" % (k, out[k].shape, N_DAYS, T))
    return out


def anchors(m: dict) -> dict:
    H = m["H"]
    spans = [s for row in H for s in merge_spans(row)]
    return {
        "J_plan": float(m["J_plan_day"].sum()),
        "J_emg": float(m["J_emg_day"].sum()),
        "total": float(m["J_plan_day"].sum() + m["J_emg_day"].sum()),
        "QG": float(m["G"].sum()),
        "C_sum": float(m["C"].sum()),
        "D_sum": float(m["D"].sum()),
        "H_kWh": float(H.sum()),
        "emg_days": int((H.sum(axis=1) > 1e-9).sum()),
        "emg_spans": len(spans),
        "max_span_kWh": float(max(s[2] for s in spans)) if spans else 0.0,
        "s_end": float(m["s1"][-1]),
        "soc_min": float(min(m["s0"].min(), m["s1"].min())),
        "soc_max": float(max(m["s0"].max(), m["s1"].max())),
    }


def check_anchors(m: dict, *, verbose: bool = True) -> tuple[dict, list[str]]:
    got, bad = anchors(m), []
    for k, exp in EXPECT.items():
        tol = TOL_COUNT.get(k, TOL_LOOSE.get(k, 0.01))
        diff = abs(got[k] - exp)
        ok = diff <= tol
        if not ok:
            bad.append("%s: 现算 %r vs 说明 %r（差 %r）" % (k, got[k], exp, got[k] - exp))
        if verbose:
            print("  %-12s 现算 %16.4f | 说明 %16.4f | 差 %12.6f | %s"
                  % (k, got[k], exp, got[k] - exp, "OK" if ok else "**FAIL**"))
    return got, bad


def check_chain(m: dict, *, verbose: bool = True) -> list[str]:
    """SOC 链与 η 递推自洽性。"""
    bad = []
    gap = float(np.abs(m["s1"][:-1] - m["s0"][1:]).max())
    rec = max(abs(r0 + ETA * c - d / ETA - s1)
              for r0, c, d, s1 in zip(m["s0"], m["C"].sum(axis=1), m["D"].sum(axis=1), m["s1"]))
    if verbose:
        print("  SOC 链 |s1[i]-s0[i+1]| max = %.8f；日界 η 递推残差 max = %.6f" % (gap, rec))
    if gap > 1e-6:
        bad.append("SOC 日界链断裂，最大间隙 %.8f kWh" % gap)
    if rec > 1e-2:
        bad.append("日界 η 递推残差 %.6f kWh 偏大" % rec)
    lo = min(m["s0"].min(), m["s1"].min())
    hi = max(m["s0"].max(), m["s1"].max())
    if lo < 1200 - 1e-6 or hi > 10800 + 1e-6:
        bad.append("日界 SOC 越界：%.2f ~ %.2f" % (lo, hi))
    return bad


def soc_path(m: dict, i: int) -> np.ndarray:
    """第 i 天的 145 点 SOC 轨迹（S[0]=s0，按 η=0.9 递推）。"""
    s = np.empty(T + 1, float)
    s[0] = m["s0"][i]
    s[1:] = s[0] + np.cumsum(ETA * m["C"][i] - m["D"][i] / ETA)
    return s


def load_inputs(m: dict, *, verbose: bool = True) -> dict:
    """附件1 电价 + 附件2 负载/光伏（Q2 窗口 2025-02-01~12-31 = 索引 31..364），与台账日期硬对齐。"""
    import sys as _sys
    _sys.path.insert(0, r"D:\CMUCU\4对话\code")
    import data_io as D  # noqa: E402

    day = D.load_q1_day()
    price = np.asarray(day["price"], float)
    dl, load_y = D.load_year_load()
    dp, pv_y = D.load_year_pv()
    load_y, pv_y = np.asarray(load_y, float), np.asarray(pv_y, float)
    want = [str(x) for x in m["dates"]]
    got = [str(x)[:10] for x in dl[31:365]]
    if want != got:
        raise ValueError("附件2 与台账日期对不上：%s..%s vs %s..%s" % (want[0], want[-1], got[0], got[-1]))
    out = {"price": price, "load_kW": load_y[31:365], "pv_kW": pv_y[31:365], "dates": m["dates"]}
    out["load_kWh"] = out["load_kW"] * DT
    out["pv_kWh"] = out["pv_kW"] * DT
    if verbose:
        print("  输入对齐 OK：电价 %.4f~%.4f；负载 %.0f~%.0f kW；光伏 %.0f~%.0f kW（%s~%s）"
              % (price.min(), price.max(), out["load_kW"].min(), out["load_kW"].max(),
                 out["pv_kW"].min(), out["pv_kW"].max(), want[0], want[-1]))
    return out


def daily(m: dict, inp: dict) -> dict:
    return {
        "date": [str(d) for d in m["dates"]],
        "load_kWh": inp["load_kWh"].sum(axis=1), "pv_kWh": inp["pv_kWh"].sum(axis=1),
        "G_kWh": m["G"].sum(axis=1), "H_kWh": m["H"].sum(axis=1),
        "C_kWh": m["C"].sum(axis=1), "D_kWh": m["D"].sum(axis=1),
        "R_PV_kWh": m["R_PV"].sum(axis=1), "R_G_kWh": m["R_G"].sum(axis=1),
        "J_plan": m["J_plan_day"], "J_emg": m["J_emg_day"],
        "J_cash": m["J_plan_day"] + m["J_emg_day"],
        "s0": m["s0"], "s1": m["s1"], "margin": m["margin"],
    }


def monthly(m: dict, inp: dict) -> dict:
    acc: dict[str, dict] = {}
    for i, d in enumerate(m["dates"]):
        k = "%04d-%02d" % (d.year, d.month)
        a = acc.setdefault(k, dict.fromkeys(
            ("load_kWh", "pv_kWh", "G_kWh", "H_kWh", "R_PV_kWh", "R_G_kWh", "J_plan", "J_emg"), 0.0))
        a["load_kWh"] += float(inp["load_kWh"][i].sum()); a["pv_kWh"] += float(inp["pv_kWh"][i].sum())
        a["G_kWh"] += float(m["G"][i].sum()); a["H_kWh"] += float(m["H"][i].sum())
        a["R_PV_kWh"] += float(m["R_PV"][i].sum()); a["R_G_kWh"] += float(m["R_G"][i].sum())
        a["J_plan"] += float(m["J_plan_day"][i]); a["J_emg"] += float(m["J_emg_day"][i])
    keys = sorted(acc)
    return {"keys": keys, **{k: np.array([acc[x][k] for x in keys], float) for k in acc[keys[0]]}}


def table3(m: dict) -> dict:
    """论文表 3（四个指定日期的紧急购电段），来自 `res.paper_table3`，并用台账 H 现算复核。"""
    paper = ["2025-03-20", "2025-06-21", "2025-09-23", "2025-12-21"]
    out = {}
    for d in paper:
        segs = m["res"].get("paper_table3", {}).get(d, [])
        i = [j for j, x in enumerate(m["dates"]) if str(x) == d]
        led = merge_spans(m["H"][i[0]]) if i else []
        out[d] = {"segs": segs, "ledger_n": len(led),
                  "ledger_kWh": [round(s[2], 4) for s in led]}
    return out


def top_days(m: dict, k: int = 5) -> dict:
    j = m["J_emg_day"]
    idx = np.argsort(-j)[:k]
    return {"idx": idx.tolist(), "dates": [str(m["dates"][i]) for i in idx],
            "J_emg": [float(j[i]) for i in idx],
            "share_pct": float(100 * j[idx].sum() / j.sum()) if j.sum() else 0.0}


def main() -> int:
    print("== 主口径台账 ==")
    m = load_main()
    print("  sha256 OK（%s…）天数 %d 段/日 %d  日期 %s ~ %s"
          % (m["sha256"][:16], len(m["dates"]), T, m["dates"][0], m["dates"][-1]))
    print("  caliber:", m["caliber"][:80])
    print("== 锚点对表（现算 vs 交付说明） ==")
    _, bad = check_anchors(m)
    bad += check_chain(m)
    print("== 绘图输入 ==")
    inp = load_inputs(m)
    d = daily(m, inp)
    print("  逐日抽样：%s load %.0f / pv %.0f / G %.0f / H %.2f kWh / J_cash %.2f 元 / margin %.3f"
          % (d["date"][0], d["load_kWh"][0], d["pv_kWh"][0], d["G_kWh"][0], d["H_kWh"][0],
             d["J_cash"][0], d["margin"][0]))
    mo = monthly(m, inp)
    print("  月度 %d 个月：ΣJ_cash = %.2f 元" % (len(mo["keys"]), float((mo["J_plan"] + mo["J_emg"]).sum())))
    t = top_days(m)
    print("  紧急费前 5 天：", ", ".join("%s %.0f 元" % (a, b) for a, b in zip(t["dates"], t["J_emg"])),
          "| 占比 %.2f%%" % t["share_pct"])
    print("  弃电：弃光伏 %.2f kWh / 弃计划电 %.2f kWh" % (m["R_PV"].sum(), m["R_G"].sum()))
    print("  论文表3：", {k: v["segs"] for k, v in table3(m).items()})
    print("\nANCHORS:", "PASS" if not bad else "FAIL")
    for b in bad:
        print("  !", b)
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
