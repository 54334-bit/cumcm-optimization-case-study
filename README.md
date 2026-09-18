# CUMCM 优化调度案例：微网与外部电网协同

> 非官方案例项目。它整理一个微网优化调度的建模、代码片段、论文源码和可复核的汇总结果；**不包含中国大学生数学建模竞赛题面、官方附件、官方结果模板、真实填报工作簿、第三方论文或竞赛 PDF**。

本项目与 `cumcm-optimization-rag` 是两个独立项目：这里不含 RAG 引擎、语料或索引。RAG 仅可作为建模方法检索的可选外部服务，核心模型、说明和本地复核脚本不依赖它。

## 协作者

- [54334-bit](https://github.com/54334-bit)
- [o0enon0ok-cell](https://github.com/o0enon0ok-cell)
- yidan chen

## 案例范围

四问沿同一储能物理合同逐步扩展信息与结算机制：Q1 为单日两阶段词典序 LP；Q2 为因果光伏预测、逐日 LP 与 E1 执行；Q3 加入 0:00/6:00/12:00/18:00 预报更新、读法 C 结算与 v2b 执行；Q4 在波动电价下分别重算 Q2 与 Q3。统一权威口径和冻结数值见 [models/unified-formulation.md](models/unified-formulation.md)。

项目仅保留汇总数值，不能把不同信息结构下的 Q2 与 Q3 总费用作优劣差额解释。已记录的源结果为：Q1 35,126.9486 元；Q2 13,252,341.09 元；Q3 13,120,194.06 元；Q4-2 13,850,454.64 元；Q4-3 13,727,033.66 元。它们是源工作流的冻结记录，而非本仓库重新运行的结果。

## 目录

```text
models/                  四问权威口径入口与统一冻结方案
src/cumcm_case_c/q3/     Q3 求解、执行与预测的已审计代码片段
scripts/                 独立复核脚本
tests/                   可移植路径接口测试
data/                    数据许可、获取和目录约定；不含题面及附件
results/                 汇总结果台账和来源说明；不含真实结果工作簿
paper/                   唯一主 TeX 与 Q3 代码附录源码
references/              来源、许可和获取登记
docs/                    方法、复现、RAG 接入与重构设计/计划
```

## Restored source-project layout

The repository also preserves the recoverable parts of the original working layout instead of replacing that layout with the publication-oriented tree:

- `灵敏度分析/` contains the byte-verified original unified Q1–Q4 formulation.
- `论文优化/` contains the byte-verified final TeX source, its verification ledgers, and the Q3 appendix sources.
- The publication-oriented `models/`, `paper/`, and `src/` paths remain available as stable entry points; they do not replace the restored source-project paths.

The recovery is evidence-driven. Files are restored only when a surviving byte-identical copy, a recorded SHA-256, or a complete canonical Codex write event is available. Missing binary workbooks, PDFs, and figures are listed in `docs/recovery/recovery-report.md` rather than recreated from prose.

## 环境与最小检查

Python 3.11 或更高版本可运行本仓库的静态检查；如果要执行基于本地授权工作簿的 Q3 审计，还需要 `numpy` 与 `openpyxl`。

```powershell
python -m pytest -q tests
python -m compileall -q src scripts tests
```

在已合法取得竞赛材料和填报结果后，使用者可将其保存在仓库外或 `data/local/`（已忽略），再显式执行：

```powershell
python scripts/audit_q3_result.py `
  --result-workbook <本地Q3结果工作簿> `
  --price-workbook <本地附件1工作簿> `
  --output results/tables/q3_fee_audit.txt
```

脚本不会下载、查找或内置任何个人绝对路径；输出为读法 C、右端点电价下的独立核算。它只验证给定工作簿的表结构和费用算式，不能证明输入材料的来源或竞赛提交有效性。

## 论文源码

`paper/main.tex` 是唯一维护的论文主文件，`paper/appendix/` 含可嵌入的 Q3 代码附录。论文依赖竞赛 LaTeX 模板和多张由原工作流生成的图件，这些依赖未在本公开仓库再分发；因此本次仅完成静态 TeX 检查，不宣称可在无外部材料的环境中编译。详见 `docs/reproducibility.md`。

## 可选 RAG 接入

没有 RAG 时，本项目仍可阅读模型并运行仓库内的检查。若已在本机另行安装独立 RAG 服务，可复制 `.codex/config.example.toml`，把其中的环境变量替换为本机服务入口。不要提交实际配置、令牌、索引、语料或模型缓存。详细约定见 `docs/rag-integration.md`。

## 许可、来源与贡献

本仓库中原创代码和原创文档以 Apache-2.0 许可发布，详见 `LICENSE`、`NOTICE` 和 `THIRD_PARTY_NOTICES.md`。竞赛材料和第三方内容不因本许可而获得再分发权。数据边界见 `data/README.md`，来源清单见 `references/SOURCES.md`。

贡献前请阅读 `CONTRIBUTING.md`；引用方式见 `CITATION.cff`。已知限制、历史验证与未决事项见 `docs/reproducibility.md`。
