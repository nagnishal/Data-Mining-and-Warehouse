# DMW Lab Exam — Question 1: Complete Report
## Annapurna Stores — Data Warehouse & Analytics Platform

| Field | Detail |
|---|---|
| **Dataset** | /exam/data/ — Annapurna Stores (12 Supermarkets, Full Year 2024) |
| **Stack** | PostgreSQL 16 · MinIO S3 Object Store · DuckDB Analytical Engine |
| **Execution** | Fully reproducible via single docker compose up |
| **Output Files** | output/monthly_reconciliation.csv · output/task_b_idempotence.json |

---

## Business Context

The CFO mandated:
Build me something where October is October. I want to slice revenue by store, by product
category, by day of the week and by month, and I want the same number every time I ask.
I also want March's prices when I ask about last March. I do not care what software you
use. I do care the analyst can stop opening files by hand.

---

## System Architecture

Raw POS Files → Dialect Normalizer → Deduplication Engine → Object Store Lake → DuckDB Federated Engine

Three POS dialects handled:
- S01-S05: Comma-separated, ISO-8601 timestamps
- S06-S09: Semicolon-separated, DD-MM-YYYY timestamps
- S10-S12: UTF-8 BOM, Epoch second timestamps

---

## TASK A: Platform Standup & Object Store Landing

### Objective
Design and implement the storage organization for 12 stores x 12 months x 3 POS dialects.

### Storage Design: Hive-Style Partitioned Columnar Parquet

lake/
  store_id=S01/ month=2024-01/data.parquet ... month=2024-12/data.parquet
  store_id=S02/ month=2024-01/data.parquet ... month=2024-12/data.parquet
  ...
  store_id=S12/ month=2024-01/data.parquet ... month=2024-12/data.parquet

- URI Layout: s3://annapurna-sales/store_id={store_id}/month={YYYY-MM}/data.parquet
- Total Partitions Created: 144 (exactly 12 stores x 12 months)
- Format: Snappy-compressed columnar Parquet

### Proof: Measured Scan Efficiency
Target Query: Revenue for Store S01, October 2024

METRIC                     | FLAT FOLDER (*.csv)         | PARTITIONED PARQUET      | IMPROVEMENT
Files Inspected            | 4,457 files                 | 1 file                   | 99.98% pruned
Bytes Scanned              | 68,706,877 bytes (65.52 MB) | 159,723 bytes (155.98 KB)| 99.77% pruned
Files Skipped              | 0                           | 4,456 files saved        | 430x faster
I/O Complexity             | O(N) full scan              | O(1) direct path hit     | —

RESULT: The partitioned layout reduces a 65 MB full scan to a 156 KB single-file read — a 430x byte throughput improvement.

---

## TASK B: Safe to Run Twice (Idempotent Ingestion)

### Objective
Prove that running the pipeline multiple times produces identical, deterministic output.

### The Problem: Re-Sent Files
- Billing systems re-send files on error: SALES_S07_20240711__R1.csv, __R2.csv etc.
- Exactly 68 re-sent files were found in the data.
- Vendor note: "Some re-sends are not complete. Safe deduplication unit is (bill_no, line_no)."

### Deduplication Strategy
  Safe key: composite (bill_no, line_no)
  dedup_df = raw_df.drop_duplicates(subset=['bill_no', 'line_no'])

### Idempotence Proof — 3 Consecutive Full Runs
Checksum formula: SHA256 over sorted (bill_no | line_no | qty | unit_price | line_type) for all rows

RUN | RAW ROWS  | DEDUP ROWS | DROPPED | SHA-256 CHECKSUM                                                  | TIME
1   | 1,137,585 | 1,120,924  | 16,661  | 877893f7e480a216adcac651a3fb161ca38ee35effd068203b8e8aaf96a5eb5c | 60.22s
2   | 1,137,585 | 1,120,924  | 16,661  | 877893f7e480a216adcac651a3fb161ca38ee35effd068203b8e8aaf96a5eb5c | 70.72s
3   | 1,137,585 | 1,120,924  | 16,661  | 877893f7e480a216adcac651a3fb161ca38ee35effd068203b8e8aaf96a5eb5c | 61.02s

PROOF SUCCESSFUL: All 3 runs produced IDENTICAL row counts AND IDENTICAL SHA-256 checksums.

Key Numbers:
- Total raw transaction lines found: 1,137,585
- Unique transaction lines (after dedup): 1,120,924
- Duplicate lines safely discarded: 16,661
- Checksum identity: Bit-for-bit identical across all 3 runs

---

## TASK C: Dimensional Schema & Source Data Gotchas

### Objective
Design the star schema and identify/resolve all data quality traps that would corrupt analytics.

### Star Schema Design

                  dim_stores (12 rows)
                  - store_id (PK), store_name, city, state, region, floor_area_sqft

dim_products (1,224 rows)    fact_sales (789,516 rows)     dim_categories (14 rows)
- product_sk (PK)     1:* - bill_no, line_no (PK)   *:1 - category_id (PK)
- product_code          - store_id (FK)                   - category_name
- product_name          - product_sk (FK)                 - department
- category_id (FK)      - business_date (DATE)            - gst_rate
- valid_from, valid_to  - day_of_week (VARCHAR)
                        - month (VARCHAR)
                        - line_type (VARCHAR)
                        - qty (NUMERIC)
                        - unit_price (NUMERIC)
                        - line_total (NUMERIC)

Master Table Row Counts:
- dim_stores:      12 rows   (one per supermarket)
- dim_products:  1,224 rows  (SCD Type 2 versions)
- dim_categories:   14 rows  (product departments)
- price_revisions: 4,320 rows (historical price ladder)
- fact_sales:    789,516 rows (net revenue transaction lines)

---

### GOTCHA #1: Line Types & The October Revenue Double-Count (2.17x)

The POS files contain 6 distinct line types mixed in the same file:

LINE_TYPE | ROWS IN LAKE | RAW VALUE (INR)    | INCLUDE IN REVENUE? | ROLE
SALE      | 745,860      | +543,249,600.00    | YES                 | Sold item
RETURN    |  16,161      |  -11,779,520.00    | YES                 | Customer return
DISCOUNT  |  22,603      |   -5,294,511.00    | YES                 | Promotional discount
VOID      |   4,892      |   -3,309,857.00    | YES                 | Cancelled bill mirror
TAX       | 165,704      |  +45,439,290.00    | NO                  | GST (pass-through liability)
TENDER    | 165,704      | +568,305,000.00    | NO                  | Total payment line per bill

October 2024 Revenue Pitfall Demonstrated:

  Naive SUM(qty x unit_price) on ALL rows:  INR 122,501,668.06
  Correct revenue (excluding TAX+TENDER):   INR  56,359,195.92
                                            ─────────────────────
  Inflation Ratio:                               2.17x !!!

Why? The TENDER row is written once per bill (165,704 bills = 165,704 TENDER rows).
Summing TENDER alongside SALE rows counts revenue effectively TWICE.

Fix Applied:
  WHERE line_type IN ('SALE', 'RETURN', 'DISCOUNT', 'VOID')
  -- Single filter eliminates the 2.17x double-count.

---

### GOTCHA #2: Reissued Product Codes (SCD Type 2 Required)

In June 2024, merchandising retired and reissued 24 product codes to entirely different products.

Example — Product Code P100621:
PERIOD           | product_sk | product_name               | Category
Before 2024-06-01| 1089       | Catch Coriander Powder 500g| C06 – Spices & Masala
After 2024-06-01 | 2213       | Cadbury Chewing Gum 50g    | C13 – Confectionery

Naive JOIN pitfall: JOIN products ON product_code → 2 master rows per transaction
                    → doubled rows + corrupted category totals

SCD Type 2 Fix Applied:
  LEFT JOIN products p
    ON s.product_code = p.product_code
   AND s.business_date::DATE >= p.valid_from
   AND s.business_date::DATE <= p.valid_to

Result: fact_sales has 789,516 net revenue lines — clean, no duplicated categories.

---

## TASK D: Make March Use March's Prices (SCD Type 2 Price Revisions)

### Objective
Enable time-travel price queries: March 2024 → March prices; today → today's prices.
Using THE SAME QUERY with just a date parameter change.

Historical Price Data:
- price_revisions table: 4,320 rows
- Each row: (product_sk, mrp, selling_price, effective_from, effective_to)
- Current prices have effective_to = 9999-12-31

Parameterized Query:
  SELECT
      p.product_code, p.product_name,
      pr.mrp, pr.selling_price, pr.effective_from, pr.effective_to,
      :target_date AS reporting_date
  FROM products p
  JOIN price_revisions pr ON p.product_sk = pr.product_sk
  WHERE p.product_code = 'P100049'
    AND :target_date::DATE >= pr.effective_from
    AND :target_date::DATE <= pr.effective_to;

### Execution Results — Product: Britannia Cream Biscuit 60g (P100049)

Run 1 — target_date = '2024-03-15' (March Historical Price):
  mrp:            INR 74.98
  selling_price:  INR 66.95     ← March 2024 shelf price
  effective_from: 2022-01-01
  effective_to:   2024-06-19

Run 2 — target_date = '2024-08-15' (Current/Today Shelf Price):
  mrp:            INR 77.20
  selling_price:  INR 68.93     ← Current shelf price
  effective_from: 2024-08-08
  effective_to:   9999-12-31

RESULT: Zero changes to query logic.
  March 2024 → INR 66.95
  August 2024 → INR 68.93
  SCD Type 2 temporal join delivers correct historical prices automatically.

---

## TASK E: Federated Query Across Object Store & PostgreSQL

### Objective
Execute an analytical query simultaneously reading from BOTH the MinIO/Parquet lake
AND PostgreSQL — without copying data between systems.

### Federated SQL Query
  SELECT
      st.region, pc.category_name,
      COUNT(DISTINCT s.bill_no)           AS total_bills,
      ROUND(SUM(s.qty * s.unit_price), 2) AS category_revenue
  FROM read_parquet('s3://annapurna-sales/*/*/*.parquet') s  -- OBJECT STORE
  JOIN stores st ON s.store_id = st.store_id               -- POSTGRESQL
  JOIN products p
    ON s.product_code = p.product_code
   AND s.business_date::DATE BETWEEN p.valid_from AND p.valid_to  -- POSTGRESQL SCD2
  JOIN product_categories pc ON p.category_id = pc.category_id   -- POSTGRESQL
  WHERE s.line_type IN ('SALE', 'RETURN', 'DISCOUNT', 'VOID')
    AND s.business_date >= '2024-10-01' AND s.business_date <= '2024-10-31'
  GROUP BY st.region, pc.category_name
  ORDER BY category_revenue DESC
  LIMIT 5;

### EXPLAIN ANALYZE Execution Plan
  Total Execution Time: 0.544 seconds

  TOP_N (Top: 5)
    └─ HASH_GROUP_BY (SUM, COUNT DISTINCT in memory)
         └─ HASH_JOIN (cross-system join in DuckDB)
              ├─ POSTGRES_SCAN (stores, categories, products)
              └─ PARQUET_SCAN
                   Filter Pushdown: line_type IN ('SALE','RETURN',...)
                   Partition Pruning: month = '2024-10' only (1 partition per store)

### Query Output — Top 5 Regional Categories, October 2024:

REGION  | CATEGORY NAME   | TOTAL BILLS | CATEGORY REVENUE (INR)
South   | Staples & Grains| 2,446       | 4,940,102.53
South   | Baby Care       | 2,263       | 4,264,328.55
South   | Edible Oils     | 2,372       | 4,060,432.88
West    | Staples & Grains| 1,287       | 2,373,386.42
North   | Staples & Grains| 1,169       | 2,345,071.42

RESULT: 0.544 seconds — across a fully federated join spanning two storage systems and 144 Parquet partitions.

---

## TASK F: Financial Reconciliation Against finance_monthly.csv

### Objective
Verify pipeline revenue against Finance Controller's signed-off figures for all 12 months.

### Full 12-Month Reconciliation Table
Source: output/monthly_reconciliation.csv

MONTH   | PIPELINE NET REVENUE | FINANCE SIGNED-OFF  | VARIANCE   | STATUS
2024-01 | 38,446,071.33        | 38,446,071.33       | 0.00       | MATCH
2024-02 | 34,887,085.55        | 34,887,085.55       | 0.00       | MATCH
2024-03 | 41,971,649.09        | 42,457,899.09       | -486,250.00| DISCREPANCY
2024-04 | 37,958,457.37        | 37,958,457.37       | 0.00       | MATCH
2024-05 | 41,764,716.40        | 41,764,716.40       | 0.00       | MATCH
2024-06 | 38,987,082.82        | 38,987,082.82       | 0.00       | MATCH
2024-07 | 40,295,160.11        | 40,527,291.81       | -232,131.70| DISCREPANCY
2024-08 | 45,252,181.75        | 45,252,181.75       | 0.00       | MATCH
2024-09 | 44,615,037.46        | 44,615,037.46       | 0.00       | MATCH
2024-10 | 56,359,195.92        | 56,359,195.92       | 0.00       | MATCH
2024-11 | 51,583,838.47        | 51,583,838.47       | 0.00       | MATCH
2024-12 | 50,745,259.48        | 50,745,209.00       | +50.48     | DISCREPANCY

Summary: 9 out of 12 months match EXACTLY to the paisa. 3 months have explainable variances.

---

### Discrepancy #1 — March 2024: Variance of -INR 486,250.00

Pipeline Revenue:   INR 41,971,649.09
Finance Signed-Off: INR 42,457,899.09
Variance:               -INR 486,250.00
Root Cause Category: Revenue Definition — Scope Difference

Root Cause: Finance included a manually invoiced institutional bulk order worth INR 4,86,250
processed through back-office ERP, completely outside the POS till system. The POS export
correctly captured all register sales, but this institutional order was never entered into any till.

Recommendation to Finance:
  "The INR 4,86,250 variance is an out-of-till institutional order. We recommend adding
  an official ERP invoice ingestion feed or an audited adjustments bridge table so
  non-till institutional orders are ingested automatically into the pipeline."

---

### Discrepancy #2 — July 2024: Variance of -INR 232,131.70

Pipeline Revenue:   INR 40,295,160.11
Finance Signed-Off: INR 40,527,291.81
Variance:               -INR 232,131.70
Root Cause Category: Source Data Gap — Hardware Outage

Root Cause: Store S07 (Pune) suffered a complete till server failure for 3 consecutive days:
July 9, 10, and 11, 2024. Files SALES_S07_20240709.csv, SALES_S07_20240710.csv, and
SALES_S07_20240711.csv DO NOT EXIST in the POS export folder. Finance closed the month
by having the store manager call in estimated daily totals.

Recommendation to Finance:
  "The July source data is missing three store-days due to hardware failure at S07.
  Create a formal manual journal adjustment table for store outages rather than
  relying on informal spreadsheet edits."

---

### Discrepancy #3 — December 2024: Variance of +INR 50.48

Pipeline Revenue:   INR 50,745,259.48
Finance Signed-Off: INR 50,745,209.00
Variance:               +INR 50.48
Root Cause Category: Revenue Definition — Rounding Convention

Root Cause: Finance rounded each individual customer bill total to the nearest integer rupee
BEFORE summing across the month. The pipeline sums exact decimal line-item values.
The accumulated rounding difference is INR 50.48 — a pure arithmetic convention mismatch.

Recommendation to Finance:
  "The INR 50.48 difference is pure rounding convention (bill-level rupee rounding vs.
  exact decimal summing). Standardize the company-wide accounting definition to
  line-level decimal precision, with bill rounding recorded as a separate line item."

---

## Summary of All Key Numbers

METRIC                                     | VALUE
Raw POS files loaded                       | 4,457 CSV files
Raw transaction lines ingested             | 1,137,585
Duplicate lines dropped (safe dedup)       | 16,661
Clean lines in lake                        | 1,120,924
Hive partitions created                    | 144 (12 stores x 12 months)
Parquet bytes for S01/Oct (vs 65MB flat)   | 155.98 KB (99.77% bytes pruned)
Idempotence runs proven                    | 3 consecutive runs, identical SHA-256
fact_sales net revenue lines               | 789,516
Months reconciled exactly (zero variance)  | 9 / 12
Months with explained variances            | 3 / 12
October 2024 naive revenue (WRONG)         | INR 1,22,50,1668.06
October 2024 correct net revenue           | INR 5,63,59,195.92
Inflation ratio if TAX+TENDER included     | 2.17x
SCD Type 2 codes reissued in June 2024    | 24 product codes
March price (P100049 Britannia Biscuit)    | INR 66.95
August price (P100049 Britannia Biscuit)   | INR 68.93
Federated query execution time             | 0.544 seconds

---

## How to Reproduce Everything

Option 1: Full Docker Stack (Recommended)
  docker compose up --build

  This single command:
  1. Starts PostgreSQL 16 on port 5432 and seeds all master tables from masters.sql
  2. Starts MinIO object store on ports 9000 & 9001
  3. Builds analytics container which:
     - Ingests all 4,457 raw POS files
     - Deduplicates to 1,120,924 clean rows
     - Partitions into 144 Hive Parquet files under lake/
     - Builds the star schema (fact + 3 dims)
     - Proves idempotence over 3 runs
     - Runs Task D price lookups
     - Runs Task E federated join
     - Runs Task F financial reconciliation
     - Writes output/monthly_reconciliation.csv and output/task_b_idempotence.json

Option 2: Local Python Execution
  py pipeline.py

Output Files Generated:
  output/monthly_reconciliation.csv     12-month finance reconciliation
  output/task_b_idempotence.json        3-run idempotence proof with SHA-256
  lake/store_id=*/month=*/data.parquet  144 Hive-partitioned Parquet files
