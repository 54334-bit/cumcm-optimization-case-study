# -*- coding: utf-8 -*-
"""因果裕度非预见口径的交付包：打包前从 result2.xlsx 自身 + 官方附件独立复算，再打包 + 哈希清单。"""
import sys, os, json, shutil, hashlib, datetime as dt
sys.path.append("D:\\CMUCU\\rag\\.deps")
import numpy as np, openpyxl

B = "D:\\CMUCU\\5\u5bf9\u8bdd\\"
OUT = B + "\u4ea4\u4ed8\u5305_Q2_\u56e0\u679c\u88d5\u5ea6\u975e\u9884\u89c1"
XLSX = B + "result2.xlsx"
A1 = r"D:\CMUCU\赛题\C题\附件\附件1.xlsx"
A2 = r"D:\CMUCU\赛题\C题\附件\附件2.xlsx"
T, DT = 144, 1 / 6
EBAR, SMIN, SMAX, ETA = 5000 * DT, 1200.0, 10800.0, 0.9
DAYS = list(range(31, 365))
FAIL = []


def ck(n, c, d=""):
    print(("PASS  " if c else "FAIL  ") + n + ("  | " + str(d) if d else ""))
    if not c:
        FAIL.append(n)


w1 = openpyxl.load_workbook(A1)["Sheet1"]
price = np.array([w1.cell(r, 2).value for r in range(2, 146)], float)
w2 = openpyxl.load_workbook(A2)
L = np.array([[w2["小区负载"].cell(d + 2, c).value for c in range(2, 146)] for d in DAYS], float)
PV = np.array([[w2["光伏发电实际功率"].cell(d + 2, c).value for c in range(2, 146)] for d in DAYS], float)
wb = openpyxl.load_workbook(XLSX)
ws1, ws2, ws3 = wb["计划购电量"], wb["充放电量"], wb["紧急购电量"]
G = np.zeros((len(DAYS), T)); jp = 0.0; mx = 0.0
for i in range(len(DAYS)):
    r = 2 + i
    for t in range(T):
        G[i, t] = ws1.cell(r, 2 + t).value or 0
    v = float(np.dot(price, G[i])); jp += v
    mx = max(mx, abs(v - (ws1.cell(r, 147).value or 0)))
ck("表1 逐行购电费 == Σp·G", mx < 1e-3, "max %.2e" % mx)
ck("表1 全年计划费 == 12,891,818.24", abs(jp - 12891818.24) < 0.05, "%.4f" % jp)
ck("表1 全年购电量 == 21,283,432.62", abs(G.sum() - 21283432.62) < 1, "%.4f" % G.sum())
soc = np.zeros((len(DAYS), 2))
for i in range(len(DAYS)):
    soc[i, 0] = ws2.cell(2 + 6 * i, 6).value or 0
    soc[i, 1] = ws2.cell(3 + 6 * i, 6).value or 0
ck("表2 SOC 跨日链无断点", float(np.abs(soc[:-1, 1] - soc[1:, 0]).max()) < 1e-3)
ck("表2 SOC ∈ [1200,10800]", soc.min() >= 1199.99 and soc.max() <= 10800.01, "%.1f~%.1f" % (soc.min(), soc.max()))
v3 = [ws3.cell(r, 3).value for r in range(2, ws3.max_row + 1)]
nz = [x for x in v3 if x]
Htot = 0.0; runs = 0
s = float(soc[0, 0])
for i in range(len(DAYS)):
    s = float(soc[i, 0]); prev = False
    for t in range(T):
        gap = L[i, t] * DT - PV[i, t] * DT - G[i, t]
        if gap > 1e-12:
            dd = max(0.0, min(EBAR, ETA * max(0.0, s - SMIN), gap))
            s -= dd / ETA; h = gap - dd; Htot += h
            if h > 1e-6:
                if not prev:
                    runs += 1
                prev = True
            else:
                prev = False
        else:
            s += ETA * max(0.0, min(EBAR, (SMAX - s) / ETA, -gap)); prev = False
ck("表3 段数 == 375", len(nz) == 375 and runs == 375, "%d / greedy %d" % (len(nz), runs))
ck("表3 电量 == 55,801.046 kWh", abs(sum(nz) - 55801.046) < 0.05 and abs(Htot - 55801.046) < 0.05,
   "sheet %.4f / greedy %.4f" % (sum(nz), Htot))
if os.path.exists(OUT):
    shutil.rmtree(OUT)
os.makedirs(OUT + "\\evidence\\code", exist_ok=True)
shutil.copy2(XLSX, OUT + "\\result2.xlsx")
shutil.copy2(B + "\u4ea4\u4ed8\u8bf4\u660e_Q2_\u56e0\u679c\u88d5\u5ea6\u975e\u9884\u89c1.md", OUT + "\\\u4ea4\u4ed8\u8bf4\u660e_Q2_\u56e0\u679c\u88d5\u5ea6\u975e\u9884\u89c1.md")
shutil.copy2(B + "\u9644\u5f55_Q2\u53e3\u5f84\u5bf9\u7167.md", OUT + "\\\u9644\u5f55_Q2\u53e3\u5f84\u5bf9\u7167.md")
EVID = ["q2_emg_detail.json", "q2_cp5_verify_causal.json", "q2_cp4_materialize_causal.json",
        "q2_v5_gate_probe.json",
        "trust_layer_verify.json", "q2_forecast_scan8.json", "q2_forecast_scan9.json",
        "review_R20_\u56e0\u679c\u88d5\u5ea6\u53e3\u5f84\u4ea4\u4ed8\u590d\u6838.md",
        "q2_mapping_discriminate.json", "q2_probe_where.json", "q2_forecast_scan.json"]
n = 0
for f in EVID:
    src = B + "output\\" + f
    if os.path.exists(src):
        shutil.copy2(src, OUT + "\\evidence\\" + f); n += 1
SCRIPTS = ["q2_v2_micro.py", "q2_milp_plan.py", "q2_emg_detail.py", "q2_s5_materialize_causal.py",
           "q2_s6_verify_causal.py", "q2_pack_causal.py", "q2_trust_layer.py", "q2_forecast_scan9.py"]
nc = 0
for f in SCRIPTS:
    src = B + "code\\" + f
    if os.path.exists(src):
        shutil.copy2(src, OUT + "\\evidence\\code\\" + f); nc += 1


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


files = []
for root, _, fs in os.walk(OUT):
    for f in fs:
        fp = os.path.join(root, f)
        files.append((os.path.relpath(fp, OUT).replace("\\", "/"), os.path.getsize(fp), sha(fp)))
lines = ["# Q2 交付包清单（主口径：非预见 + 因果保守裕度）", "",
         "生成：%s" % dt.datetime.now().isoformat(timespec="seconds"),
         "口径：**0:00 计划用可得信息（负荷已知、光伏=过去4天均值×因果保守裕度）；结算用附件2 实际负载/实际光伏；5 倍紧急购电**",
         "", "关键数字：**全年购电费用 13,252,341.09 元**（计划 12,891,818.24 + 紧急 360,522.85）；紧急 **242 天 / 375 段 / 55,801.05 kWh**；计划购电量 21,283,432.62 kWh。",
         "", "**提交件：`result2.xlsx`**（表3 按 375 段真实时段动态展开）。",
         "", "对照：完全信息下界 12,254,696.55 元（紧急 0，不可执行口径，仅下界）；附件1 典型日预报口径 19,043,406.75 元。",
         "", "| 文件 | 字节 | sha256 |", "| --- | ---: | --- |"]
for rel, sz, h in sorted(files):
    lines.append("| `%s` | %d | `%s` |" % (rel, sz, h[:16]))
open(OUT + "\\\u4ea4\u4ed8\u6e05\u5355.md", "w", encoding="utf-8").write("\n".join(lines))
print("\n=== 打包 ===\n 目录:", OUT, "| 文件:", len(files), "| evidence:", n, "| code:", nc)
print("结论:", "校验全绿" if not FAIL else ("失败 " + str(FAIL)))
