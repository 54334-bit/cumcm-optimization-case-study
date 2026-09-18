# Recovered implementation

This directory contains the recovered team implementation for Q1–Q4 and figure generation. It is preserved primarily as source-level evidence for the delivered workbooks and figures.

The code was restored from the original delivery workflow. Some historical scripts retain their original Windows path assumptions and orchestration layout, so they are **not** presented as a one-command portable package. New work should start from the model contract in `models/unified-formulation.md`, use `data/processed/`, and provide every input/output path explicitly.

The repository-level static checks compile these modules. Compilation does not establish that a legacy script can be run unchanged outside its original controlled workflow. The canonical numerical records are in `submissions/` and `evidence/`.
