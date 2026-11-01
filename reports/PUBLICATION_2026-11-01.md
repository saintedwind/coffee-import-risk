# Publication audit — 2026-11-01

## Scope

IRR/toman conversion, cost explanations, roasting and sales allocation, five operational scenario engines, evidence manifests and local future-forecast registry.

## Validation

68 automated unit/data/Streamlit tests passed again on 2026-11-01.

The actual FRED history, five-engine UI/replay and historical Iranian listing comparisons were executed on 2026-10-27; they were not rerun or relabeled as current market quotes on publication day.

[Original evidence and limitations](2026-10-27-release/RELEASE_REVIEW_FA.md)

## Limitations retained

Commercial costs and 271,000 toman/USD are explicitly assumed/user-reported. No customer invoice, complete Iranian settlement-FX history or future outcome was verified. The large wholesale price mismatch and inadequate tail coverage remain recorded.

## Publication boundary

Source and selected attributed evidence only. No credentials, private documents, raw downloaded evaluation inputs, model weights, local databases, caches or temporary runtime state are published. Historical experiments are not renamed as fresh validation. No production/customer accuracy claim is added.

Pre-publication main revision: `c403d78d96c5720ae6bbe208af27194fe912102f`. GitHub Actions on the published source is the independent CI record; a historical green run is not substituted for a new code revision.
