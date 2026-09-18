# -*- coding: utf-8 -*-
"""放行闸门 G1–G5 自查（主对话亲做）：结构/数值/红线/一致性/表述。"""
import hashlib, os, re
from openpyxl import load_workbook

R = r"D:\CMUCU\7.6对话"
X = os.path.join(R, "交付", "Q3交付", "01_提交件", "result3.xlsx")
T = r"D:\CMUCU\赛题\C题\附件\附件5\result3.xlsx"
TPL_SHA = "c59da470cabd0be23f602c95c8aa9d11ec224a0cdac216b3e1f218e65d006bdc"
FORBID = ["q=0.8 最优", "q=0.5 更优", "Q3 比 Q2 改进", "比 Q2 改进"]

def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""): h.update(c)
    return h.hexdigest()

out = []
out.append(f"# 放行闸门判定（主对话亲做）\n\n- 生成：{__import__('datetime').datetime.now():%Y-%m-%d %H:%M}\n")
wb, wt = load_workbook(X, read_only=True, data_only=True), load_workbook(T, read_only=True, data_only=True)
sn_o, sn_t = wb.sheetnames, wt.sheetnames
ok1 = sn_o == sn_t
dim_o, dim_t = {}, {}
for s in sn_o:
    dim_o[s] = (wb[s].max_row, wb[s].max_column); dim_t[s] = (wt[s].max_row, wt[s].max_column)
hdr_ok = all([c for c in wb[s].iter_rows(min_row=1, max_row=1, values_only=True)][0]
             == [c for c in wt[s].iter_rows(min_row=1, max_row=1, values_only=True)][0]
             for s in ("计划购电量", "调整购电量"))
tpl_ok = sha(T).lower() == TPL_SHA
gi = dim_o["计划购电量"]; g2 = dim_o["调整购电量"]
out.append("## G1 结构\n")
out.append(f"- 表名与顺序 = 模板：{ok1}（{sn_o}）\n- 主表尺寸：计划 {gi} / 调整 {g2}（模板 {dim_t['计划购电量']}）\n"
           f"- 表头逐格 = 模板：{hdr_ok}\n- 模板 sha256 未变：{tpl_ok}（{sha(T)[:16]}…）\n")
plan = [r for r in wb["计划购电量"].iter_rows(min_row=2, values_only=True)]
adj = [r for r in wb["调整购电量"].iter_rows(min_row=2, values_only=True)]
tot = sum(r[146] for r in plan); totA = sum(r[146] for r in adj)
d = abs(tot - 13369682.337448763) / 13369682.337448763
out.append("## G2 数值\n")
out.append(f"- 计划表第147列全年合计 = **{tot:.6f}**（目标 13,369,682.337449；相对差 {d:.2e}）\n"
           f"- 调整表第147列全年合计 = {totA:.6f}（与计划表差 {abs(tot-totA):.2e}）\n"
           f"- 天数 = {len(plan)}（应为 334）\n")
soc = [r for r in wb["充放电量"].iter_rows(min_row=2, values_only=True)]
charges = [r[2] for r in soc if r[2] is not None]; dis = [r[3] for r in soc if r[3] is not None]
svals = [r[5] for r in soc if r[5] is not None]
neg = [v for v in charges + dis if v < 0]
out.append("## G3 红线\n")
out.append(f"- 4h 段限值 = 20000 kWh；最大充电 {max(charges):.3f}、最大放电 {max(dis):.3f}；越限 0：{max(charges)<=20000 and max(dis)<=20000}\n"
           f"- 充放电非负：{len(neg)==0}\n- 储电量范围 [{min(svals):.3f}, {max(svals):.3f}] ⊂ [1200,10800]：{min(svals)>=1200-1e-6 and max(svals)<=10800+1e-6}\n")
fd = os.path.join(R, "交付", "Q3交付", "03_论文素材", "论文表1表2表3_四个指定日期.md")
out.append("## G4 一致性\n")
out.append(f"- 四日期回填件存在：{os.path.exists(fd)}；其中含 46227.7086（3-20 全天费，与逐日对账一致）："
           f"{('46227.7086' in open(fd, encoding='utf-8').read()) if os.path.exists(fd) else False}\n")
bad = []
for root, _, files in os.walk(R):
    if "外部意见" in root: continue
    for fn in files:
        if fn.endswith(".md"):
            txt = open(os.path.join(root, fn), encoding="utf-8", errors="ignore").read()
            for s in FORBID:
                if s in txt: bad.append((os.path.join(root, fn), s))
out.append("## G5 表述\n")
out.append(f"- 违禁表述命中：{len(bad)} 处" + ("" if not bad else "\n" + "\n".join(f"  - {a} :: {b}" for a, b in bad)) + "\n")
gate = ok1 and hdr_ok and tpl_ok and d < 1e-6 and len(plan) == 334 and max(charges) <= 20000 and not neg
out.append(f"## 结论\n\n**{'可放行' if gate else '不予放行'}**（G1–G3 硬判据；G4/G5 见上）\n")
p = os.path.join(R, "放行闸门判定_20260913.md")
open(p, "w", encoding="utf-8").write("\n".join(out))
print("\n".join(out))
