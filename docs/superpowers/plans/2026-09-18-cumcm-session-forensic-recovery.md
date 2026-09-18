# CUMCM 历史会话取证恢复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从本机 Codex 历史会话和现存仓库证据中恢复删除前的 CUMCM 原项目结构与可验证文件，在不覆盖现有成果的前提下通过独立分支和 PR 交付。

**Architecture:** 历史 JSONL 会话仅作为只读证据源；先生成路径与操作事件索引，再按“完整写入/完整读取/补丁链/片段/二进制线索”分级恢复到隔离暂存区。控制器是唯一写入者，恢复文件通过大小、行数、SHA-256、结构约束和交叉会话证据验真后，才复制回原目录结构并提交 Git 分支。

**Tech Stack:** PowerShell 7、Git、GitHub CLI、Codex JSONL 会话、SHA-256、pytest/项目静态检查。

---

### Task 1: 固定基线与证据边界

**Files:**
- Create: `docs/recovery/recovery-ledger.md`
- Create: `docs/recovery/recovery-manifest.csv`
- Read: `models/unified-formulation.md`
- Read: `<CODEX_HOME>/sessions/2026/09/**/*.jsonl`

- [ ] **Step 1: 记录当前分支、HEAD、远程和工作树状态**

Run: `git status --short --branch; git rev-parse HEAD; git remote -v`

Expected: 当前为干净的 `main`，HEAD 不在恢复过程中被修改。

- [ ] **Step 2: 从 9 月 10–16 日会话提取所有 `cumcm` 路径引用**

Run: `rg -o -N '<project-root>[^"\r\n]*' <CODEX_HOME>/sessions/2026/09`

Expected: 得到 Q1–Q4、灵敏度分析、论文优化、结果文件及过程文档的候选路径集合。

- [ ] **Step 3: 建立恢复状态枚举**

`exact` = 完整内容且通过验证；`reconstructed` = 完整基线加连续补丁链；`partial` = 仅片段；`reference-only` = 仅文件名/哈希；`unrecoverable-binary` = 日志无二进制内容。

### Task 2: 并行只读取证

**Files:**
- Read only: `<CODEX_HOME>/sessions/2026/09/**/*.jsonl`
- No writes by agents

- [ ] **Step 1: Q1–Q4 与灵敏度方案取证**

提取完整写入、完整读取、补丁、最终行数/字节数/哈希以及原相对路径；禁止生成近似正文。

- [ ] **Step 2: 论文优化与 TeX 取证**

提取每个 TeX 的基线、顺序补丁、最终验证指标、模板和图件依赖；区分源码可恢复与 PDF 仅可重编译。

- [ ] **Step 3: 代码、CSV、结果与目录清单取证**

提取脚本全文、CSV/JSON 文本数据、旧目录树、二进制文件名、大小和哈希线索。

### Task 3: 构建确定性恢复器

**Files:**
- Create: `scripts/recovery/Export-CodexSessionEvidence.ps1`
- Create: `scripts/recovery/Restore-CodexTextArtifacts.ps1`
- Create: `tests/recovery/Test-RecoveryScripts.ps1`
- Create: `_recovery_staging/evidence/`
- Create: `_recovery_staging/restored/`

- [ ] **Step 1: 编写测试，验证 JSONL 事件提取不会执行日志中的命令**

Run: `pwsh -File tests/recovery/Test-RecoveryScripts.ps1`

Expected: 初次因脚本缺失失败；实现后通过，并证明日志仅按 JSON 数据解析。

- [ ] **Step 2: 导出路径、时间、会话、事件类型、命令和输出摘要**

恢复器只读取 `response_item`、`custom_tool_call`、`custom_tool_call_output` 和命令执行事件，不解释或执行其中的任意文本。

- [ ] **Step 3: 按时间重建完整写入和补丁链**

仅在存在完整基线且每个补丁都能唯一应用时输出文件；任何歧义立即降级为 `partial`。

- [ ] **Step 4: 生成恢复清单与证据引用**

每行记录原路径、暂存路径、状态、来源会话、最终哈希、已知历史哈希和验证说明。

### Task 4: 隔离恢复与真实性验证

**Files:**
- Write: `_recovery_staging/restored/**`
- Modify: `docs/recovery/recovery-manifest.csv`
- Modify: `docs/recovery/recovery-ledger.md`

- [ ] **Step 1: 恢复 `exact` 和 `reconstructed` 文本文件**

不得覆盖仓库现有文件；同路径冲突时保存两份并登记差异。

- [ ] **Step 2: 验证关键方案**

检查 Q1–Q4、统一口径和灵敏度文件的标题、章节、关键数值、行数及可用哈希。

- [ ] **Step 3: 验证论文源码**

检查 TeX 环境闭合、花括号平衡、表格/图环境数量、已记录字节数和 SHA-256；不伪造缺失图片与 PDF。

- [ ] **Step 4: 输出无法恢复清单**

PDF、XLSX、PNG、数据库和索引若只有路径或哈希，标记为 `unrecoverable-binary`，并登记可否由文本源重建。

### Task 5: 回填原项目结构

**Files:**
- Create/restore: `Q1/**`
- Create/restore: `Q2/**`
- Create/restore: `Q3/**`
- Create/restore: `Q4/**`
- Create/restore: `q1-q3重构/**`
- Create/restore: `灵敏度分析/**`
- Create/restore: `论文优化/**`
- Preserve: 当前 `data/`, `docs/`, `models/`, `paper/`, `references/`, `results/`, `scripts/`, `src/`, `tests/`

- [ ] **Step 1: 创建恢复分支**

Run: `git switch -c codex/restore-original-cumcm-structure`

Expected: 分支基于当前 `origin/main`。

- [ ] **Step 2: 将已验证文件复制到原相对路径**

只复制 `exact` 与 `reconstructed`；`partial` 证据保留在暂存区，不冒充原文件。

- [ ] **Step 3: 调整忽略规则**

本地原始附件、题面、模板、PDF、XLSX、图片、数据库、索引和编译产物保持不公开；用户原创方案、代码与 TeX 源码可纳入版本控制。

- [ ] **Step 4: 更新 README 与恢复说明**

说明原项目结构、数据边界、复现入口、恢复来源和未恢复二进制依赖。

### Task 6: 验证、提交与 PR

**Files:**
- Verify: entire repository

- [ ] **Step 1: 执行项目测试和恢复专项静态检查**

Run: `pytest -q`

Run: `pwsh -File tests/recovery/Test-RecoveryScripts.ps1`

Expected: 全部通过；未跟踪的大型或受限二进制文件为 0。

- [ ] **Step 2: 检查敏感信息、绝对路径和 Git 变更范围**

Run: `git diff --check; git status --short; git diff --stat`

Expected: 无密钥、个人绝对路径、缓存和编译产物进入提交。

- [ ] **Step 3: 提交恢复结果**

Run: `git add <verified paths>; git commit -m "restore: recover original CUMCM project structure"`

- [ ] **Step 4: 推送分支并创建 PR**

Run: `git push -u origin codex/restore-original-cumcm-structure`

Run: `gh pr create --base main --head codex/restore-original-cumcm-structure --title "Restore original CUMCM project structure" --body-file <verified-pr-body>`

Expected: PR 明确列出精确恢复文件、重建文件、未恢复二进制和验证结果。
