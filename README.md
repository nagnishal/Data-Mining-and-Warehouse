# Data-Mining-and-Warehouse
Academic repository for storing exam files, lab programs, reports, assignments, and other course-related materials.

---

## Lab Exam Solutions

### [Question 1: Annapurna Stores Data Warehouse & Analytics Platform](./Question%201)
- **Problem**: "Three Answers to One Question" — CFO revenue reconciliations, SCD Type 2 price revisions, duplicate till dumps, and non-revenue line type resolution across 12 supermarkets.
- **Stack**: PostgreSQL 16 · MinIO S3 Object Store · DuckDB Vectorized Analytics Engine.
- **Cold Start**: `docker compose up --build`
- **Deliverables**: [`SOLUTION_REPORT.md`](./Question%201/SOLUTION_REPORT.md) · [`SOLUTION_REPORT.pdf`](./Question%201/SOLUTION_REPORT.pdf) · [`SOLUTION_REPORT.docx`](./Question%201/SOLUTION_REPORT.docx)

### [Question 2: SetuBid Deduplication Pipeline](./Question%202)
- **Problem**: "Twelve Thousand Tenders, Wearing Disguises" — Deduplication of 12,000 procurement tenders across 260 portals under a 20-minute nightly budget with zero false merges.
- **Stack**: PostgreSQL · Python MinHash + LSH with Union-Find cluster stabilization.
- **Cold Start**: `docker compose up`
- **Deliverables**: [`SOLUTION_REPORT.md`](./Question%202/SOLUTION_REPORT.md) · [`SOLUTION_REPORT.pdf`](./Question%202/SOLUTION_REPORT.pdf) · [`SOLUTION_REPORT.docx`](./Question%202/SOLUTION_REPORT.docx)
