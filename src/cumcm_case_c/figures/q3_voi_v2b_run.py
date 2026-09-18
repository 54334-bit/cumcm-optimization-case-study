# -*- coding: utf-8 -*-
r"""Q3 · 用 **v2b 执行器** 重跑 VOI/E3 四臂（隔离运行，零写入 7.6/提交件）。

背景：`7.6对话\output\voi\` 的四臂（epochs={0}/{0,6}/{0,6,12}/{0,6,12,18}）产生于 **v2b 之前**，
其 A3 臂 = v1 头条 13,369,682.34；而作废声明明文"v1 数字不得进任何文档与图表"。
故本脚本在**隔离输出目录**用 v2b 口径重跑这四臂，供 `q3_03`（滚动价值）与 `q3_11`（epochs 消融）出图。

安全设计（红线）：
  * **不改** `7.6对话\code\q76_v2b_full.py`，只在内存里覆盖模块常量 `EPOCHS_USE`；
  * 只调用 `load_data()` 与 `run_arm()`（**两者都不写文件**），**绝不调用** `cmd_run()` / `materialize()`；
  * 所有输出只写到 `D:\CMUCU\6对话\output\q3_voi_v2b\`；
  * 自检：全四时点臂必须逐位复现 v2b 头条 `J_cash = 13,120,194.06`，否则报错退出。

用法：$env:PYTHONPATH="D:\CMUCU\rag\.deps"; $env:PYTHONIOENCODING='utf-8'
      & $py "D:\CMUCU\6对话\code\q3_voi_v2b_run.py"
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from pathlib import Path

CODEX76 = Path(r"D:\CMUCU\7.6对话\code")
CODEX75 = Path(r"D:\CMUCU\7.5对话\code")
OUT = Path(r"D:\CMUCU\6对话\output\q3_voi_v2b")
EXPECT_V2B_J_CASH = 13120194.062139      # v2b 头条（交付件第 147 列）

ARMS = [(0,), (0, 6), (0, 6, 12), (0, 6, 12, 18)]
ARM_TAG = {0: "A0", 6: "A1", 12: "A2", 18: "A3"}


def load_module(path: Path):
    for d in (str(CODEX76), str(CODEX75)):
        if d not in sys.path:
            sys.path.insert(0, d)
    spec = importlib.util.spec_from_file_location("q76_v2b_full_ro", str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["q76_v2b_full_ro"] = mod
    spec.loader.exec_module(mod)          # 有 __main__ 保护，import 不执行主流程、不写盘
    return mod


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    mod = load_module(CODEX76 / "q76_v2b_full.py")
    print("模块已加载（只 import，未执行 cmd_run）", flush=True)
    print("  原 EPOCHS_USE =", getattr(mod, "EPOCHS_USE", None), flush=True)

    print("读数据（附件2/3/4）…", flush=True)
    L, P, price, fc, days = mod.load_data()
    print("  L=%s P=%s price=%s" % (L.shape, P.shape, price.shape), flush=True)

    out = {"source": str(CODEX76 / "q76_v2b_full.py"), "executor": "v2b",
           "note": "隔离重跑：只改内存常量 EPOCHS_USE、只调 run_arm（无写盘）",
           "arms": []}
    for ep in ARMS:
        mod.EPOCHS_USE = ep                 # 内存覆盖
        t = time.time()
        res = mod.run_arm("v2b", L, P, price, fc, days)
        if not res.get("ok"):
            print("  !! 臂 %s 失败：%s" % (ep, res.get("reason")), flush=True)
            return 2
        tot = {k: float(v) for k, v in res["totals"].items()}
        tag = ARM_TAG[max(ep)] if len(ep) > 1 else "A0"
        rec = {"epochs": list(ep), "tag": tag, "totals": tot,
               "n_days": int(res["n_days"]), "soc_min": float(res["soc_min"]),
               "soc_max": float(res["soc_max"]), "S_end": float(res["S_end"]),
               "max_balance_res": float(res["max_balance_res"]),
               "runtime_sec": round(time.time() - t, 1),
               "daily": [{"d": r["d"], "date": r["date"], "J_plan": r["J_plan"],
                          "J_adj": r["J_adj"], "J_emg": r["J_emg"], "J_cash": r["J_cash"],
                          "QH": r["QH"], "QG0": r["QG0"], "QA": r["QA"]} for r in res["rows"]]}
        out["arms"].append(rec)
        print("  arm %-14s J_plan=%.2f J_adj=%.2f J_emg=%.2f J_cash=%.2f  ΣH=%.1f kWh  (%.1fs)"
              % (str(ep), tot["J_plan"], tot["J_adj"], tot["J_emg"], tot["J_cash"],
                 tot.get("QH", float("nan")), rec["runtime_sec"]), flush=True)

    full = [a for a in out["arms"] if len(a["epochs"]) == 4][0]
    got = full["totals"]["J_cash"]
    ok = abs(got - EXPECT_V2B_J_CASH) < 1e-6
    out["self_check"] = {"full_epochs_J_cash": got, "expected": EXPECT_V2B_J_CASH,
                         "match": bool(ok)}
    (OUT / "voi_v2b.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                      encoding="utf-8")
    print("\n自检：全四时点臂 J_cash = %.6f，期望 %.6f，match=%s" % (got, EXPECT_V2B_J_CASH, ok))
    print("产物 ->", OUT / "voi_v2b.json")
    print("总耗时 %.1f s" % (time.time() - t0))
    return 0 if ok else 3


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
