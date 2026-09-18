# -*- coding: utf-8 -*-
"""全局陷阱雷达（只读；只写 8对话\output\global_trap_scan.json）
扫描六类风险：
 A 作废数字仍被当现行值（Q3 v1 13,369,682.34 / 旧哈希 9159846F …）
 B 版本标记（v1/v2）是否与"现行=v2"一致
 C 落位口径（是否还有文件把"标签对齐"当现行）
 D 官方模板是否被改动（size/mtime 对照已知值）
 E 我方 Q4 关键数字在文档/证据里是否一致
 F 交付包 sha256 清单是否自洽（逐条重算）
"""
import os, re, json, hashlib, time

ROOT = r"D:\CMUCU"
OUT = r"D:\CMUCU\8对话\output\global_trap_scan.json"
SKIP = (".git", "__pycache__", ".deps", ".venv", ".mplcache", ".runtime_index", "node_modules",
        "_legacy_archive", "corpus_L1_cases", "PPTreference", "_refs", ".scipy_tmp")

MODEL_FILES = [  # 只扫"模型/交付/论文素材"层，不扫语料与工具
    "8对话", "Q3交付", "5对话", "3对话", "7.5对话", "7.6对话", "4对话", "6对话", "外部意见",
]

STALE = {
    "13,369,682": "Q3 v1 数字（作废）",
    "13369682": "Q3 v1 数字（作废）",
    "9159846F": "Q3 v1 作废哈希",
    "13,456,394": "7.5 版 Q3 C 读法数字（已被 v2 取代）",
    "18,076,037": "7 对话 Q3 旧数字",
    "13,626,881": "7.5 版 Q3 A 读法旧数字",
}
CURRENT_Q4 = ["13,850,454.64", "13,727,033.66"]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


res = {"A_stale": [], "B_version": [], "C_mapping": [], "D_template": [], "E_q4num": [], "F_pkg": []}

# ---------- A/B/C/E：文档层扫描 ----------
for top in MODEL_FILES:
    base = os.path.join(ROOT, top)
    if not os.path.isdir(base):
        continue
    for dp, dn, fn in os.walk(base):
        dn[:] = [d for d in dn if d not in SKIP and not d.startswith(".mpl")]
        for f in fn:
            if not f.endswith((".md", ".txt", ".json")):
                continue
            p = os.path.join(dp, f)
            try:
                if os.path.getsize(p) > 3_000_000:
                    continue
                t = open(p, encoding="utf-8", errors="ignore").read()
            except Exception:
                continue
            rel = os.path.relpath(p, ROOT)
            for k, why in STALE.items():
                if k in t:
                    guarded = any(w in t for w in ("作废", "VOID", "void", "已废", "不再有效"))
                    res["A_stale"].append({"file": rel, "key": k, "why": why, "guarded": guarded})
            if ("作废声明" in t or "VOID" in f) and "9159846F" in t:
                res["B_version"].append({"file": rel, "note": "含 v1 作废哈希（应仅出现在作废语境）"})
            if "标签对齐" in t and not any(w in t for w in ("作废", "不得", "禁止", "错误", "旧", "方案B", "方案 B", "已废")):
                res["C_mapping"].append({"file": rel, "note": "出现'标签对齐'且无作废限定"})
            hit = [c for c in CURRENT_Q4 if c in t]
            if hit:
                res["E_q4num"].append({"file": rel, "nums": hit})

# ---------- D：官方模板未被改动 ----------
TPL = {
    "result1.xlsx": 13323, "result2.xlsx": 18397, "result3.xlsx": 265429,
    "result4-2.xlsx": 18397, "result4-3.xlsx": 265429,
}
for f, sz in TPL.items():
    p = os.path.join(ROOT, "赛题", "C题", "附件", "附件5", f)
    ok = os.path.exists(p) and os.path.getsize(p) == sz
    res["D_template"].append({"file": f, "size": os.path.getsize(p) if os.path.exists(p) else None,
                              "expected": sz, "pass": bool(ok),
                              "mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(p))) if os.path.exists(p) else None})

# ---------- F：交付包清单自洽 ----------
PKG = os.path.join(ROOT, "8对话", "交付包_Q4-2_波动电价完整购电策略")
man = os.path.join(PKG, "交付清单.md")
if os.path.exists(man):
    txt = open(man, encoding="utf-8").read()
    rows = re.findall(r"\| `([^`]+)` \| (\d+) \| `([0-9a-f]{64})` \|", txt)
    bad = []
    for rel, sz, h in rows:
        p = os.path.join(PKG, rel.replace("/", os.sep))
        if not os.path.exists(p):
            bad.append({"file": rel, "why": "missing"})
        elif os.path.getsize(p) != int(sz) or sha(p).lower() != h.lower():
            bad.append({"file": rel, "why": "size/sha mismatch"})
    res["F_pkg"] = {"n_listed": len(rows), "bad": bad}

json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

print("=== 全局陷阱雷达 ===", flush=True)
a_unguarded = [x for x in res["A_stale"] if not x["guarded"]]
print("A 作废数字命中 %d 处，其中**未加作废限定** %d 处" % (len(res["A_stale"]), len(a_unguarded)), flush=True)
for x in a_unguarded[:15]:
    print("   ⚠ %s  [%s] %s" % (x["file"], x["key"], x["why"]), flush=True)
print("B 版本标记异常 %d 处" % len(res["B_version"]), flush=True)
for x in res["B_version"][:8]:
    print("   · %s  %s" % (x["file"], x["note"]), flush=True)
print("C 落位口径可疑 %d 处" % len(res["C_mapping"]), flush=True)
for x in res["C_mapping"][:10]:
    print("   ⚠ %s  %s" % (x["file"], x["note"]), flush=True)
print("D 官方模板 5 项：" + ("全部未被改动 ✓" if all(x["pass"] for x in res["D_template"]) else "有异常！"), flush=True)
for x in res["D_template"]:
    print("   %s size=%s(期望 %s) %s" % (x["file"], x["size"], x["expected"], "PASS" if x["pass"] else "FAIL"), flush=True)
print("E 我方 Q4 数字出现于 %d 个文件" % len(res["E_q4num"]), flush=True)
print("F 交付包清单：%d 条，异常 %d 条" % (res["F_pkg"].get("n_listed", 0), len(res["F_pkg"].get("bad", []))), flush=True)
for x in res["F_pkg"].get("bad", [])[:10]:
    print("   ⚠ %s  %s" % (x["file"], x["why"]), flush=True)
print("已落盘 " + OUT, flush=True)
