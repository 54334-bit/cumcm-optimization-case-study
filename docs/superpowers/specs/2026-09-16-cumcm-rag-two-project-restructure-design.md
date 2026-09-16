# CUMCM 与国赛优化类 RAG 双项目重构设计

日期：2026-09-16

## 1. 目标与边界

本次重构形成两个彼此独立、可分别开源和独立运行的项目：

- `D:\OneDrive\文档\ChatGPT\cumcm`：国赛优化类赛题的案例建模、求解、复现与论文工程。
- `D:\OneDrive\文档\ChatGPT\rag`：面向国赛优化类题目的 RAG 引擎、MCP 服务、语料治理与检索工程。

两个项目不采用子模块、嵌套仓库或共享源码。`cumcm` 可以通过 MCP 可选调用 `rag`，但其核心建模与复现流程不以 `rag` 为运行前提；`rag` 也不依赖 `cumcm` 仓库。

用户原消息中的 `D:\OneDrive\文档\ChatGPT\mathmodeling\_rag搭建` 实际不存在。经磁盘和现有配置核对，本次待合并的实际源目录为 `D:\OneDrive\文档\ChatGPT\mathmodeling_rag搭建`。

## 2. 输入与最终状态

### 2.1 输入目录

1. `D:\OneDrive\文档\ChatGPT\cumcm`
2. `D:\OneDrive\文档\ChatGPT\mathmodeling_rag搭建`
3. `D:\OneDrive\文档\ChatGPT\rag`

### 2.2 最终目录

重构后仅保留两个正式项目根目录：

```text
D:\OneDrive\文档\ChatGPT\
├─ cumcm\
└─ rag\
```

`mathmodeling_rag搭建` 的有效内容合并进 `rag` 并通过验收后，删除旧目录。`rag` 根目录是 Codex 已登记的工作区路径，不再嵌套 `RAG系统_初版`、`staging_rag` 或日期快照目录。

## 3. 重构方法

采用白名单重建方式：

1. 在 D 盘创建临时重构目录。
2. 从三个输入目录中仅复制确认有价值、合法且属于目标项目的文件。
3. 在临时目录完成结构调整、路径适配、文档补充和静态验证。
4. 验证通过后，以新结构替换两个正式项目根目录。
5. 删除未进入白名单的缓存、重复副本、历史快照、编译产物及旧 RAG 工程。

该方式避免旧目录中的缓存、版本残留和隐含依赖被无意带入新项目。正式替换前必须校验所有解析后的绝对路径均位于预期的三个源目录、D 盘临时目录或两个目标目录内。

## 4. `cumcm` 项目设计

### 4.1 项目定位

`cumcm` 是国赛优化类题目的案例项目，重点保留：

- 权威建模方案与统一口径；
- 可复现的求解和校验代码；
- 必要的数据样例、结果和数据字典；
- 唯一权威论文源码及附录源码；
- 敏感性分析、模型假设和复现说明；
- 可选的外部 RAG 接入说明与配置示例。

### 4.2 目标结构

```text
cumcm/
├─ README.md
├─ LICENSE
├─ NOTICE
├─ THIRD_PARTY_NOTICES.md
├─ CONTRIBUTING.md
├─ CITATION.cff
├─ AGENTS.md
├─ .gitignore
├─ .codex/
│  └─ config.example.toml
├─ docs/
│  ├─ problem-overview.md
│  ├─ methodology.md
│  ├─ model-assumptions.md
│  ├─ reproducibility.md
│  ├─ rag-integration.md
│  └─ archive/
├─ models/
│  ├─ q1.md
│  ├─ q2.md
│  ├─ q3.md
│  ├─ q4.md
│  ├─ sensitivity-analysis.md
│  └─ unified-formulation.md
├─ src/
│  └─ cumcm_case_c/
├─ scripts/
├─ tests/
├─ data/
│  ├─ README.md
│  ├─ raw/
│  ├─ processed/
│  └─ sample/
├─ results/
│  ├─ README.md
│  ├─ tables/
│  └─ figures/
├─ paper/
│  ├─ main.tex
│  └─ appendix/
└─ references/
   └─ SOURCES.md
```

### 4.3 保留准则

- 每个问题只保留一份权威方案；必要的演进记录精简后放入 `docs/archive`。
- 只保留能够解释、生成或核验最终结果的代码与数据。
- 论文只维护一个 `paper/main.tex`，附录源码集中到 `paper/appendix`。
- 结果文件必须在 `results/README.md` 中说明来源、生成方式和对应模型。
- 第三方题面、附件和论文仅在确认允许再分发时保留原文件，否则改为来源链接、哈希和获取说明。

### 4.4 删除准则

- Tectonic 二进制、压缩包、字体缓存和编译缓存；
- `__pycache__`、`.pyc`、`.aux`、临时日志和测试编译产物；
- 已被权威版本取代的过程稿、对话稿和重复论文版本；
- `code_rendered` 等与源码重复的渲染副本；
- 一次性交付压缩包和重复 PDF；
- 旧 RAG 验收日志及 RAG 引擎副本；
- 无法确认再分发权利的第三方论文、题包和二进制材料。

## 5. `rag` 项目设计

### 5.1 合并基线

以 `mathmodeling_rag搭建\RAG系统_初版` 的当前代码、测试、配置、manifest 和经许可审查的语料为权威基线。

`rag\staging_rag` 和 `rag\runtime_fix_20260905` 仅作为差异核对来源，不得反向覆盖权威基线。确认其中没有独有且仍有价值的内容后，整体删除。

### 5.2 目标结构

```text
rag/
├─ README.md
├─ LICENSE
├─ NOTICE
├─ DATA_LICENSE.md
├─ THIRD_PARTY_NOTICES.md
├─ CONTRIBUTING.md
├─ SECURITY.md
├─ CITATION.cff
├─ .gitignore
├─ pyproject.toml
├─ src/
│  └─ cumcm_rag/
│     ├─ __init__.py
│     ├─ core.py
│     ├─ ingest.py
│     ├─ cli.py
│     └─ mcp_server.py
├─ config/
│  ├─ rag.yaml
│  └─ codex_config.example.toml
├─ scripts/
├─ tests/
│  ├─ unit/
│  └─ integration/
├─ data/
│  ├─ README.md
│  ├─ manifest/
│  │  ├─ corpus_manifest.csv
│  │  ├─ sources.csv
│  │  └─ exclusions.csv
│  ├─ corpus/
│  │  ├─ L0_official/
│  │  ├─ L1_cases/
│  │  └─ L2_methods/
│  └─ incoming/
├─ artifacts/
│  └─ index/
├─ docs/
│  ├─ architecture.md
│  ├─ corpus-governance.md
│  ├─ codex-mcp.md
│  ├─ validation.md
│  └─ migration.md
└─ docker/
   ├─ Dockerfile
   └─ compose.yaml
```

### 5.3 路径与接口

- Python 包使用 `src/cumcm_rag` 布局，入口支持 `python -m cumcm_rag.cli` 和 `python -m cumcm_rag.mcp_server`。
- 运行路径通过包相对路径、配置文件或环境变量解析，不依赖 `RAG系统_初版` 等旧目录名。
- `artifacts/index`、模型缓存和完整下载文件默认不纳入 Git；README 提供可复现的构建方法。
- manifest 是语料登记的唯一事实来源。迁移前基线为 399 条记录，其中 L0 119、L1 193、L2 87；迁移后的任何行数变化都必须有明确的版权、重复或质量排除记录。

### 5.4 删除准则

- `.venv`、`.hf_cache`、`__pycache__` 和 `.pyc`；
- 根级及系统内的 `_legacy_archive`；
- `archive_excluded` 原始文件，仅保留结构化排除原因；
- manifest 的 `.bak`、`dedup-bak` 和 `fixpath-bak` 版本；
- `staging_rag`、`runtime_fix_20260905` 及已合并的旧快照；
- 原始题包压缩文件和可重建的生成索引；
- 未授权语料、污染网页、非优化题内容及重复第三方插件；
- 硬编码旧根目录的 current 配置和一次性验收日志。

## 6. 双项目集成边界

本机可使用 `cumcm\.codex\config.toml` 指向独立 `rag` 项目的 MCP 服务，但该文件包含绝对路径，不进入公开版本控制。`cumcm` 仅提交 `.codex/config.example.toml`，其中使用占位符或环境变量。

公开接口仅包括：

- MCP 工具及其参数约定；
- RAG 安装与启动方法；
- `cumcm` 中的可选接入说明。

不在两个仓库之间复制源码、语料、索引或虚拟环境。

## 7. 许可证与开源合规

两个项目的原创代码与原创文档采用 Apache License 2.0。该许可证不会自动覆盖题面、竞赛附件、第三方论文、字体、二进制、模型、模板或第三方代码。

- `cumcm` 使用 `THIRD_PARTY_NOTICES.md` 和 `data/README.md` 说明第三方材料。
- `rag` 额外使用 `DATA_LICENSE.md`，逐类说明语料的许可、来源与再分发边界。
- 无明确再分发许可的材料不进入公开仓库，只记录元数据、来源链接、许可状态和校验哈希。
- 第三方代码如确需保留，必须保留其原许可证和版权声明。

## 8. README 要求

两个 README 均使用中文为主，并至少包含：

- 项目定位及与另一项目的边界；
- 目录结构；
- 环境要求与安装方法；
- 最小可运行示例；
- 数据或语料获取与许可说明；
- 测试、复现和常见故障处理；
- 开源贡献与引用方法；
- 已知限制。

`rag/README.md` 还需覆盖索引构建、MCP 配置、Codex 接入和 Docker 使用。`cumcm/README.md` 还需覆盖四问模型、结果复现和论文构建。

## 9. 验证与完成标准

### 9.1 通用静态检验

- 必需的 README、LICENSE、NOTICE、贡献说明和忽略规则存在；
- 不含 `.venv`、缓存、字节码、编译垃圾、历史快照或备份文件；
- 不含旧目录名和失效绝对路径；
- 不含常见明文密钥、令牌、密码或私钥；
- 所有公开第三方文件均有来源和许可说明；
- 所有生成文件均有来源或重建方法。

### 9.2 `cumcm` 验收

- Python 源码通过静态编译；
- 权威结果文件与论文关键数值的一致性检查通过；
- 论文只存在一个权威主文件；
- Q1 至 Q4、敏感性分析和统一模型均有清晰入口；
- 在没有 RAG 的情况下仍能阅读和运行核心复现流程；
- 可选 RAG 示例不包含个人机器的公开绝对路径。

### 9.3 `rag` 验收

- Python 源码通过静态编译和测试；
- MCP stdio 初始化、工具列表、状态和健康检查通过；
- manifest 登记路径存在、SHA-256 匹配、许可字段完整且无重复登记；
- 未登记文件不会被索引；
- 迁移后的 manifest 差异均能由排除记录解释；
- Codex 工作区仍指向 `D:\OneDrive\文档\ChatGPT\rag`；
- Docker Compose 配置可解析；
- 不依赖旧目录 `mathmodeling_rag搭建`、`RAG系统_初版`、`staging_rag` 或 `runtime_fix_20260905`。

### 9.4 删除门槛

只有在临时重构目录完成上述检验并核对保留清单后，才替换正式目录和删除旧文件。删除完成后重新统计文件、大小、重复哈希和旧路径引用，确认最终仅保留两个独立项目。

## 10. 不在本次范围内

- 不把两个项目发布到远程平台；
- 不创建 GitHub Release；
- 不替用户判断无法从现有证据确认的第三方授权；
- 不修改或重建项目级 RAG 知识库来冒充来源证据；
- 不将 `cumcm` 与 `rag` 合并为单仓库、monorepo 或嵌套项目。
