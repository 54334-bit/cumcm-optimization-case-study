# Data boundary

The repository does **not** redistribute the original CUMCM problem statement, the raw official attachments, or the official workbook templates. Obtain those materials from the rights holder or official channel if you need the original sources.

## Public processed inputs

`processed/` contains the team’s cleaned and aligned CSV/JSON inputs used by the delivery workflow. They are derived from the contest attachments and retain the fields required by the source code:

| File family | Role |
| --- | --- |
| `q1_clean.csv`, `q1_image.json` | Representative-day inputs for Q1 |
| `attachment2_load.csv`, `attachment2_pv.csv` | Aligned 2025 load and PV actuals |
| `attachment3_clean.csv` | Rolling PV forecast records |
| `attachment4_clean.csv` | Time-varying electricity prices for Q4 |

The checksum file in `processed/manifest.sha256` and the cleaning/audit notes in [docs/data-processing/](../docs/data-processing/) are historical provenance records. They do not grant any right to redistribute the original attachments.

## Local-only material

Put any separately authorized raw files under `data/local/`; the directory is ignored by Git. Scripts must receive local file paths through command-line arguments, relative paths, or environment variables. No script should depend on a personal absolute path.
