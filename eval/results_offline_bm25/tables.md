# Evaluation results

Generated 2026-10-26 08:41 UTC from `results_offline_bm25`.

## Corpus and test set

- Source documents: 109; characters: 491,299
- Naive index keeps 266,764 characters (54.3%); 57 documents truncated
- Clean ingestion: {'duplicates_dropped': 16, 'binary_dropped': 4, 'empty_dropped': 1, 'boilerplate_lines_removed': 5455, 'docs_after_cleaning': 91, 'chunks': 443}
- Test set: 89 answerable + 12 unanswerable questions
- Answerable questions whose evidence survives naive ingestion: 59 (66.3%); clean ingestion: 89 (100.0%)

## Retrieval (answerable questions)

| Ingestion | Chunk (chars) | Units | Retriever | k | Hit@k (%) | MRR@10 (%) | Evidence recall@k (%) | Evidence hit@k (%) [95% CI] | Context (chars) |
|---|---|---|---|---|---|---|---|---|---|
| naive | – | 108 | bm25 | 1 | 53.9 | 57.9 | 53.9 | 53.9 [43.8-65.2] | 2760 |
| naive | – | 108 | bm25 | 3 | 61.8 | 57.9 | 61.8 | 61.8 [51.7-71.9] | 8370 |
| naive | – | 108 | bm25 | 5 | 62.9 | 57.9 | 62.9 | 62.9 [52.8-73.0] | 13863 |
| naive | – | 108 | bm25 | 10 | 65.2 | 57.9 | 65.2 | 65.2 [55.1-75.3] | 27249 |
| clean | 500 | 1006 | bm25 | 1 | 59.5 | 70.3 | 57.1 | 55.1 [44.9-65.2] | 543 |
| clean | 500 | 1006 | bm25 | 3 | 79.8 | 70.3 | 78.5 | 77.5 [68.5-85.4] | 1632 |
| clean | 500 | 1006 | bm25 | 5 | 85.4 | 70.3 | 84.6 | 84.3 [77.5-91.0] | 2728 |
| clean | 500 | 1006 | bm25 | 10 | 88.8 | 70.3 | 88.0 | 87.6 [80.9-94.4] | 5482 |
| clean | 1000 | 443 | bm25 | 1 | 66.3 | 75.8 | 65.5 | 65.2 [56.2-74.2] | 960 |
| clean | 1000 | 443 | bm25 | 3 | 84.3 | 75.8 | 83.3 | 82.0 [74.2-89.9] | 2939 |
| clean | 1000 | 443 | bm25 | 5 | 87.6 | 75.8 | 87.3 | 86.5 [78.7-93.3] | 4869 |
| clean | 1000 | 443 | bm25 | 10 | 92.1 | 75.8 | 91.8 | 91.0 [85.4-96.6] | 9869 |
| clean | 1500 | 297 | bm25 | 1 | 73.0 | 80.4 | 72.7 | 71.9 [61.8-80.9] | 1380 |
| clean | 1500 | 297 | bm25 | 3 | 86.5 | 80.4 | 86.1 | 85.4 [77.5-92.1] | 4209 |
| clean | 1500 | 297 | bm25 | 5 | 91.0 | 80.4 | 90.6 | 89.9 [83.1-95.5] | 7015 |
| clean | 1500 | 297 | bm25 | 10 | 95.5 | 80.4 | 95.1 | 94.4 [88.8-98.9] | 14072 |

