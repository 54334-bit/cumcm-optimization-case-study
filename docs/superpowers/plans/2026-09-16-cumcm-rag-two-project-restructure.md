# CUMCM 与国赛优化类 RAG 双项目重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `cumcm` 与 `rag` 重构为两个独立、可验证、可分别开源的 Git 仓库，并在确认正确 GitHub 身份后分别发布。

**Architecture:** 在 D 盘临时目录按白名单重建两个项目，先验证内容、路径、许可与运行入口，再用验证通过的目录替换原项目。`mathmodeling_rag搭建` 只合并进独立的 `rag`；`cumcm` 仅保留可选 MCP 接入示例，不复制 RAG 源码或语料。

**Tech Stack:** PowerShell 7、Python 3.12、pytest、MCP stdio、YAML、CSV manifest、Docker Compose、Git、GitHub CLI。

---

## 文件与职责映射

### `cumcm`

- `README.md`：项目入口、案例边界、复现与论文构建说明。
- `LICENSE`：原创代码与文档的 Apache-2.0 许可证。
- `NOTICE`、`THIRD_PARTY_NOTICES.md`：版权边界和第三方材料说明。
- `.gitignore`：排除本机配置、缓存、编译物和交付包。
- `.codex/config.example.toml`：不含本机绝对路径的可选 RAG 接入示例。
- `models/*.md`：Q1–Q4、敏感性分析和统一模型的权威说明。
- `src/cumcm_case_c/`：案例求解与核验代码。
- `data/README.md`：数据来源、获取方法、许可与目录说明。
- `results/README.md`：结果与生成流程映射。
- `paper/main.tex`：唯一权威论文主文件。
- `paper/appendix/`：附录源码和附录代码。
- `references/SOURCES.md`：可复核来源清单。

### `rag`

- `README.md`：RAG 安装、语料、索引、CLI、MCP、Codex 和 Docker 入口。
- `LICENSE`：原创代码与文档的 Apache-2.0 许可证。
- `DATA_LICENSE.md`、`THIRD_PARTY_NOTICES.md`：语料和第三方材料边界。
- `pyproject.toml`：Python 包、入口和依赖声明。
- `src/cumcm_rag/`：核心检索、入库、CLI 与 MCP 服务。
- `config/rag.yaml`：默认相对路径配置。
- `config/codex_config.example.toml`：无本机绝对路径的 Codex 示例。
- `data/manifest/corpus_manifest.csv`：语料登记的唯一事实来源。
- `data/manifest/sources.csv`、`exclusions.csv`：来源和排除记录。
- `data/corpus/`：通过许可筛选的 L0/L1/L2 语料。
- `scripts/`：下载、抽取、OCR、manifest 和校验工具。
- `tests/`：核心、manifest 和 MCP 集成测试。
- `docker/`：Dockerfile 与 Compose 配置。
- `docs/`：架构、语料治理、MCP 接入、迁移和验收说明。

### 过程记录

- `D:\OneDrive\文档\ChatGPT\cumcm\docs\restructure\inventory-before.csv`：重构前文件清单与哈希。
- `D:\OneDrive\文档\ChatGPT\cumcm\docs\restructure\deletion-ledger.md`：删除类别、理由与体量。
- `D:\OneDrive\文档\ChatGPT\rag\docs\restructure\inventory-before.csv`：RAG 源目录和旧目标目录的迁移清单。
- `D:\OneDrive\文档\ChatGPT\rag\docs\restructure\migration-report.md`：manifest 差异、许可排除和验证结果。

## Task 1：建立基线与安全边界

**Files:**
- Create: `D:\OneDrive\文档\ChatGPT\cumcm\docs\restructure\inventory-before.csv`
- Create: `D:\OneDrive\文档\ChatGPT\cumcm\docs\restructure\deletion-ledger.md`
- Create: `D:\OneDrive\文档\ChatGPT\rag\docs\restructure\inventory-before.csv`
- Create: `D:\OneDrive\文档\ChatGPT\rag\docs\restructure\migration-report.md`

- [ ] **Step 1: 解析并校验所有源目录和目标目录**

  使用 `Resolve-Path` 确认三个输入目录分别等于已批准路径，并确认临时目录位于 `D:\OneDrive\文档\ChatGPT\.restructure-20260916`。

- [ ] **Step 2: 生成重构前清单**

  对普通文件记录相对路径、字节数、最后修改时间和 SHA-256。缓存和虚拟环境可按目录记录总量，避免为数万可重建文件生成无价值逐文件台账。

- [ ] **Step 3: 固化删除分类**

  在台账中列出缓存、虚拟环境、编译产物、精确重复、历史快照、无授权第三方材料和过时过程稿，并记录保留的权威替代文件。

- [ ] **Step 4: 验证 GitHub 身份**

  运行：`gh api user --jq '.login'`

  期望：发布前返回用户明确确认的 GitHub 登录名。当前检测值为 `54334-bit`，与用户文字 `zzc54334` 不一致，因此在确认前禁止创建远程仓库。

## Task 2：在 D 盘白名单重建 `cumcm`

**Files:**
- Create: `D:\OneDrive\文档\ChatGPT\.restructure-20260916\cumcm\...`
- Read: `D:\OneDrive\文档\ChatGPT\cumcm\Q1\...`
- Read: `D:\OneDrive\文档\ChatGPT\cumcm\Q2\...`
- Read: `D:\OneDrive\文档\ChatGPT\cumcm\Q3\...`
- Read: `D:\OneDrive\文档\ChatGPT\cumcm\Q4\...`
- Read: `D:\OneDrive\文档\ChatGPT\cumcm\q1-q3重构\...`
- Read: `D:\OneDrive\文档\ChatGPT\cumcm\灵敏度分析\...`
- Read: `D:\OneDrive\文档\ChatGPT\cumcm\论文优化\...`

- [ ] **Step 1: 创建目标骨架**

  创建设计文档规定的 `models`、`src`、`scripts`、`tests`、`data`、`results`、`paper`、`references`、`docs` 和 `.codex` 目录。

- [ ] **Step 2: 迁移权威模型说明**

  将已审计的 Q1–Q4、统一方案和敏感性分析权威稿复制并重命名为稳定文件名；精确重复只保留一份。

- [ ] **Step 3: 迁移可复现代码和结果**

  迁移 Q3 主体代码、`final_audit.py`、`verify_paper.py`、附录构建脚本及必要结果表；不迁移 `code_rendered`、字节码或缓存。

- [ ] **Step 4: 选定唯一论文主文件**

  对两个终稿候选做结构和内容比较，选择覆盖最完整且与结果一致的版本为 `paper/main.tex`；其余版本不进入新项目。

- [ ] **Step 5: 迁移许可允许的数据与来源记录**

  保留复现必需且来源明确的数据；官方题面、附件和第三方论文若无明确再分发许可，则只在 `data/README.md` 或 `references/SOURCES.md` 记录来源与哈希。

- [ ] **Step 6: 写入开源文档和忽略规则**

  README 使用中文，明确项目独立性、安装、复现、论文构建、RAG 可选接入、许可和限制。

## Task 3：重构 `rag` 的 Python 包与路径

**Files:**
- Create: `D:\OneDrive\文档\ChatGPT\.restructure-20260916\rag\src\cumcm_rag\__init__.py`
- Create: `...\core.py`
- Create: `...\ingest.py`
- Create: `...\cli.py`
- Create: `...\mcp_server.py`
- Create: `...\config\rag.yaml`
- Create: `...\pyproject.toml`
- Test: `...\tests\unit\test_core.py`
- Test: `...\tests\integration\test_mcp_stdio.py`

- [ ] **Step 1: 先迁移测试并改写导入路径**

  将现有核心和 MCP 测试迁入标准测试目录，目标导入路径统一为 `cumcm_rag`。

- [ ] **Step 2: 运行测试并记录迁移前失败**

  运行：`python -m pytest -q <临时 rag>\tests`

  期望：在包尚未迁移时因 `cumcm_rag` 不存在而失败，证明测试覆盖新入口。

- [ ] **Step 3: 迁移核心实现**

  将 `rag_core.py`、`ingest.py`、`query_cli.py` 和 `server.py` 分别迁移为 `core.py`、`ingest.py`、`cli.py`、`mcp_server.py`，更新导入与路径解析。

- [ ] **Step 4: 消除数字目录和旧根路径依赖**

  配置默认值从包根、项目根或环境变量解析；源码不得再依赖 `01_rag_engine`、`02_corpus_repository`、`03_mcp_rag` 或 `RAG系统_初版`。

- [ ] **Step 5: 建立包和命令入口**

  `pyproject.toml` 提供 `cumcm-rag` 和 `cumcm-rag-mcp` 命令，并将 runtime、dev、corpus 工具依赖分组。

- [ ] **Step 6: 运行迁移后的测试**

  运行：`python -m pytest -q <临时 rag>\tests`

  期望：核心和 MCP 测试通过；如当前环境缺少可选 OCR 或模型依赖，相应测试必须明确 skip，而不是静默成功。

## Task 4：迁移并治理 RAG 语料

**Files:**
- Create: `D:\OneDrive\文档\ChatGPT\.restructure-20260916\rag\data\manifest\corpus_manifest.csv`
- Create: `...\sources.csv`
- Create: `...\exclusions.csv`
- Create: `...\data\corpus\...`
- Create: `...\scripts\verify_manifest.py`

- [ ] **Step 1: 以当前 399 行 manifest 为基线**

  保存迁移前层级统计：L0=119、L1=193、L2=87。

- [ ] **Step 2: 依据许可和来源字段筛选公开语料**

  未获明确再分发许可的题面、优秀论文、扫描件和第三方包不复制原文，写入 `exclusions.csv` 并保留来源、哈希和排除原因。

- [ ] **Step 3: 迁移允许公开的登记文件**

  重写 manifest 的相对路径，保证所有 `source_file` 位于 `data/corpus`，并保持层级和 case_id 语义。

- [ ] **Step 4: 编写 manifest 校验器**

  校验文件存在、路径不越界、SHA-256 匹配、关键许可字段非空、登记路径唯一、内容哈希无无解释重复。

- [ ] **Step 5: 运行 manifest 校验**

  运行：`python <临时 rag>\scripts\verify_manifest.py`

  期望：退出码 0，并输出保留、排除、缺失、哈希不符和重复计数。

## Task 5：完成 `rag` 文档、部署与 Codex 接入

**Files:**
- Create: `D:\OneDrive\文档\ChatGPT\.restructure-20260916\rag\README.md`
- Create: `...\LICENSE`
- Create: `...\DATA_LICENSE.md`
- Create: `...\THIRD_PARTY_NOTICES.md`
- Create: `...\config\codex_config.example.toml`
- Create: `...\docker\Dockerfile`
- Create: `...\docker\compose.yaml`
- Create: `...\docs\architecture.md`
- Create: `...\docs\corpus-governance.md`
- Create: `...\docs\codex-mcp.md`
- Create: `...\docs\validation.md`

- [ ] **Step 1: 编写 README 和架构文档**

  覆盖安装、最小查询、索引构建、MCP、Codex、Docker、语料治理、许可和故障排查。

- [ ] **Step 2: 创建安全的配置示例**

  示例仅使用 `${RAG_ROOT}` 或相对入口，不出现用户机器的绝对路径、旧目录名或 current 配置。

- [ ] **Step 3: 更新 Docker 路径**

  Docker 构建上下文和启动命令指向 `src/cumcm_rag` 新入口。

- [ ] **Step 4: 验证 Compose**

  运行：`docker compose -f <临时 rag>\docker\compose.yaml config`

  期望：配置可解析；若 Docker 未安装，在验收报告中记录环境限制，不跳过其静态 YAML 检查。

## Task 6：静态检验与安全复核

**Files:**
- Modify: 两个临时项目中的不合格文件
- Update: 两个项目的重构报告

- [ ] **Step 1: Python 静态编译**

  对两个项目的 `src`、`scripts` 和 `tests` 运行 `python -m compileall -q`，期望退出码 0。

- [ ] **Step 2: 执行项目测试**

  运行两个项目 README 声明的测试和复现检查，记录通过、跳过和环境限制。

- [ ] **Step 3: 扫描旧路径和冗余类型**

  使用 `rg` 和文件枚举确认不含旧根目录、`.venv`、`.hf_cache`、`__pycache__`、`.pyc`、备份 manifest、Tectonic 缓存和历史快照。

- [ ] **Step 4: 扫描敏感信息**

  搜索 API key、token、密码、私钥头和常见云凭据格式；命中项必须逐一判断和清除。

- [ ] **Step 5: 独立只读复核**

  由审查代理分别检查 `cumcm`、`rag` 和开源许可/秘密风险；重要问题修复后再复核。

## Task 7：替换正式目录并删除旧工程

**Files:**
- Replace: `D:\OneDrive\文档\ChatGPT\cumcm`
- Replace: `D:\OneDrive\文档\ChatGPT\rag`
- Delete after verification: `D:\OneDrive\文档\ChatGPT\mathmodeling_rag搭建`
- Delete after verification: `D:\OneDrive\文档\ChatGPT\.restructure-20260916`

- [ ] **Step 1: 再次解析目标绝对路径**

  确认所有递归移动和删除目标都严格位于上述四个明确路径，不使用通配符或未解析变量。

- [ ] **Step 2: 将旧正式目录移入 D 盘临时备份槽**

  使用同一 PowerShell 会话和 `Move-Item -LiteralPath`，禁止跨 Shell 拼接路径。

- [ ] **Step 3: 将验证通过的新目录移入正式路径**

  立即检查两个根目录的 README、LICENSE、源代码、测试和数据入口存在。

- [ ] **Step 4: 更新本机非公开 Codex 配置**

  `cumcm\.codex\config.toml` 指向 `D:\OneDrive\文档\ChatGPT\rag` 下的新 MCP 入口，并由 `.gitignore` 排除。

- [ ] **Step 5: 运行正式路径冒烟测试**

  从两个正式根目录重新运行静态编译、关键测试、manifest 校验和 MCP stdio 测试。

- [ ] **Step 6: 删除旧目录和临时备份**

  仅当正式路径测试通过后，删除旧 `mathmodeling_rag搭建`、旧项目备份和临时目录，并记录删除体量及不可恢复性。

## Task 8：初始化两个独立 Git 仓库

**Files:**
- Create: `D:\OneDrive\文档\ChatGPT\cumcm\.git\...`
- Create: `D:\OneDrive\文档\ChatGPT\rag\.git\...`

- [ ] **Step 1: 分别执行 Git 初始化**

  在两个根目录运行 `git init -b main`，不得在共同父目录初始化仓库。

- [ ] **Step 2: 检查纳入范围**

  运行 `git status --short` 和 `git ls-files` 预检，确保不包含缓存、私有配置、大型未授权材料或嵌套 `.git`。

- [ ] **Step 3: 分别创建首次提交**

  `cumcm` 提交信息：`chore: prepare standalone CUMCM case project`

  `rag` 提交信息：`chore: prepare standalone CUMCM optimization RAG`

- [ ] **Step 4: 检查工作树**

  期望两个仓库的 `git status --short` 均为空。

## Task 9：创建并发布两个 GitHub 公共仓库

**Files:**
- Modify: 两个仓库的 Git remote 配置

- [ ] **Step 1: 确认 GitHub 账号与仓库名**

  发布账号必须由用户确认。建议仓库名：`cumcm-optimization-case-study` 与 `cumcm-optimization-rag`。

- [ ] **Step 2: 检查远程仓库是否已存在**

  使用 `gh repo view <owner>/<repo>`；若已存在，不覆盖、不强推，先报告冲突。

- [ ] **Step 3: 创建公共仓库并推送**

  使用 `gh repo create <owner>/<repo> --public --source <local-path> --remote origin --push`。

- [ ] **Step 4: 远程复核**

  检查默认分支、可见性、远程 URL、README、LICENSE、文件大小和最新提交；确认两个仓库互不嵌套且远端不同。

- [ ] **Step 5: 输出交付摘要**

  告知两个本地路径、两个 GitHub URL、最终文件统计、删除类别、测试结果、许可边界和仍需用户处理的限制。
