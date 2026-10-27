# Evaluation results

Generated 2026-10-27 09:14 UTC from `/Users/haddadalwiyafie/chatbot_telu-main/eval/results`.

## Corpus and test set

- Source documents: 109; characters: 491,299
- Naive index keeps 266,764 characters (54.3%); 57 documents truncated
- Clean ingestion: {'duplicates_dropped': 16, 'binary_dropped': 4, 'empty_dropped': 1, 'boilerplate_lines_removed': 5455, 'docs_after_cleaning': 91, 'chunks': 443}
- Test set: 89 answerable + 12 unanswerable questions
- Answerable questions whose evidence survives naive ingestion: 58 (65.2%); clean ingestion: 89 (100.0%)

## Retrieval (answerable questions)

| Ingestion | Chunk (chars) | Units | Retriever | k | Hit@k (%) | MRR@10 (%) | Evidence recall@k (%) | Evidence hit@k (%) [95% CI] | Context (chars) | vs deployed: gained / lost, McNemar p |
|---|---|---|---|---|---|---|---|---|---|---|
| naive | – | 108 | dense | 1 | 55.1 | 60.9 | 54.7 | 53.9 [43.8-64.0] | 2840 | – |
| naive | – | 108 | dense | 3 | 65.2 | 60.9 | 64.0 | 61.8 [51.7-71.9] | 8436 | – |
| naive | – | 108 | dense | 5 | 68.5 | 60.9 | 67.0 | 64.0 [53.9-74.2] | 13834 | – |
| naive | – | 108 | dense | 10 | 69.7 | 60.9 | 67.7 | 64.0 [53.9-74.2] | 26963 | – |
| naive | – | 108 | bm25 | 1 | 55.1 | 59.8 | 54.1 | 52.8 [42.7-64.0] | 2760 | 6 / 7, p = 1.0000 |
| naive | – | 108 | bm25 | 3 | 64.0 | 59.8 | 62.7 | 60.7 [50.6-70.8] | 8370 | 1 / 2, p = 1.0000 |
| naive | – | 108 | bm25 | 5 | 65.2 | 59.8 | 63.9 | 61.8 [51.7-71.9] | 13863 | 0 / 2, p = 0.5000 |
| naive | – | 108 | bm25 | 10 | 69.7 | 59.8 | 67.7 | 64.0 [53.9-74.2] | 27249 | 0 / 0, p = 1.0000 |
| naive | – | 108 | hybrid | 1 | 59.5 | 63.5 | 58.2 | 56.2 [46.1-67.4] | 2774 | 5 / 3, p = 0.7266 |
| naive | – | 108 | hybrid | 3 | 66.3 | 63.5 | 65.0 | 62.9 [52.8-73.0] | 8313 | 1 / 0, p = 1.0000 |
| naive | – | 108 | hybrid | 5 | 69.7 | 63.5 | 67.7 | 64.0 [53.9-74.2] | 13877 | 0 / 0, p = 1.0000 |
| naive | – | 108 | hybrid | 10 | 69.7 | 63.5 | 67.7 | 64.0 [53.9-74.2] | 26654 | 0 / 0, p = 1.0000 |
| clean | 500 | 1006 | dense | 1 | 69.7 | 79.9 | 64.5 | 60.7 [50.6-70.8] | 562 | 27 / 21, p = 0.4709 |
| clean | 500 | 1006 | dense | 3 | 87.6 | 79.9 | 83.6 | 80.9 [71.9-88.8] | 1670 | 25 / 8, p = 0.0046 |
| clean | 500 | 1006 | dense | 5 | 92.1 | 79.9 | 88.5 | 84.3 [76.4-91.0] | 2762 | 25 / 7, p = 0.0021 |
| clean | 500 | 1006 | dense | 10 | 98.9 | 79.9 | 96.4 | 94.4 [88.8-98.9] | 5444 | 29 / 2, p = 0.0000 |
| clean | 500 | 1006 | bm25 | 1 | 59.5 | 71.2 | 55.0 | 50.6 [40.4-60.7] | 543 | 20 / 23, p = 0.7608 |
| clean | 500 | 1006 | bm25 | 3 | 80.9 | 71.2 | 78.0 | 75.3 [66.3-84.3] | 1632 | 24 / 12, p = 0.0652 |
| clean | 500 | 1006 | bm25 | 5 | 87.6 | 71.2 | 84.5 | 82.0 [74.2-89.9] | 2728 | 25 / 9, p = 0.0090 |
| clean | 500 | 1006 | bm25 | 10 | 92.1 | 71.2 | 88.0 | 85.4 [77.5-92.1] | 5482 | 27 / 8, p = 0.0019 |
| clean | 500 | 1006 | hybrid | 1 | 69.7 | 79.9 | 64.2 | 59.5 [49.4-69.7] | 557 | 24 / 19, p = 0.5424 |
| clean | 500 | 1006 | hybrid | 3 | 88.8 | 79.9 | 85.0 | 82.0 [74.2-89.9] | 1639 | 27 / 9, p = 0.0039 |
| clean | 500 | 1006 | hybrid | 5 | 94.4 | 79.9 | 90.8 | 88.8 [82.0-94.4] | 2745 | 28 / 6, p = 0.0002 |
| clean | 500 | 1006 | hybrid | 10 | 95.5 | 79.9 | 92.9 | 91.0 [84.3-96.6] | 5485 | 29 / 5, p = 0.0000 |
| clean | 1000 | 443 | dense | 1 | 69.7 | 82.4 | 67.8 | 66.3 [57.3-75.3] | 993 | 24 / 13, p = 0.0989 |
| clean | 1000 | 443 | dense | 3 | 93.3 | 82.4 | 91.3 | 87.6 [79.8-94.4] | 2960 | 27 / 4, p = 0.0000 |
| clean | 1000 | 443 | dense | 5 | 98.9 | 82.4 | 97.2 | 94.4 [88.8-98.9] | 4893 | 30 / 3, p = 0.0000 |
| clean | 1000 | 443 | dense | 10 | 98.9 | 82.4 | 98.1 | 96.6 [92.1-100.0] | 9755 | 31 / 2, p = 0.0000 |
| clean | 1000 | 443 | bm25 | 1 | 68.5 | 78.6 | 65.7 | 62.9 [52.8-73.0] | 960 | 24 / 16, p = 0.2682 |
| clean | 1000 | 443 | bm25 | 3 | 87.6 | 78.6 | 84.4 | 79.8 [71.9-88.8] | 2939 | 24 / 8, p = 0.0070 |
| clean | 1000 | 443 | bm25 | 5 | 91.0 | 78.6 | 88.9 | 85.4 [77.5-92.1] | 4869 | 26 / 7, p = 0.0013 |
| clean | 1000 | 443 | bm25 | 10 | 95.5 | 78.6 | 93.7 | 89.9 [83.1-95.5] | 9869 | 28 / 5, p = 0.0001 |
| clean | 1000 | 443 | hybrid | 1 | 75.3 | 84.8 | 72.5 | 70.8 [61.8-80.9] | 992 | 25 / 10, p = 0.0167 |
| clean | 1000 | 443 | hybrid | 3 | 94.4 | 84.8 | 92.0 | 87.6 [79.8-94.4] | 2893 | 28 / 5, p = 0.0001 |
| clean | 1000 | 443 | hybrid | 5 | 96.6 | 84.8 | 95.1 | 92.1 [85.4-97.8] | 4892 | 29 / 4, p = 0.0000 |
| clean | 1000 | 443 | hybrid | 10 | 98.9 | 84.8 | 97.8 | 95.5 [91.0-98.9] | 9889 | 31 / 3, p = 0.0000 |
| clean | 1500 | 297 | dense | 1 | 71.9 | 83.0 | 69.7 | 67.4 [58.4-77.5] | 1423 | 20 / 8, p = 0.0357 |
| clean | 1500 | 297 | dense | 3 | 93.3 | 83.0 | 92.0 | 89.9 [83.1-95.5] | 4103 | 26 / 1, p = 0.0000 |
| clean | 1500 | 297 | dense | 5 | 95.5 | 83.0 | 94.9 | 94.4 [88.8-98.9] | 6915 | 29 / 2, p = 0.0000 |
| clean | 1500 | 297 | dense | 10 | 98.9 | 83.0 | 98.9 | 98.9 [96.6-100.0] | 13860 | 32 / 1, p = 0.0000 |
| clean | 1500 | 297 | bm25 | 1 | 75.3 | 82.4 | 72.5 | 69.7 [59.6-78.7] | 1380 | 26 / 12, p = 0.0336 |
| clean | 1500 | 297 | bm25 | 3 | 87.6 | 82.4 | 85.6 | 83.2 [74.2-89.9] | 4209 | 28 / 9, p = 0.0026 |
| clean | 1500 | 297 | bm25 | 5 | 93.3 | 82.4 | 91.2 | 88.8 [82.0-94.4] | 7015 | 29 / 7, p = 0.0003 |
| clean | 1500 | 297 | bm25 | 10 | 97.8 | 82.4 | 96.4 | 94.4 [88.8-98.9] | 14072 | 31 / 4, p = 0.0000 |
| clean | 1500 | 297 | hybrid | 1 | 75.3 | 85.2 | 73.0 | 70.8 [61.8-79.8] | 1428 | 23 / 8, p = 0.0107 |
| clean | 1500 | 297 | hybrid | 3 | 95.5 | 85.2 | 94.2 | 92.1 [86.5-96.6] | 4142 | 32 / 5, p = 0.0000 |
| clean | 1500 | 297 | hybrid | 5 | 98.9 | 85.2 | 98.1 | 96.6 [92.1-100.0] | 6995 | 32 / 3, p = 0.0000 |
| clean | 1500 | 297 | hybrid | 10 | 98.9 | 85.2 | 98.5 | 97.8 [94.4-100.0] | 14133 | 32 / 2, p = 0.0000 |

## End-to-end answer quality

| Config | Description | Accuracy (%) [95% CI] | Partial or better (%) | Faithfulness (%) | False refusal (%) | Negative rejection (%) | Token F1 | Evidence in context (%) | p50 / p95 latency (s) | vs G1: gained / lost, McNemar p (Holm) |
|---|---|---|---|---|---|---|---|---|---|---|
| G0 | LLM only (no retrieval) | 6.7 [2.2-12.4] | 13.5 | – | 76.4 | 100.0 | 8.5 | – | 0.85 / 2.01 | 3 / 49, p = 0.000 (0.000) |
| G1 | Deployed: naive ingestion + dense, k=3 | 59.8 [49.4-70.1] | 65.5 | 100.0 | 36.0 | 100.0 | 43.6 | 61.8 | 1.10 / 1.46 | – |
| G2 | Clean ingestion + dense, k=3 | 77.5 [68.5-85.4] | 92.1 | 100.0 | 7.9 | 100.0 | 63.4 | 87.6 | 1.26 / 2.79 | 23 / 6, p = 0.002 (0.005) |
| G3 | Clean ingestion + hybrid, k=3 | 71.9 [61.8-80.9] | 95.5 | 95.3 | 4.5 | 100.0 | 63.6 | 87.6 | 1.28 / 2.01 | 22 / 10, p = 0.050 (0.050) |
| G4 | Clean ingestion + hybrid, k=5 | 78.7 [69.7-87.6] | 97.8 | 97.7 | 2.2 | 100.0 | 65.0 | 92.1 | 1.30 / 1.66 | 23 / 5, p = 0.001 (0.003) |

Pure refusals rescored by rule (judge label overridden): G0 20; G1 30; G2 1; G3 3; G4 2. Latency counts only records with a measured successful call: G0 n = 8; G1 n = 8; G2 n = 8; G3 n = 8; G4 n = 8.

## Planned paired comparisons (answerable questions, exact McNemar, Holm-adjusted)

| Comparison | Factor isolated | n | Accuracy A (%) | Accuracy B (%) | Gained / lost | p | p (Holm) |
|---|---|---|---|---|---|---|---|
| G1 vs G0 | value of retrieval | 87 | 59.8 | 6.9 | 49 / 3 | 0.0000 | 0.0000 |
| G2 vs G1 | ingestion | 87 | 77.0 | 59.8 | 21 / 6 | 0.0059 | 0.0178 |
| G3 vs G2 | retriever | 89 | 71.9 | 77.5 | 4 / 9 | 0.2668 | 0.3591 |
| G4 vs G3 | depth | 89 | 78.7 | 71.9 | 10 / 4 | 0.1796 | 0.3591 |

## Accuracy by category (%)

| Category | n | G0 | G1 | G2 | G3 | G4 |
|---|---|---|---|---|---|---|
| academic-admin | 12 | 8.3 | 63.6 | 66.7 | 58.3 | 75.0 |
| admission-fees | 8 | 0.0 | 37.5 | 62.5 | 37.5 | 62.5 |
| admission-path | 24 | 4.2 | 45.8 | 75.0 | 70.8 | 70.8 |
| admission-scholarship | 5 | 0.0 | 100.0 | 80.0 | 80.0 | 80.0 |
| campus | 5 | 20.0 | 80.0 | 100.0 | 100.0 | 100.0 |
| campus-life | 7 | 0.0 | 83.3 | 85.7 | 71.4 | 85.7 |
| contact | 3 | 0.0 | 66.7 | 66.7 | 66.7 | 66.7 |
| leadership | 6 | 0.0 | 33.3 | 100.0 | 83.3 | 83.3 |
| out-of-scope | 3 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| profile | 9 | 11.1 | 88.9 | 77.8 | 88.9 | 88.9 |
| program | 4 | 50.0 | 0.0 | 75.0 | 75.0 | 75.0 |
| research | 6 | 0.0 | 83.3 | 83.3 | 83.3 | 100.0 |
| unanswerable-distractor | 2 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| unanswerable-indomain | 7 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |

## Failure analysis (questions not fully correct)

| Failure type | G1 | G2 | G3 | G4 |
|---|---|---|---|---|
| Missing content (evidence not indexed) | 29 | 0 | 0 | 0 |
| Not retrieved (indexed, not in top k) | 2 | 8 | 9 | 5 |
| Refused although evidence was in context | 0 | 1 | 0 | 0 |
| Wrong or incomplete although evidence was in context | 4 | 11 | 16 | 14 |
| Answered an unanswerable question | 0 | 0 | 0 | 0 |

Generator: `gemini-3.5-flash-lite`; judge: `command-a-03-2025`; embedder: `embed-v4.0`; Python 3.12.15 on macOS-26.2-arm64-arm-64bit.
