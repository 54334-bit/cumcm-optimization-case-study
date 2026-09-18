"""7.6 全量递归扫描器（只读 7.5/7.6 output，只写 7.6 报告）。

任务：把"定期全量扫描"做成可复跑脚本 + 一份禁引清单（见 _subagent_tasks/q76_scan_guard.md）。

一条命令复跑：
  C:\\Users\\刘嘉琪\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe ^
      D:\\CMUCU\\7.6对话\\code\\q76_scan.py

输出（只写这两处，绝不写 7.5）：
  D:\\CMUCU\\7.6对话\\output\\scan\\scan_report.json
  D:\\CMUCU\\7.6对话\\output\\scan\\scan_report.md

扫描六项：
  1 递归覆盖（文件总数 + 扩展名计数）
  2 陈旧检（含 J_plan|J_cash 且 mtime 早于"锚修正 15:50"，却仍在 live 区）
  3 台账一致性（逐行 json.loads、产物 vs 台账 n_days、同名不同代次）
  4 哈希完整性（自报 hash_unchanged:false / hash_ok!=true；脚本 mtime 晚于产物）
  5 数值不变量 J_cash = J_plan + J_adj + J_emg（rtol 1e-6）
  6 禁引清单素材汇总
"""
from __future__ import annotations

import hashlib
import json
import time
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve()
CODE76 = HERE.parent                      # D:\CMUCU\7.6对话\code
ROOT76 = CODE76.parent                    # D:\CMUCU\7.6对话
PROJ = ROOT76.parent                      # D:\CMUCU
OUT75 = PROJ / "7.5对话" / "output"
OUT76 = ROOT76 / "output"
CODE75 = PROJ / "7.5对话" / "code"
SCAN_DIR = OUT76 / "scan"

# 修线 / 锚修正时刻（任务给定）
T_FEE_REPAIR = "2026-09-12 14:16"   # 费用线修线
T_ANCHOR_FIX = "2026-09-12 15:50"   # 首小时左锚修正完成
T_FILES = {"legacy_1736076": "2026-09-12 14:20:54"}  # q3_data_audit.json 落盘（旧代次内嵌）

FEE_KEYS = ("J_plan", "J_adj", "J_emg", "J_cash")
J_MARKERS = ("J_plan", "J_cash")
RTOL = 1e-6

EXEMPT_DIR_PREFIXES = ("_archive_pre_anchor", "_quarantine_")


def ts(x: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(x))


def mk(s: str) -> float:
    return time.mktime(time.strptime(s, "%Y-%m-%d %H:%M"))


def sha256(p: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with open(p, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def read_json(p: Path):
    try:
        with open(p, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def rel(p: Path, base: Path) -> str:
    return str(p.relative_to(base)).replace("/", "\\")


def walk_files(base: Path) -> list:
    files = []
    for p in base.rglob("*"):
        try:
            if p.is_file():
                files.append(p)
        except OSError:
            continue
    return sorted(files)


# ---------------------------------------------------------------- 1 递归覆盖
def scan_coverage() -> dict:
    inv = {}
    for tag, base in (("7.5", OUT75), ("7.6", OUT76)):
        files = walk_files(base)
        ext = Counter()
        by_dir = Counter()
        total_bytes = 0
        entries = []
        for p in files:
            try:
                st = p.stat()
            except OSError:
                continue
            r = rel(p, base)
            ext[(p.suffix.lower() or "<noext>")] += 1
            top = r.split("\\")[0] if "\\" in r else "<top>"
            by_dir[top] += 1
            total_bytes += st.st_size
            entries.append({"rel": f"{tag}\\{r}", "size": st.st_size,
                            "mtime": ts(st.st_mtime), "sha256": sha256(p)})
        dirs = [str(d.relative_to(base)).replace("/", "\\")
                for d in sorted(base.rglob("*")) if d.is_dir()]
        inv[tag] = {
            "root": str(base),
            "n_files": len(entries),
            "n_dirs": len(dirs),
            "dirs": dirs,
            "total_bytes": total_bytes,
            "by_ext": dict(sorted(ext.items(), key=lambda kv: (-kv[1], kv[0]))),
            "by_top_dir": dict(sorted(by_dir.items(), key=lambda kv: kv[0])),
            "files": entries,
        }
    return inv


# ---------------------------------------------------------------- 2 陈旧检
def scan_stale() -> dict:
    t_fee = mk(T_FEE_REPAIR)
    t_anchor = mk(T_ANCHOR_FIX)
    rows, live, exempt = [], [], []
    for tag, base in (("7.5", OUT75), ("7.6", OUT76)):
        for p in walk_files(base):
            r = rel(p, base)
            top = r.split("\\")[0] if "\\" in r else ""
            if p.suffix.lower() in (".bak",):          # 备份不是 JSON，另在 3/6 项处理
                continue
            if p.suffix.lower() not in (".json", ".jsonl", ".md", ".txt"):
                continue
            try:
                txt = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if not any(k in txt for k in J_MARKERS):
                continue
            mt = p.stat().st_mtime
            row = {
                "root": tag, "rel": r, "mtime": ts(mt),
                "before_repair": bool(mt < t_fee),
                "before_anchor_fix": bool(mt < t_anchor),
                "in_exempt_dir": top.startswith(EXEMPT_DIR_PREFIXES),
                "margin_source": None,
            }
            try:
                m = json.loads(txt)
                if isinstance(m, dict) and isinstance(m.get("margin_source"), str):
                    row["margin_source"] = m["margin_source"]
            except Exception:
                pass
            rows.append(row)
            if row["in_exempt_dir"]:
                exempt.append(row)
            elif row["before_anchor_fix"]:
                live.append(row)
    return {
        "cutoffs": {"fee_repair": T_FEE_REPAIR, "anchor_fix": T_ANCHOR_FIX},
        "n_with_fee_markers": len(rows),
        "n_exempt_in_archive_or_quarantine": len(exempt),
        "n_before_repair_1416_live": sum(1 for r in rows
                                        if r["before_repair"] and not r["in_exempt_dir"]),
        "n_before_anchor_1550_live": len(live),
        "live_before_anchor": live,
        "exempt_before_anchor": exempt,
        "all_rows": rows,
    }


# ---------------------------------------------------------------- 3 台账一致性
LEDGER_SUFFIXES = (".jsonl",)


def scan_ledgers() -> dict:
    ledgers = []
    for tag, base in (("7.5", OUT75), ("7.6", OUT76)):
        for p in walk_files(base):
            if p.suffix.lower() != ".jsonl":
                continue
            lines_ok, lines_bad, records = 0, [], []
            with open(p, "r", encoding="utf-8", errors="replace") as fh:
                for i, line in enumerate(fh, 1):
                    s = line.strip()
                    if not s:
                        continue
                    try:
                        obj = json.loads(s)
                    except Exception as e:
                        lines_bad.append({"line": i, "error": type(e).__name__ + ": " + str(e)[:160],
                                          "head": s[:120]})
                        continue
                    lines_ok += 1
                    if isinstance(obj, dict):
                        records.append((i, obj))
            ledgers.append({
                "root": tag, "rel": rel(p, base), "path": str(p),
                "n_lines_parsed_ok": lines_ok,
                "n_lines_unparseable": len(lines_bad),
                "unparseable": lines_bad,
                "records": records,
            })

    # 3a 产物 vs 台账 n_days
    ndays_rows, ndays_bad = [], []
    for lg in ledgers:
        for ln, obj in lg["records"]:
            out_path = obj.get("out_path")
            if not isinstance(out_path, str):
                continue
            cfg = obj.get("cfg") if isinstance(obj.get("cfg"), dict) else {}
            led = cfg.get("n_days", obj.get("n_days"))
            op = Path(out_path)
            art = read_json(op) if op.is_file() else None
            art_n = art.get("n_days") if isinstance(art, dict) else None
            row = {
                "root": lg["root"], "ledger": lg["rel"], "line": ln,
                "key": obj.get("key"), "out_path": out_path,
                "out_exists": op.is_file(),
                "ledger_n_days": led, "artifact_n_days": art_n,
                "same": (led == art_n) if op.is_file() else None,
            }
            ndays_rows.append(row)
            if row["out_exists"] and not row["same"]:
                ndays_bad.append(row)

    # 3b 同名不同代次（同一产物相对路径被多个不同配置的台账行写入）
    sig_of = defaultdict(set)
    ref_of = defaultdict(list)
    for lg in ledgers:
        for ln, obj in lg["records"]:
            out_path = obj.get("out_path")
            if not isinstance(out_path, str):
                continue
            cfg = obj.get("cfg") if isinstance(obj.get("cfg"), dict) else {}
            sig = json.dumps({k: cfg.get(k) for k in
                              ("billing", "margin", "demand", "q", "q_block", "d0", "d1",
                               "n_days", "epochs", "s_init") if k in cfg},
                             sort_keys=True, ensure_ascii=False)
            sig_of[out_path].add(sig)
            ref_of[out_path].append({"root": lg["root"], "ledger": lg["rel"],
                                     "line": ln, "key": obj.get("key"),
                                     "ts_start": obj.get("ts_start") or obj.get("ts_end"),
                                     "cfg_sig": sig})
    multi, missing = [], []
    for out_path, sigs in sorted(sig_of.items()):
        if len(sigs) > 1:
            multi.append({
                "out_path": out_path,
                "out_exists": Path(out_path).is_file(),
                "n_distinct_cfg": len(sigs),
                "n_refs": len(ref_of[out_path]),
                "refs": ref_of[out_path],
            })
        elif not Path(out_path).is_file():
            missing.append({"out_path": out_path, "n_refs": len(ref_of[out_path]),
                            "refs": ref_of[out_path]})
    for lg in ledgers:          # records 过大，不进报告
        lg.pop("records", None)
    return {
        "ledgers": ledgers,
        "n_ledgers": len(ledgers),
        "n_lines_total_ok": sum(l["n_lines_parsed_ok"] for l in ledgers),
        "n_lines_total_unparseable": sum(l["n_lines_unparseable"] for l in ledgers),
        "n_days_checked": len(ndays_rows),
        "n_days_mismatch": len(ndays_bad),
        "n_days_mismatch_rows": ndays_bad,
        "n_days_all_rows": ndays_rows,
        "n_same_name_multi_gen": len(multi),
        "same_name_multi_gen": multi,
        "n_ledger_refs_missing_artifact": len(missing),
        "ledger_refs_missing_artifact": missing,
        "n_distinct_out_paths": len(sig_of),
    }


# ---------------------------------------------------------------- 4 哈希完整性
def iter_fee_objects(node, ptr=""):
    if isinstance(node, dict):
        if all(k in node for k in FEE_KEYS):
            yield ptr or "/", node
        for k, v in node.items():
            yield from iter_fee_objects(v, ptr + "/" + str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from iter_fee_objects(v, ptr + "/" + str(i))
    elif isinstance(node, str):
        s = node.strip()
        if s[:1] in "{[":                       # 台账 stdout_tail 里的内嵌 JSON
            try:
                yield from iter_fee_objects(json.loads(s), ptr + "<embedded>")
            except Exception:
                return


def scan_hash_integrity() -> dict:
    artifacts = []
    flagged = []
    script_mtimes = {}
    for tag, base in (("7.5", OUT75), ("7.6", OUT76)):
        for p in walk_files(base):
            if p.suffix.lower() != ".json":
                continue
            try:
                txt = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if '"hash_unchanged"' not in txt and '"hash_ok"' not in txt \
                    and '"hash_changed_files"' not in txt:
                continue
            d = read_json(p)
            rows = []

            def collect(obj, ptr=""):
                if isinstance(obj, dict):
                    if "hash_unchanged" in obj:
                        rows.append({"ptr": ptr or "/", "field": "hash_unchanged",
                                     "value": obj["hash_unchanged"]})
                    if "hash_ok" in obj:
                        rows.append({"ptr": ptr or "/", "field": "hash_ok",
                                     "value": obj["hash_ok"]})
                    if "hash_changed_files" in obj:
                        rows.append({"ptr": ptr or "/", "field": "hash_changed_files",
                                     "value": obj["hash_changed_files"]})
                    for k, v in obj.items():
                        collect(v, ptr + "/" + str(k))
                elif isinstance(obj, list):
                    for i, v in enumerate(obj):
                        collect(v, ptr + "/" + str(i))

            if isinstance(d, (dict, list)):
                collect(d)
            bad = []
            for r in rows:
                v = r["value"]
                if r["field"] == "hash_unchanged" and v is False:
                    bad.append(dict(r, why="自报 hash_unchanged=false"))
                elif r["field"] == "hash_ok" and v is not True:
                    bad.append(dict(r, why="自报 hash_ok!=true"))
                elif r["field"] == "hash_changed_files" and isinstance(v, list) and v:
                    bad.append(dict(r, why="hash_changed_files 非空"))
            rec = {"root": tag, "rel": rel(p, base), "mtime": ts(p.stat().st_mtime),
                   "hash_fields": rows, "violations": bad}
            artifacts.append(rec)
            if bad:
                flagged.append(rec)

    # 4b 脚本 mtime 晚于其产物：以台账 cmd 记为生产者，用基准目录解析脚本名
    script_newer, seen = [], set()
    for tag, base, code_base in (("7.5", OUT75, CODE75), ("7.6", OUT76, CODE76)):
        for p in walk_files(base):
            if p.suffix.lower() != ".jsonl":
                continue
            for i, obj in ledger_objects(p):
                out_path = obj.get("out_path")
                if not isinstance(out_path, str):
                    continue
                cmd = obj.get("cmd")
                if isinstance(cmd, list) and len(cmd) > 1:
                    script = cmd[1]
                elif isinstance(cmd, str):
                    parts = cmd.split()
                    script = parts[1] if len(parts) > 1 else None
                else:
                    script = None
                if not script:
                    continue
                sp = code_base / Path(str(script).replace("\\", "/")).name
                op = Path(out_path)
                if not (sp.is_file() and op.is_file()):
                    continue
                k = (tag, str(sp), out_path)
                if k in seen:
                    continue
                seen.add(k)
                smt, omt = sp.stat().st_mtime, op.stat().st_mtime
                script_mtimes.setdefault(str(sp), ts(smt))
                if smt > omt + 1.0:
                    script_newer.append({
                        "root": tag, "ledger": rel(p, base), "line": i,
                        "key": obj.get("key"), "script": str(sp),
                        "script_mtime": ts(smt), "artifact": out_path,
                        "artifact_mtime": ts(omt),
                        "delta_sec": round(smt - omt, 1),
                    })
    return {
        "n_artifacts_with_hash_fields": len(artifacts),
        "n_artifacts_flagged": len(flagged),
        "flagged": flagged,
        "all_artifacts": artifacts,
        "n_script_newer_than_artifact": len(script_newer),
        "script_newer_than_artifact": script_newer,
        "producer_script_mtimes": dict(sorted(script_mtimes.items())),
    }


def ledger_objects(p: Path):
    with open(p, "r", encoding="utf-8", errors="replace") as fh:
        for i, line in enumerate(fh, 1):
            s = line.strip()
            if not s:
                continue
            try:
                obj = json.loads(s)
            except Exception:
                continue
            if isinstance(obj, dict):
                yield i, obj


# ---------------------------------------------------------------- 5 数值不变量
def scan_invariants() -> dict:
    checked, viol = [], []
    files_with_fees = 0
    for tag, base in (("7.5", OUT75), ("7.6", OUT76)):
        for p in walk_files(base):
            if p.suffix.lower() != ".json":
                continue
            d = read_json(p)
            if d is None:
                continue
            hits = list(iter_fee_objects(d))
            if not hits:
                continue
            files_with_fees += 1
            for ptr, obj in hits:
                try:
                    lhs = float(obj["J_cash"])
                    rhs = float(obj["J_plan"]) + float(obj["J_adj"]) + float(obj["J_emg"])
                except Exception:
                    continue
                diff = abs(lhs - rhs)
                scale = max(abs(lhs), abs(rhs), 1.0)
                ok = diff <= RTOL * scale
                row = {"root": tag, "rel": rel(p, base), "ptr": ptr,
                       "J_cash": lhs, "sum3": rhs, "abs_diff": diff,
                       "rel_diff": diff / scale, "ok": ok}
                checked.append(row)
                if not ok:
                    viol.append(row)
    bad_files = sorted({(r["root"], r["rel"]) for r in viol})
    return {
        "rtol": RTOL,
        "n_files_with_fee_keys": files_with_fees,
        "n_objects_checked": len(checked),
        "n_violations": len(viol),
        "violations": viol,
        "n_violating_files": len(bad_files),
        "violating_files": [{"root": a, "rel": b} for a, b in bad_files],
    }


# ---------------------------------------------------------------- 6 禁引清单素材
def scan_ban_material(stale: dict, hashint: dict) -> dict:
    items = []
    # (a) 内嵌旧代次 J_cash 的审计文件
    audit = OUT75 / "q3_data_audit.json"
    hits = []
    if audit.is_file():
        d = read_json(audit)
        for ptr, obj in iter_fee_objects(d) if d is not None else []:
            hits.append({"ptr": ptr, "J_cash": obj.get("J_cash"), "J_plan": obj.get("J_plan")})
    items.append({
        "id": "A_audit_embedded_old_gen",
        "path": str(audit),
        "why": "内含旧代次费用（任务点名 J_cash=17,836,076.11 一类的 anchor 修正前数字）",
        "replacement": "7.6\\output\\b2\\b2_solution.json 或 7.6\\output 最新台账所指向的逐配置产物（需先过 hash_ok）",
        "evidence": {"mtime": ts(audit.stat().st_mtime) if audit.is_file() else None,
                     "embedded_fee_objects": hits[:20], "n_embedded": len(hits)},
    })
    # (b) 隔离目录
    q = OUT75 / "_quarantine_smoke_20260912"
    qf = [rel(p, OUT75) for p in walk_files(q)] if q.is_dir() else []
    items.append({
        "id": "B_quarantine_smoke",
        "path": str(q),
        "why": "冒烟隔离件（口径未定稿即被隔离）",
        "replacement": "7.6\\output 正式台账所指向的产物",
        "evidence": {"n_files": len(qf), "files": qf},
    })
    # (c) 非 JSONL 的 .bak 台账
    baks = [rel(p, OUT75) for p in walk_files(OUT75) if p.suffix.lower() == ".bak"]
    items.append({
        "id": "C_bak_files",
        "path": str(OUT75 / "_g2_manifest_pre_repair.jsonl.bak") + " 等",
        "why": ".bak 备份（含 pre_repair 台账，非当前代次；其中 _g2_manifest_pre_repair.jsonl.bak 名字像 JSONL 但属备份）",
        "replacement": "7.5\\output\\q75_g2_manifest.jsonl（修线后）与 7.6\\output\\q76_e2_manifest.jsonl",
        "evidence": {"n_bak_in_75": len(baks), "bak_files": baks},
    })
    # (d) 归档目录
    arch = OUT75 / "_archive_pre_anchor"
    af = [rel(p, OUT75) for p in walk_files(arch)] if arch.is_dir() else []
    items.append({
        "id": "D_archive_pre_anchor",
        "path": str(arch),
        "why": "锚修正前产物归档（含未修锚费用数字）",
        "replacement": "7.6\\output 现行台账产物",
        "evidence": {"n_files": len(af), "files": af},
    })
    # (e) 7 对话全线数字
    items.append({
        "id": "E_conv7_numbers",
        "path": str(PROJ / "7对话"),
        "why": "7 对话全线数字未接入 7.6 冻结口径（任务点名禁引）",
        "replacement": "7.6\\output 台账 + 7.6 口径冻结文档",
        "evidence": {"exists": (PROJ / "7对话").is_dir()},
    })
    # (f) 附带：陈旧 live 件 + 哈希不可用件
    items.append({
        "id": "F_stale_live",
        "path": "（见 scan_report 第 2 项）",
        "why": "mtime 早于锚修正 15:50 但仍留在 live 区的含费用件",
        "replacement": "对应 7.6 复跑件",
        "evidence": {"n": len(stale["live_before_anchor"]),
                     "files": [f"{r['root']}\\{r['rel']}" for r in stale["live_before_anchor"]]},
    })
    items.append({
        "id": "G_hash_flagged",
        "path": "（见 scan_report 第 4 项）",
        "why": "自报 hash_unchanged:false / hash_ok!=true 或 hash_changed_files 非空的产物",
        "replacement": "重跑并过 hash_ok 的产物",
        "evidence": {"n": len(hashint["flagged"]),
                     "files": [f"{r['root']}\\{r['rel']}" for r in hashint["flagged"]]},
    })
    return {"items": items}


# ---------------------------------------------------------------- main
def main():
    t0 = time.time()
    cov = scan_coverage()
    stale = scan_stale()
    led = scan_ledgers()
    hi = scan_hash_integrity()
    inv = scan_invariants()
    ban = scan_ban_material(stale, hi)
    rep = {
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "scanner": str(HERE),
        "mode": "read-only on 7.5; writes only 7.6\\output\\scan",
        "coverage": cov,
        "stale": stale,
        "ledgers": led,
        "hash_integrity": hi,
        "invariants": inv,
        "ban_material": ban,
        "elapsed_sec": round(time.time() - t0, 2),
    }
    SCAN_DIR.mkdir(parents=True, exist_ok=True)
    with open(SCAN_DIR / "scan_report.json", "w", encoding="utf-8") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=1)

    n75 = cov["7.5"]["n_files"]
    n76 = cov["7.6"]["n_files"]
    L = []
    L.append(f"# 7.6 全量递归扫描报告（{rep['generated']}）")
    L.append("")
    L.append(f"扫描器：`{HERE}`（一条命令复跑，见文末）。耗时 {rep['elapsed_sec']} s。")
    L.append("")
    L.append("## 1 递归覆盖")
    L.append("")
    L.append(f"- 7.5\\output：**{n75}** 个文件 / {cov['7.5']['n_dirs']} 个子目录，"
             f"扩展名计数 " + "、".join(f"`{k}`×{v}" for k, v in cov["7.5"]["by_ext"].items()))
    L.append(f"- 7.6\\output：**{n76}** 个文件 / {cov['7.6']['n_dirs']} 个子目录，"
             f"扩展名计数 " + "、".join(f"`{k}`×{v}" for k, v in cov["7.6"]["by_ext"].items()))
    L.append(f"- 合计 **{n75 + n76}** 个文件（含 `g2_runs*`、`.jsonl`、`.bak`、`_archive_pre_anchor`、"
             f"`_quarantine_*`、`_scratch_rows_out`）")
    L.append("")
    L.append("| 顶层目录 | 7.5 文件数 | 7.6 文件数 |")
    L.append("| --- | --- | --- |")
    tops = sorted(set(cov["7.5"]["by_top_dir"]) | set(cov["7.6"]["by_top_dir"]))
    for t in tops:
        L.append(f"| `{t}` | {cov['7.5']['by_top_dir'].get(t, 0)} | "
                 f"{cov['7.6']['by_top_dir'].get(t, 0)} |")
    L.append("")
    L.append("## 2 陈旧检（含 `J_plan`/`J_cash` 且早于时间闸门）")
    L.append("")
    L.append(f"- 命中费用键的文件：**{stale['n_with_fee_markers']}** 个")
    L.append(f"- 早于**修线 14:16** 且**不在** `_archive_pre_anchor\\` / `_quarantine_*\\` 内："
             f"**{stale['n_before_repair_1416_live']}** 个")
    L.append(f"- 早于**锚修正 15:50** 且**不在**归档/隔离区内的 live 件："
             f"**{stale['n_before_anchor_1550_live']}** 个")
    L.append(f"- 已被归档/隔离（不算 live）：**{stale['n_exempt_in_archive_or_quarantine']}** 个")
    L.append("")
    if stale["live_before_anchor"]:
        L.append("| # | 位置 | mtime | 早于14:16 | margin_source |")
        L.append("| --- | --- | --- | --- | --- |")
        for i, r in enumerate(stale["live_before_anchor"], 1):
            L.append(f"| {i} | `{r['root']}\\{r['rel']}` | {r['mtime']} | "
                     f"{'是' if r['before_repair'] else '否'} | {r['margin_source'] or '-'} |")
    else:
        L.append("无 live 陈旧件。")
    L.append("")
    L.append("## 3 台账一致性")
    L.append("")
    L.append(f"- 台账（`*.jsonl`）**{led['n_ledgers']}** 份，可解析行 **{led['n_lines_total_ok']}** 行")
    L.append(f"- 不可解析行：**{led['n_lines_total_unparseable']}** 行")
    if led["n_lines_total_unparseable"]:
        for lg in led["ledgers"]:
            for b in lg["unparseable"]:
                L.append(f"  - `{lg['root']}\\{lg['rel']}` 第 {b['line']} 行：{b['error']}")
    L.append(f"- 产物 vs 台账 `n_days` 比对：**{led['n_days_checked']}** 条，"
             f"不一致 **{led['n_days_mismatch']}** 条")
    if led["n_days_mismatch"]:
        for r in led["n_days_mismatch"]:
            L.append(f"  - `{r['ledger']}` 第 {r['line']} 行 / `{r['out_path']}`："
                     f"台账 {r['ledger_n_days']} vs 产物 {r['artifact_n_days']}")
    L.append(f"- 同名不同代次（同一产物路径被多个不同配置写入）：**{led['n_same_name_multi_gen']}** 处")
    for m in led["same_name_multi_gen"]:
        L.append(f"  - `{m['out_path']}`：{m['n_distinct_cfg']} 种配置 / {m['n_refs']} 次引用")
        for rf in m["refs"]:
            L.append(f"    - {rf['root']} `{rf['ledger']}` L{rf['line']} key=`{rf['key']}` "
                     f"ts={rf['ts_start']} cfg={rf['cfg_sig']}")
    L.append(f"- 台账指向但产物缺失：**{led['n_ledger_refs_missing_artifact']}** 处")
    for m in led["ledger_refs_missing_artifact"]:
        L.append(f"  - `{m['out_path']}`（{m['n_refs']} 次引用）")
    L.append("")
    L.append("## 4 哈希完整性")
    L.append("")
    L.append(f"- 带哈希字段的产物：**{hi['n_artifacts_with_hash_fields']}** 个，"
             f"其中自报异常：**{hi['n_artifacts_flagged']}** 个")
    for r in hi["flagged"]:
        L.append(f"  - `{r['root']}\\{r['rel']}`（{r['mtime']}）：")
        for v in r["violations"]:
            L.append(f"    - `{v['ptr']}` {v['why']}（值 {json.dumps(v['value'], ensure_ascii=False)[:120]}）")
    L.append(f"- 脚本 mtime **晚于**其产物：**{hi['n_script_newer_than_artifact']}** 件")
    for r in hi["script_newer_than_artifact"]:
        L.append(f"  - `{r['script']}`（{r['script_mtime']}）晚于 `{r['artifact']}`"
                 f"（{r['artifact_mtime']}，+{r['delta_sec']}s）")
    L.append("")
    L.append("## 5 数值不变量 `J_cash = J_plan + J_adj + J_emg`（rtol 1e-6）")
    L.append("")
    L.append(f"- 含四项费用键的 JSON：**{inv['n_files_with_fee_keys']}** 个；"
             f"被查对象 **{inv['n_objects_checked']}** 处（含台账 `stdout_tail` 内嵌 JSON）")
    L.append(f"- 违例：**{inv['n_violations']}** 处，涉及 **{inv['n_violating_files']}** 个文件")
    for r in inv["violations"][:200]:
        L.append(f"  - `{r['root']}\\{r['rel']}` @ `{r['ptr']}`："
                 f"J_cash={r['J_cash']:.6f} sum3={r['sum3']:.6f} "
                 f"abs={r['abs_diff']:.3e} rel={r['rel_diff']:.3e}")
    if inv["n_violations"] > 200:
        L.append(f"  - （其余 {inv['n_violations'] - 200} 处见 scan_report.json）")
    L.append("")
    L.append("## 6 禁引清单素材（详见 `7.6对话\\禁引清单_Q3_20260912.md`）")
    L.append("")
    for it in ban["items"]:
        ev = it["evidence"]
        n = None
        for k in ("n", "n_files", "n_embedded", "n_bak_in_75"):
            if isinstance(ev.get(k), int):
                n = ev[k]
                break
        if n is None and isinstance(ev.get("files"), list):
            n = len(ev["files"])
        if n is None:
            n = "存在" if ev.get("exists") else "—"
        L.append(f"- **{it['id']}** `{it['path']}`：{it['why']}（计数 {n}）→ 替代：{it['replacement']}")
    L.append("")
    L.append("## 复跑命令")
    L.append("")
    L.append("```powershell")
    L.append("C:\\Users\\刘嘉琪\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe "
             "D:\\CMUCU\\7.6对话\\code\\q76_scan.py")
    L.append("```")
    L.append("")
    L.append("## 只读声明")
    L.append("")
    L.append("本扫描器只调用 `open(..., 'r')` / `Path.stat()` / `hashlib`，全部写操作的目标路径均在 "
             "`D:\\CMUCU\\7.6对话\\output\\scan\\` 下。7.5 侧零写入的核对方式：")
    L.append("比对 `scan_report.json.coverage['7.5'].files` 里每个文件的 `size` / `mtime` / `sha256` 与磁盘现值；"
             "任一被改写，`sha256` 必变。")
    (SCAN_DIR / "scan_report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"OK 7.5 files={n75} 7.6 files={n76} stale_live={stale['n_before_anchor_1550_live']} "
          f"bad_lines={led['n_lines_total_unparseable']} ndays_mismatch={led['n_days_mismatch']} "
          f"multi_gen={led['n_same_name_multi_gen']} hash_flagged={hi['n_artifacts_flagged']} "
          f"script_newer={hi['n_script_newer_than_artifact']} inv_viol={inv['n_violations']} "
          f"elapsed={rep['elapsed_sec']}s")
    print(f"-> {SCAN_DIR / 'scan_report.json'}")
    print(f"-> {SCAN_DIR / 'scan_report.md'}")


if __name__ == "__main__":
    main()
