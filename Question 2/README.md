# SetuBid Deduplication Pipeline (Question 2)

Deduplication pipeline for 12,000 procurement tender notices across 260 portals under a 20-minute nightly budget with persistent relational storage and bookmark stability.

---

## Quickstart (Cold Start)

Run the complete pipeline from cold start with a single command:

```bash
docker compose up
```

- **Zero configuration required**: Builds the pipeline container, starts PostgreSQL with a health check, and runs all 5 sections.
- **Runtime**: ~140 seconds (~2.3 minutes), well within the 20-minute (1,200s) budget.
- **Outputs**: Auto-saved to `./output/`.

---

## Submission Artifacts

| File | Description |
|---|---|
| [`SOLUTION_REPORT.md`](./SOLUTION_REPORT.md) | Comprehensive report answering Sections A through E with measured empirical evidence |
| [`SOLUTION_REPORT.pdf`](./SOLUTION_REPORT.pdf) | Formatted PDF report with embedded figures, callout boxes, and benchmark tables |
| [`SOLUTION_REPORT.docx`](./SOLUTION_REPORT.docx) | Formatted Microsoft Word document report |
| [`report_generater.py`](./report_generater.py) | Python script generating both DOCX and PDF reports from markdown and output assets |
| [`pipeline.py`](./pipeline.py) | Self-contained Python pipeline executing all 5 sections |
| [`docker-compose.yml`](./docker-compose.yml) | Multi-container stack (Postgres + Python pipeline) |
| [`Dockerfile`](./Dockerfile) | Reproducible image specification |
| [`requirements.txt`](./requirements.txt) | Pinned Python dependencies |
| [`output/summary.json`](./output/summary.json) | Machine-readable metrics emitted at pipeline completion |
| [`output/B_minhash_error.png`](./output/B_minhash_error.png) | MinHash estimator error distribution plot |
| [`output/C_lsh_recall_curve.png`](./output/C_lsh_recall_curve.png) | LSH candidate recall theoretical S-curve vs measured bar chart |
| [`output/E_work_distribution.png`](./output/E_work_distribution.png) | Candidate list size histogram highlighting portal hotspots |
| [`output/E_lorenz_curve.png`](./output/E_lorenz_curve.png) | Lorenz curve showing skew of retrieval workload |

---

## Key Results Summary

- **Asymmetric Cost Compliance**: 
  - **FP = 0 (Precision = 1.000)**: Absolutely zero false merges, fulfilling the head of product's 9:1 penalty constraint against merging distinct contracts.
  - **Recall = 0.7455**, **F1 = 0.8542**.
- **Database Access Path**:
  - PostgreSQL composite B-tree index on `(band_id, bucket_key)` achieves **0.057 ms** execution time per probe vs **11.015 ms** for sequential scan (**193× faster**, verified via `EXPLAIN ANALYSE`).
- **Hotspot Mitigation**:
  - Primary mitigation (calibrated $k=7$ word shingles) eliminates vocabulary collapse in construction procurement tenders.
  - Secondary mitigation (capping candidate lists at 50) caps candidate pairs from 9.6M down to 461K at a measured quality cost of 4.3 pp recall.
- **Bookmark Stability**:
  - Deterministic Union-Find assigns `canonical_id = min(notice_id)` to clusters, ensuring bidder bookmarks remain invariant across nightly runs.
