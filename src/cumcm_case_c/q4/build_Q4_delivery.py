# -*- coding: utf-8 -*-
"""按 Q1/Q2/Q3 同构，构建正式交付位 D:\CMUCU\Q4交付\
  目录：00 索引 / 01 提交件 / 02 交付说明与附录 / 03 论文素材 / 04 证据 / 05 代码 / 06 图件 + manifest.sha256.json
  只写 Q4交付\；来源一律只读复制自 8对话\。缺项在索引里显式标注。
"""
import os, shutil, hashlib, json, time

S = r"D:\CMUCU\8对话"
D = r"D:\CMUCU\Q4交付"
SUBDIRS = ["01_提交件", "02_交付说明与附录", "03_论文素材", "04_证据", "05_代码", "06_图件"]
for s in SUBDIRS:
    os.makedirs(os.path.join(D, s), exist_ok=True)

SUB = {  # 目标子目录 -> 源文件列表（只读复制）
    "01_提交件": [r"output\result4-2.xlsx", r"output\result4-3.xlsx"],
    "02_交付说明与附录": [
        r"交付包_Q4-2_波动电价完整购电策略\交付说明_Q4-2_波动电价完整购电策略.md",
        r"交付说明模板_Q4-3.md", r"监理回执整改说明_Q4.md",
        r"交付包_Q4-2_波动电价完整购电策略\稳健性与封存清单_Q4.md",
        r"防陷阱策略_Q4.md", r"Q4-3_继承规格与执行器结论更正.md", r"出题人视角_反AI意图与评分识别点.md",
        r"交付说明_Q4-3_待大队长签发.md", r"状态更新_交付前核对.md",
    ],
    "03_论文素材": [r"Q4_稳健性与裕度结论.md", r"三方共验_Q4交付件_裁定.md", r"三方共验_Q4前沿与结构性遗漏_裁定.md"],
    "04_证据": [
        r"output\q4_data_anchor.json", r"output\q4_cp2_gate.json", r"output\q4_cp2_checkpoint.json",
        r"output\q4_validator_result.json", r"output\q4_validator_result4-3.json",
        r"output\q4_counterfactual_2x2.json", r"output\q4_price_block_decomp.json",
        r"output\q4_gate_segments.json", r"output\q4_margin_deepdive.json", r"output\q4_margin_M2_scan.json",
        r"output\q4_verify_soc.json", r"output\q4_probe_price_caliber_v2.json", r"output\q4_probe_lambda_joint.json",
        r"output\q4_q3v2_gate.json", r"output\q4_q3v2_solution.json",
        r"output\q4_q43_qm_scan.json", r"output\q4_q43_2x2.json",
        r"output\q4_site_guard_report.md", r"output\q4_cross_consistency_report.md",
        r"output\q4_leakage_injection.json",
        r"output\q4_quality_guard_report.md", r"output\q4_design_guard_report.md",
        r"output\q4_validator_review_report.md", r"output\site_guard_fingerprint.json",
        r"output\global_trap_scan.json",
    ],
    "05_代码": [r"code\q4_data_io.py", r"code\q4_det_seq.py", r"code\q4_materialize.py", r"code\q4_validator.py",
                r"code\q4_q3v2_driver.py", r"code\q4_validator_q3struct.py", r"code\q4_counterfactual_2x2.py",
                r"code\q4_price_block_decomp.py", r"code\site_guard_fingerprint.py", r"code\global_trap_scan.py",
                r"code\q4_q43_qm_scan.py", r"code\q4_q43_2x2_and_pricearm.py", r"code\build_Q4_delivery.py",
                r"code\fix_result4_3_fee.py"],
    # 交付位根目录的交接件（在下方单独复制）
}
missing = []
for sub, files in SUB.items():
    for rel in files:
        src = os.path.join(S, rel)
        if not os.path.exists(src):
            missing.append(rel)
            continue
        shutil.copy2(src, os.path.join(D, sub, os.path.basename(rel)))

# 根目录交接件
for extra in (r"Q4_最终产物清单与交接.md",):
    src = os.path.join(S, extra)
    if os.path.exists(src):
        shutil.copy2(src, os.path.join(D, os.path.basename(extra)))
    else:
        missing.append(extra)

# 已回填的 Q4-3 交付说明：另存为正式名（保留原名副本，不删任何已有文件）
_spec = os.path.join(S, "交付说明_Q4-3_待大队长签发.md")
if os.path.exists(_spec):
    shutil.copy2(_spec, os.path.join(D, "02_交付说明与附录", "交付说明_Q4-3.md"))

# 交付说明_Q4-3 尚未回填：放一份"未完成"占位说明，避免误读
ph = os.path.join(D, "02_交付说明与附录", "交付说明_Q4-3_未回填.md")
if not os.path.exists(ph):
    open(ph, "w", encoding="utf-8").write(
        "# 交付说明（Q4-3）｜**未回填（占位）**\n\n"
        "> 本问的正式交付说明以 `交付说明模板_Q4-3.md` 为模板，待回填 Q3 v2 哈希与全部关键数字后生效。\n"
        "> 在回填完成前，**不得**据本目录的 `result4-3.xlsx` 对外宣称口径齐全。\n")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


rows, files = [], []
for dp, dn, fn in os.walk(D):
    for f in fn:
        p = os.path.join(dp, f)
        files.append(os.path.relpath(p, D).replace("\\", "/"))
files.sort()
for rel in files:
    p = os.path.join(D, rel)
    rows.append("| `%s` | %d | `%s` |" % (rel, os.path.getsize(p), sha(p)))

readme = """# Q4 交付索引（问题四：波动电价下重算问题二与问题三）

> 生成：%s ｜ 线别：对话 8（Q4）｜ 结构对齐 `Q1交付/` `Q2交付/` `Q3交付/`

## 一、交付物

| 文件 | 内容 | 状态 |
| --- | --- | --- |
| `01_提交件/result4-2.xlsx` | 波动电价下问题二的完整购电策略（3 表） | ✅ 已完成（独立校验 11/11、errors=[]） |
| `01_提交件/result4-3.xlsx` | 波动电价下问题三的完整购电策略（4 表） | ✅ 已产出（待回填交付说明与终检） |

## 二、关键数字

| 口径 | 全年费用（元） | 说明 |
| --- | ---: | --- |
| Q2（附件1 价，非预见+因果裕度） | 13,252,341.09 | 继承基线（已冻结） |
| **Q4-2（附件4 价）** | **13,850,454.64** | 相对 Q2 **+4.51%%** |
| Q3 v2（附件1 价，v2b 执行器） | **13,120,194.06** | 继承自 `Q3交付/`（旧 13,369,682.34 已作废） |
| **Q4-3（附件4 价，v2b）** | **13,727,033.66** | 相对 Q3 v2 **+4.63%%**；闸门复现 Q3 v2 差 +0.00 |

**机制**：附件1 为附件4 的逐时段全年均值；波动电价抬高成本源于"价格日级水平与净负荷正相关（corr 0.9824）"，
2×2 反事实把它拆为**价格环境效应 +744,522.48** 与**重优化效应 −146,408.94**（净 +598,113.55）。

## 三、目录

| 目录 | 内容 |
| --- | --- |
| `01_提交件/` | 两份 result 文件 |
| `02_交付说明与附录/` | Q4-2 交付说明、Q4-3 模板与占位、监理整改说明、稳健性清单、防陷阱策略、继承规格、出题人视角 |
| `03_论文素材/` | 稳健性与封存清单、三方共验裁定（交付件/前沿） |
| `04_证据/` | 锚点、闸门、checkpoint、两部校验器结果、2×2、分块拆解、段数、裕度、λ、价格口径、指纹、全局陷阱雷达、三份监理报告 |
| `05_代码/` | 主线/物化/校验/Q4-3 驱动/反事实/指纹/扫描等脚本快照 |
| `06_图件/` | **由队长落地**（对话 8 只提供图件数据源清单，见 `Q4_最终产物清单与交接.md` §六） |

## 四、待补（不影响两份提交件成立）

1. `02_交付说明与附录/交付说明_Q4-3.md` —— 待回填（Q3 v2 哈希 `39F4C8DF…` + 全部关键数字 + 读法 C 声明）；
2. `03_论文素材/` —— 2×2 表、分块拆解表、机制段、17.9%% 参数推导、D/U 两读法并列；
3. `06_图件/` —— 5 张图（SVG+300dpi PNG+manifest）；
4. Q4-3 的独立复算报告（现场监理 `q4_site_guard` 在跑）。

## 五、清单

| 文件 | 字节 | sha256 |
| --- | ---: | --- |
""" % time.strftime("%Y-%m-%d %H:%M")

open(os.path.join(D, "00_README_交付索引.md"), "w", encoding="utf-8").write(readme + "\n".join(rows) + "\n")
json.dump({"generated": time.strftime("%Y-%m-%d %H:%M:%S"),
           "files": {r: sha(os.path.join(D, r)) for r in files if not r.endswith("manifest.sha256.json")}},
          open(os.path.join(D, "manifest.sha256.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

print("Q4交付 已构建：%d 个文件" % len(files), flush=True)
for r in files:
    print("   %s" % r, flush=True)
if missing:
    print("⚠ 源文件缺失（未复制）：", missing, flush=True)
