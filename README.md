# CUMCM 2026 Problem C: Microgrid-to-Grid Dispatch

An open, evidence-oriented record of our team solution to **Problem C, 2026 China Undergraduate Mathematical Contest in Modeling (CUMCM)**: *Microgrid and External Grid Power Regulation Strategy*.

This is a team project, not an official CUMCM repository. It contains our original implementation, final submission workbooks, processed inputs, model documentation, validation evidence, figure-generation code, and the final paper. The independently maintained `cumcm-optimization-rag` project is not part of this repository; RAG may provide methodological context but is never used as a substitute for the contest statement, attachment data, or computed results.

## Team

- [54334-bit](https://github.com/54334-bit)
- [o0enon0ok-cell](https://github.com/o0enon0ok-cell)
- yidan chen

## What the repository contains

The four questions share a storage-physics contract while expanding the information and settlement structures:

| Question | Decision setting | Canonical output |
| --- | --- | --- |
| Q1 | Representative-day deterministic LP with a hard terminal SOC closure | `submissions/result1.xlsx` |
| Q2 | Causal PV forecast, daily planning LP, and E1 execution | `submissions/result2.xlsx` |
| Q3 | 0:00/6:00/12:00/18:00 rolling forecasts and settlement reading C | `submissions/result3.xlsx` |
| Q4 | Q2 and Q3 recomputed under time-varying electricity prices | `submissions/result4-2.xlsx`, `submissions/result4-3.xlsx` |

The frozen totals are historical, byte-preserved delivery records—not outputs recomputed during this repository reorganization. The binding mathematical conventions and result ledger are documented in [models/unified-formulation.md](models/unified-formulation.md).

## Repository layout

```text
models/                  Binding Q1-Q4 formulations and sensitivity conventions
src/cumcm_case_c/        Solvers, validators, execution logic, and figure generators
data/processed/          Processed, aligned data derived from contest attachments
submissions/             Five canonical, byte-preserved submission workbooks
deliverables/            Recovered question-by-question delivery records and audit trail
evidence/                Frozen checks, validation outputs, and sensitivity evidence
assets/                  Figure assets and recovered paper-material archive
paper/                   Final paper, TeX source, appendix, and referenced figures
paper-optimization/      Historical paper-improvement workspace and Q3 appendix sources
sensitivity-analysis/    Historical Q1-Q4 sensitivity-analysis workspace
docs/                    Method, data processing, delivery notes, and reproducibility guides
references/              Source register and team reference material
```

`deliverables/` preserves the manually recovered working records. `submissions/`, `src/`, `data/processed/`, `evidence/`, and `assets/` are the canonical public entry points. This separation avoids treating intermediate workbooks, voided artifacts, or audit notes as the final submission baseline.

## Reproduce and inspect

Use Python 3.11+; the delivery environment recorded by the team used Python 3.12 with `numpy`, `scipy`, `pandas`, `openpyxl`, and `matplotlib`.

```powershell
python -m pytest -q tests
python -m compileall -q src scripts tests
```

The processed CSV inputs are provided for auditability. The original CUMCM statement, raw attachments, and official templates are not redistributed here. See [data/README.md](data/README.md) for the scope and [docs/data-processing/](docs/data-processing/) for the cleaning record.

The canonical workbooks are retained without rewriting. Their SHA-256 hashes, delivery context, and separation from process-history copies are documented in [submissions/README.md](submissions/README.md).

## Paper and figures

[paper/final-paper.pdf](paper/final-paper.pdf) is the team final paper. `paper/main.tex` is the stable TeX entry point; the 15 figures it references are available under `paper/figures/`. Additional figures, manifests, and generators live in `assets/figures/` and `src/cumcm_case_c/figures/`.

The paper is a frozen deliverable. A successful static check of the TeX source does not by itself establish that every environment will reproduce the exact compiled PDF.

## Data, provenance, and limitations

- Processed data are team-produced alignment outputs derived from the contest attachments. They preserve the derived fields used by our code, not the original attachment workbooks.
- The five `submissions/*.xlsx` files are the team’s canonical delivery artifacts. They include solution outputs and are published here by the team as part of this case study.
- Do not compare Q2 and Q3 total cost as a causal “improvement”: their information and settlement structures differ.
- Historical validation evidence records what was checked in the source workflow; it is not a claim that every experiment has been rerun in the current checkout.

## License and citation

Original code and documentation are licensed under [Apache-2.0](LICENSE). CUMCM materials and any third-party content retain their own rights; see [NOTICE](NOTICE), [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), and [references/SOURCES.md](references/SOURCES.md). Cite the repository using [CITATION.cff](CITATION.cff).

For contribution conventions, see [CONTRIBUTING.md](CONTRIBUTING.md). For the recovery history and known limits, see [docs/recovery/](docs/recovery/).
