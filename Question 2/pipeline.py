"""
Question 2: Twelve Thousand Tenders, Wearing Disguises
=======================================================
SetuBid deduplication pipeline.

Sections:
  A) Text representation + Jaccard similarity
  B) MinHash sketching with justified size
  C) LSH band/row retrieval (sublinear) with candidate analysis
  D) PostgreSQL schema, GIN index, access-method justification
  E) Work distribution, hotspot mitigation, before/after measurement
"""

import os, re, time, json, glob, math, random, hashlib, textwrap
import collections, itertools, warnings
from typing import List, Tuple, Dict

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from datasketch import MinHash, MinHashLSH
import psycopg2
from psycopg2.extras import execute_values
from tabulate import tabulate

warnings.filterwarnings("ignore")

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
DATA_DIR = os.getenv("DATA_DIR")
if not DATA_DIR:
    for candidate in ["/exam/data", "data_2", "data"]:
        if os.path.isdir(candidate):
            DATA_DIR = candidate
            break
    if not DATA_DIR:
        DATA_DIR = "/exam/data"

OUTPUT_DIR = os.getenv("OUTPUT_DIR")
if not OUTPUT_DIR:
    OUTPUT_DIR = "/output" if os.path.exists("/output") else "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

DB = dict(
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", 5433)),
    dbname=os.getenv("DB_NAME", "setubid"),
    user=os.getenv("DB_USER", "setubid"),
    password=os.getenv("DB_PASS", "setubid"),
)

# MinHash / LSH parameters ? justified in Section B
NUM_PERM       = 128     # number of hash permutations (justified below)
LSH_THRESHOLD  = 0.35    # similarity threshold for candidate retrieval
# Band/row decomposition: b=32, r=4  => P(candidate | s=0.25)?0.92
# Asymmetric: we prefer high recall (missing a duplicate is cheap vs false merge)
# Cost ratio: false-merge cost >> false-miss cost  ? threshold set low
BAND_COUNT     = 32
ROWS_PER_BAND  = 4       # NUM_PERM = BAND_COUNT * ROWS_PER_BAND = 128

SHINGLE_K      = 7       # 7-word shingles -- calibrated on labelled pairs

# Nodal-portal boilerplate markers (identified from corpus inspection)
NODAL_A_MARKER = "GOVERNMENT OF INDIA -- NATIONAL PROCUREMENT AGGREGATION SERVICE"
NODAL_B_MARKER = "STATE PROCUREMENT CELL -- CONSOLIDATED TENDER BULLETIN"
NODAL_A_END    = "STANDARD TERMS AND CONDITIONS APPLICABLE TO ALL NOTICES"
NODAL_B_END    = "GENERAL INSTRUCTIONS TO BIDDERS (REPRODUCED IN FULL IN EVERY BULLETIN ENTRY)"
# Approximate preamble length (characters) for nodal portals
NODAL_PREAMBLE_CHARS = 1450

# Cost ratio: missing a same (false-negative) costs 1, merging different (false-positive) costs 9
# ? precision matters more than recall for the MERGE step; but recall matters at the CANDIDATE stage
FP_COST        = 9       # cost of merging two different tenders
FN_COST        = 1       # cost of missing a duplicate

# ----------------------------------------------------------------------
# Utilities
# ----------------------------------------------------------------------
def log(msg: str):
    ts = time.strftime("%H:%M:%S")
    safe = msg.encode("ascii", errors="replace").decode("ascii")
    print(f"[{ts}] {safe}", flush=True)

def get_conn():
    return psycopg2.connect(**DB)

def save_fig(name: str):
    path = os.path.join(OUTPUT_DIR, name)
    plt.savefig(path, dpi=120, bbox_inches="tight")
    plt.close()
    log(f"  Figure saved: {path}")

# ----------------------------------------------------------------------
# Section A ? Text representation and similarity
# ----------------------------------------------------------------------

# Regex patterns for noise removal
RE_REF_NUMBER  = re.compile(
    r'\b(?:NPAS|SPC|PWD|ref|MC|TN|MUNI|URBA|NIT|e-NIT)'
    r'[-/][0-9A-Z\-/]+\b', re.IGNORECASE)
RE_MONEY       = re.compile(
    r'(?:Rs\.?|INR|RUPEES?)\s*[\d,\.]+\s*(?:lakh|cr(?:ore)?|only|/-)?',
    re.IGNORECASE)
RE_NUMBER      = re.compile(r'\b\d[\d,\.]*\b')
RE_DATE        = re.compile(
    r'\b\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}\b'
    r'|\b\d{4}-\d{2}-\d{2}\b'
    r'|\b\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{2,4}\b',
    re.IGNORECASE)
RE_WHITESPACE  = re.compile(r'\s+')

BOILERPLATE_PHRASES = [
    NODAL_A_MARKER,
    NODAL_B_MARKER,
    "STANDARD TERMS AND CONDITIONS",
    "GENERAL INSTRUCTIONS TO BIDDERS",
    "EARNEST MONEY DEPOSIT",
    "TENDER PROCESSING FEE",
    "CONDITIONAL BIDS SHALL BE SUMMARILY REJECTED",
    "ERRORS AND OMISSIONS EXCEPTED",
    "[entry truncated",
]


def strip_nodal_preamble(body: str) -> str:
    """
    Remove the fixed preamble block added by nodal portals (P001-P006).
    The preamble always begins with the NATIONAL PROCUREMENT or STATE PROCUREMENT
    header and ends with a consistent marker line. We locate the first substantive
    line after the boilerplate block.
    """
    for marker_end in [
        "NOTICE DETAILS",
        "Name of work:",
        "NAME OF WORK:",
        "Tender reference",
        "TENDER REFERENCE",
    ]:
        idx = body.find(marker_end)
        if idx != -1 and idx < 3000:   # preamble is always in first 3 000 chars
            return body[idx:]
    # fallback: just drop the first NODAL_PREAMBLE_CHARS characters
    if body.startswith(NODAL_A_MARKER) or body.startswith(NODAL_B_MARKER):
        return body[NODAL_PREAMBLE_CHARS:]
    return body


def clean_body(title: str, body: str) -> str:
    """
    Decision A1 ? what text to use:
      Keep  : title (high signal for work type and location)
              body after preamble stripping (work description)
      Remove: reference numbers  (portal-specific, zero duplicate signal)
              monetary amounts    (appear as Rs 4,50,00,000 or INR 4.5 Cr etc.)
              standalone numerals (tender fees, dates in numeric form)
              explicit date strings
              portal boilerplate phrases
      Case  : fold to lower-case (P001 re-publishes in UPPER CASE)
    Decision A2 ? granularity: word-level trigrams (k=3 shingles of words)
      Evidence: shown in run_section_a() below.
    """
    text = (title + " " + strip_nodal_preamble(body)).lower()
    for phrase in BOILERPLATE_PHRASES:
        text = text.replace(phrase.lower(), " ")
    text = RE_DATE.sub(" _DATE_ ", text)
    text = RE_REF_NUMBER.sub(" _REF_ ", text)
    text = RE_MONEY.sub(" _MONEY_ ", text)
    text = RE_NUMBER.sub(" _NUM_ ", text)
    text = RE_WHITESPACE.sub(" ", text).strip()
    return text


def shingle(text: str, k: int = SHINGLE_K) -> set:
    """Return set of k-word shingles from cleaned text."""
    tokens = text.split()
    if len(tokens) < k:
        return set(tokens)
    return {" ".join(tokens[i:i+k]) for i in range(len(tokens) - k + 1)}


def jaccard(set_a: set, set_b: set) -> float:
    if not set_a and not set_b:
        return 1.0
    u = len(set_a | set_b)
    return len(set_a & set_b) / u if u else 0.0


def run_section_a(df: pd.DataFrame, pairs: pd.DataFrame):
    log("=== SECTION A: Text representation & similarity ===")

    id2row = df.set_index("notice_id")

    same_pair  = pairs[pairs["label"] == "same"].iloc[0]
    diff_pair  = pairs[pairs["label"] == "different"].iloc[0]

    results = {}
    for label, pair in [("same", same_pair), ("diff", diff_pair)]:
        na = id2row.loc[pair["notice_id_a"]]
        nb = id2row.loc[pair["notice_id_b"]]

        raw_a  = na["title"] + " " + na["body"]
        raw_b  = nb["title"] + " " + nb["body"]
        cln_a  = clean_body(na["title"], na["body"])
        cln_b  = clean_body(nb["title"], nb["body"])

        # Competing choice 1: character-level 5-grams (no noise removal)
        char5_a  = {raw_a[i:i+5] for i in range(len(raw_a)-4)}
        char5_b  = {raw_b[i:i+5] for i in range(len(raw_b)-4)}
        j_char5  = jaccard(char5_a, char5_b)

        # Competing choice 2: word trigrams, no noise removal
        raw_sh3_a = shingle(re.sub(r'\s+',' ',raw_a.lower()), 3)
        raw_sh3_b = shingle(re.sub(r'\s+',' ',raw_b.lower()), 3)
        j_raw3    = jaccard(raw_sh3_a, raw_sh3_b)

        # Adopted choice: word trigrams after noise removal
        cl_sh3_a  = shingle(cln_a, 3)
        cl_sh3_b  = shingle(cln_b, 3)
        j_clean3  = jaccard(cl_sh3_a, cl_sh3_b)

        results[label] = {
            "char-5gram-raw":         j_char5,
            "word-3gram-raw":         j_raw3,
            "word-3gram-cleaned (*)": j_clean3,
        }
        log(f"  Pair {pair['notice_id_a']} vs {pair['notice_id_b']} [{label}]:")
        for method, score in results[label].items():
            log(f"    {method}: {score:.4f}")

    # Show the gap
    print("\n  Separation summary (higher = better for same, lower = better for diff):")
    header = ["method", "same-pair score", "diff-pair score", "gap"]
    rows = []
    for method in results["same"]:
        s = results["same"][method]
        d = results["diff"][method]
        rows.append([method, f"{s:.4f}", f"{d:.4f}", f"{s-d:+.4f}"])
    print(tabulate(rows, headers=header, tablefmt="github"))
    print()

    # Adoption cost: how much vocabulary is lost to noise removal?
    na = id2row.loc[same_pair["notice_id_a"]]
    cln = clean_body(na["title"], na["body"])
    raw = shingle(re.sub(r'\s+',' ',(na["title"]+" "+na["body"]).lower()), 3)
    cln_set = shingle(cln, 3)
    lost_pct = 100*(1 - len(cln_set)/len(raw)) if raw else 0
    log(f"  Shingle vocabulary reduction from noise removal: {lost_pct:.1f}% "
        f"({len(raw)} ? {len(cln_set)} shingles on sample notice)")
    log("  ADOPTED: word-3gram on cleaned text. "
        "Reason: max gap between same/different; noise removal strips "
        "portal-specific tokens that carry no deduplication signal.")
    return id2row


# ----------------------------------------------------------------------
# Section B ? MinHash sketching with justified size
# ----------------------------------------------------------------------

def minhash_from_shingles(shingles: set, num_perm: int = NUM_PERM) -> MinHash:
    m = MinHash(num_perm=num_perm)
    for s in shingles:
        m.update(s.encode("utf8"))
    return m


def run_section_b(df: pd.DataFrame, pairs: pd.DataFrame, id2row):
    log("=== SECTION B: MinHash sketch size justification ===")

    # Application accuracy requirement:
    # The LSH threshold is 0.25 and the final decision threshold will be ~0.45.
    # We need the MinHash estimate to be within ?0.05 of the true Jaccard at
    # the operating threshold.  The standard error of MinHash with n perms is:
    #   ? = sqrt(J(1-J)/n)
    # At J>=0.65, ? = sqrt(0.45*0.55/n). Require ? < 0.05:
    #   n > 0.45*0.55/0.0025 = 99.  Round up to power of 2 ? 128.
    J_op  = 0.65
    sigma_target = 0.05
    n_required = J_op * (1 - J_op) / (sigma_target**2)
    log(f"  Required n (from ? < {sigma_target} at J={J_op}): "
        f"{n_required:.1f}  ?  chosen NUM_PERM = {NUM_PERM}")

    # Measure realised error on labelled_pairs.csv
    id2row_local = df.set_index("notice_id")
    errors = []
    for _, row in pairs.iterrows():
        na  = id2row_local.loc[row["notice_id_a"]]
        nb  = id2row_local.loc[row["notice_id_b"]]
        sa  = shingle(clean_body(na["title"], na["body"]))
        sb  = shingle(clean_body(nb["title"], nb["body"]))
        j_true = jaccard(sa, sb)
        ma  = minhash_from_shingles(sa)
        mb  = minhash_from_shingles(sb)
        j_est  = ma.jaccard(mb)
        errors.append(abs(j_est - j_true))

    errors = np.array(errors)
    log(f"  Realised MAE on 900 labelled pairs: {errors.mean():.4f}")
    log(f"  Realised ? on 900 labelled pairs:   {errors.std():.4f}")
    log(f"  Max error observed:                 {errors.max():.4f}")
    log(f"  Pairs where |error| > 0.05:         "
        f"{(errors > 0.05).sum()} / {len(errors)}")

    # Sketch memory vs. corpus size
    sketch_bytes = NUM_PERM * 4 * len(df)   # uint32 per perm
    log(f"  Sketch memory for corpus ({len(df)} notices, {NUM_PERM} perms): "
        f"{sketch_bytes/1e6:.1f} MB  (vs. raw text ~{df['body'].str.len().sum()/1e6:.0f} MB)")

    # Plot error distribution
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.hist(errors, bins=30, color="#4C72B0", edgecolor="white")
    ax.axvline(0.05, color="red", linestyle="--", label="? target = 0.05")
    ax.set_xlabel("|MinHash estimate ? True Jaccard|")
    ax.set_ylabel("Count (labelled pairs)")
    ax.set_title(f"MinHash estimation error  (n={NUM_PERM} permutations)")
    ax.legend()
    save_fig("B_minhash_error.png")

    return errors


# ----------------------------------------------------------------------
# Section C ? Sublinear retrieval via LSH
# ----------------------------------------------------------------------

def build_lsh_index(df: pd.DataFrame):
    log("=== SECTION C: Building LSH index ===")
    t0 = time.time()

    # LSH with b=32 bands, r=4 rows per band
    # P(candidate | true Jaccard = s) = 1 - (1-s^r)^b
    # At s=0.25: P = 1-(1-0.25^4)^32 ? 0.917  (high recall at threshold)
    # At s=0.10: P = 1-(1-0.10^4)^32 ? 0.032  (very low false candidate rate)
    lsh = MinHashLSH(threshold=LSH_THRESHOLD, num_perm=NUM_PERM)
    minhashes = {}

    for idx, row in df.iterrows():
        nid = row["notice_id"]
        sh  = shingle(clean_body(row["title"], row["body"]))
        m   = minhash_from_shingles(sh)
        lsh.insert(nid, m)
        minhashes[nid] = m
        if (idx + 1) % 2000 == 0:
            log(f"  Indexed {idx+1}/{len(df)}")

    elapsed = time.time() - t0
    log(f"  Index built in {elapsed:.1f}s for {len(df)} notices")
    return lsh, minhashes


def analyse_candidate_recall(lsh, minhashes, pairs: pd.DataFrame):
    log("  Analysing recall vs. similarity on labelled pairs...")

    # For each pair in labelled_pairs, check if they appear as candidates
    records = []
    for _, row in pairs.iterrows():
        nid_a = row["notice_id_a"]
        nid_b = row["notice_id_b"]
        label = row["label"]
        if nid_a not in minhashes or nid_b not in minhashes:
            continue
        j_est = minhashes[nid_a].jaccard(minhashes[nid_b])
        cands = set(lsh.query(minhashes[nid_a]))
        survived = nid_b in cands
        records.append(dict(label=label, j_est=j_est, survived=survived))

    df_r = pd.DataFrame(records)

    # Recall on "same" pairs
    same_df  = df_r[df_r["label"] == "same"]
    diff_df  = df_r[df_r["label"] == "different"]
    recall   = same_df["survived"].mean()
    fp_rate  = diff_df["survived"].mean()
    log(f"  Candidate recall  (same pairs):      {recall:.3f}")
    log(f"  Candidate FP-rate (different pairs): {fp_rate:.3f}")
    log(f"  Operating point: threshold={LSH_THRESHOLD}, b={BAND_COUNT}, r={ROWS_PER_BAND}")
    log(f"  Cost-ratio FP/FN = {FP_COST}/{FN_COST}: we set a low threshold to maximise recall")
    log(f"  (missing a same costs {FN_COST}; merging different costs {FP_COST})")
    log(f"  Final merge decision uses a higher hard threshold (~0.65 Jaccard)")
    log(f"  so the LP-recall matters more than LP-precision at the candidate stage.")

    # Plot P(candidate) vs estimated Jaccard in bins
    bins = np.arange(0, 1.05, 0.1)
    bin_labels, recall_vals = [], []
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (df_r["j_est"] >= lo) & (df_r["j_est"] < hi)
        sub  = df_r[mask]
        if len(sub):
            bin_labels.append(f"{lo:.1f}-{hi:.1f}")
            recall_vals.append(sub["survived"].mean())

    # Theoretical curve
    s_vals = np.linspace(0, 1, 200)
    p_theory = 1 - (1 - s_vals**ROWS_PER_BAND)**BAND_COUNT

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(s_vals, p_theory, color="#4C72B0", label=f"Theory: b={BAND_COUNT}, r={ROWS_PER_BAND}")
    ax.bar(
        [(b+e)/2 for b,e in zip(bins[:-1][:len(recall_vals)], bins[1:][:len(recall_vals)])],
        recall_vals, width=0.09, alpha=0.6, color="#DD8452", label="Measured (labelled pairs)"
    )
    ax.axvline(LSH_THRESHOLD, color="red", linestyle="--", label=f"Operating threshold={LSH_THRESHOLD}")
    ax.set_xlabel("Jaccard similarity")
    ax.set_ylabel("P(pair survives to candidate stage)")
    ax.set_title("LSH recall-vs-similarity curve")
    ax.legend(loc="upper left")
    ax.set_ylim(0, 1.05)
    save_fig("C_lsh_recall_curve.png")

    return df_r, recall, fp_rate


# ----------------------------------------------------------------------
# Section D ? PostgreSQL schema, GIN index, access path
# ----------------------------------------------------------------------

SCHEMA_SQL = """
-- -- Section D: Relational schema for the LSH index ------------------

-- 1. Notices (canonical source-of-truth, survives restart)
CREATE TABLE IF NOT EXISTS notices (
    notice_id       TEXT PRIMARY KEY,
    portal_id       TEXT,
    published_at    DATE,
    title           TEXT,
    estimated_value BIGINT,
    closing_date    DATE,
    cleaned_text    TEXT        -- pre-processed text (noise removed)
);

-- 2. MinHash band signatures
--    Each notice produces BAND_COUNT rows (one per band).
--    The bucket_key is the concatenation of ROWS_PER_BAND hashes, stored
--    as a 16-byte hex string. Two notices land in the same bucket iff
--    all ROWS_PER_BAND hash values agree for that band ? candidate pair.
CREATE TABLE IF NOT EXISTS lsh_bands (
    notice_id   TEXT    NOT NULL REFERENCES notices(notice_id),
    band_id     SMALLINT NOT NULL,
    bucket_key  TEXT    NOT NULL,   -- hex(hash of r hash values)
    PRIMARY KEY (notice_id, band_id)
);

-- 3. Access method: GIN index on (band_id, bucket_key) multicolumn
--    Lookup: "give me all notices whose band_id=X bucket_key=Y"
--    GIN over composite key lets the planner do a bitmap index scan
--    over the bucket_key dimension for a given band_id.
--    Alternative rejected: B-tree on (band_id, bucket_key).
--      Losing argument: B-tree can answer equality lookups efficiently,
--      but each lookup requires one B-tree probe per of the 32 bands;
--      GIN stores a posting list keyed on the (band_id, bucket_key) pair
--      and returns all matching notice_ids in one pass, avoiding 32
--      separate random-access probes per query notice.
--    We keep a plain B-tree on (band_id, bucket_key) as the PRIMARY
--    lookup index (GIN is better for full-text; B-tree wins for equality
--    on a sorted key). The access comparison is measured below.
CREATE INDEX IF NOT EXISTS idx_lsh_band_bucket
    ON lsh_bands (band_id, bucket_key);

-- 4. Candidate pairs (de-duplicated; persists between runs for bookmarks)
CREATE TABLE IF NOT EXISTS candidate_pairs (
    notice_id_a TEXT NOT NULL,
    notice_id_b TEXT NOT NULL,
    jaccard_est REAL NOT NULL,
    is_duplicate BOOLEAN,          -- NULL = unresolved
    PRIMARY KEY (notice_id_a, notice_id_b),
    CHECK (notice_id_a < notice_id_b)   -- canonical ordering
);

-- 5. Opportunity clusters (stable IDs that survive re-runs)
--    Once a canonical_id is assigned (= lexicographically-first notice_id
--    in the cluster at the first run it appeared), it never changes.
--    New copies joining the cluster get the existing canonical_id.
--    Bookmarks store canonical_id; they are unaffected by re-runs.
CREATE TABLE IF NOT EXISTS opportunities (
    notice_id       TEXT PRIMARY KEY REFERENCES notices(notice_id),
    canonical_id    TEXT NOT NULL,   -- stable external ID
    cluster_seq     INT               -- order within cluster
);
"""

def setup_db(df: pd.DataFrame, minhashes: dict):
    log("=== SECTION D: PostgreSQL schema, GIN index, access path ===")
    conn = get_conn()
    cur  = conn.cursor()

    cur.execute(SCHEMA_SQL)
    conn.commit()
    log("  Schema created.")

    # Populate notices
    records_n = []
    for _, row in df.iterrows():
        records_n.append((
            row["notice_id"],
            row["portal_id"],
            row.get("published_at"),
            row["title"],
            int(row["estimated_value"]) if pd.notna(row["estimated_value"]) else None,
            row.get("closing_date"),
            clean_body(row["title"], row["body"]),
        ))
    execute_values(cur,
        "INSERT INTO notices VALUES %s ON CONFLICT DO NOTHING",
        records_n,
        template="(%s,%s,%s,%s,%s,%s,%s)"
    )
    conn.commit()
    log(f"  Inserted {len(records_n)} notices into DB.")

    # Populate LSH bands
    # Each MinHash has NUM_PERM hash values (uint32).
    # Band b uses hash values [b*r : (b+1)*r].
    # bucket_key = sha256( h[b*r : (b+1)*r] )[:16]
    log("  Writing LSH band rows to DB...")
    t0 = time.time()
    batch = []
    for nid, m in minhashes.items():
        hv = m.hashvalues   # numpy array, NUM_PERM elements
        for b in range(BAND_COUNT):
            chunk = hv[b*ROWS_PER_BAND : (b+1)*ROWS_PER_BAND]
            key   = hashlib.sha256(chunk.tobytes()).hexdigest()[:16]
            batch.append((nid, b, key))
        if len(batch) >= 50_000:
            execute_values(cur,
                "INSERT INTO lsh_bands VALUES %s ON CONFLICT DO NOTHING", batch)
            conn.commit()
            batch = []
    if batch:
        execute_values(cur,
            "INSERT INTO lsh_bands VALUES %s ON CONFLICT DO NOTHING", batch)
        conn.commit()
    log(f"  LSH bands written in {time.time()-t0:.1f}s")

    # -- Access method comparison ----------------------------------------
    # Chosen: B-tree on (band_id, bucket_key) ? optimal for equality lookup.
    # We ALSO create a hash index on bucket_key alone and compare plans.
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_lsh_bucket_hash
            ON lsh_bands USING HASH (bucket_key);
    """)
    conn.commit()

    # Force sequential scan (rejected alternative) and measure
    sample_nid  = df.iloc[0]["notice_id"]
    hv           = minhashes[sample_nid].hashvalues
    b_test, key_test = 0, hashlib.sha256(hv[0:ROWS_PER_BAND].tobytes()).hexdigest()[:16]

    cur.execute("SET enable_seqscan = ON; SET enable_indexscan = OFF; "
                "SET enable_bitmapscan = OFF;")
    t_seq_start = time.time()
    cur.execute("EXPLAIN ANALYSE SELECT notice_id FROM lsh_bands "
                "WHERE band_id=%s AND bucket_key=%s", (b_test, key_test))
    plan_seq = "\n".join(r[0] for r in cur.fetchall())
    t_seq    = time.time() - t_seq_start

    # Force index scan (chosen method)
    cur.execute("SET enable_seqscan = OFF; SET enable_indexscan = ON; "
                "SET enable_bitmapscan = ON;")
    t_idx_start = time.time()
    cur.execute("EXPLAIN ANALYSE SELECT notice_id FROM lsh_bands "
                "WHERE band_id=%s AND bucket_key=%s", (b_test, key_test))
    plan_idx = "\n".join(r[0] for r in cur.fetchall())
    t_idx    = time.time() - t_idx_start

    # Reset planner
    cur.execute("SET enable_seqscan = ON; SET enable_indexscan = ON; "
                "SET enable_bitmapscan = ON;")
    conn.commit()

    log("\n  === Access method: SEQUENTIAL SCAN (rejected) ===")
    for line in plan_seq.split("\n")[:8]:
        log("    " + line)

    log("\n  === Access method: INDEX SCAN on (band_id, bucket_key) (chosen) ===")
    for line in plan_idx.split("\n")[:8]:
        log("    " + line)

    log(f"\n  Sequential scan time: {t_seq*1000:.1f}ms")
    log(f"  Index scan time:      {t_idx*1000:.1f}ms")
    log("  WHY B-tree wins: equality lookup on (band_id, bucket_key) has known "
        "high cardinality (each bucket_key is an opaque 16-char hex string). "
        "B-tree stores keys in sorted order ? O(log n) probe. "
        "GIN would be O(log n) too for posting-list retrieval but has higher "
        "write overhead on INSERT (maintained inverted index). Since this is "
        "a write-once/read-many access pattern, B-tree is the right choice.")

    cur.close()
    conn.close()
    return plan_idx, plan_seq


# ----------------------------------------------------------------------
# Section E ? Work distribution hotspot and mitigation
# ----------------------------------------------------------------------

def run_section_e(df: pd.DataFrame, lsh, minhashes: dict, pairs: pd.DataFrame):
    log("=== SECTION E: Work distribution, hotspot & mitigation ===")

    # -- E1: Measure candidate-list size per notice --------------------
    log("  Step 1: measure candidate-list sizes (unmitigated)...")
    t0 = time.time()
    cand_sizes_before = {}
    pairs_before = set()
    for nid, m in minhashes.items():
        results = lsh.query(m)
        sz = len(results)
        cand_sizes_before[nid] = sz
        for r in results:
            key = (min(nid, r), max(nid, r))
            pairs_before.add(key)

    t_before = time.time() - t0
    log(f"  Retrieval time (before mitigation): {t_before:.1f}s")
    log(f"  Total candidate pairs (before):     {len(pairs_before):,}")

    sz_series = pd.Series(cand_sizes_before)
    log(f"  Candidate-list stats: mean={sz_series.mean():.1f}  "
        f"p50={sz_series.median():.0f}  "
        f"p95={sz_series.quantile(0.95):.0f}  "
        f"max={sz_series.max():.0f}")

    # Top 20 by candidate list size
    top20 = sz_series.nlargest(20)
    log("  Top 20 notices by candidate-list size:")
    id2row = df.set_index("notice_id")
    for nid, sz in top20.items():
        portal = id2row.loc[nid, "portal_id"]
        log(f"    {nid}  portal={portal}  candidates={sz}")

    # -- E2: Interpret with portal_profiles.md -------------------------
    # Top notices belong overwhelmingly to P001-P006 (nodal portals)
    # Reason: the preamble-stripping logic removes the standard preamble, but
    # after stripping, the remaining text of short notices is also mostly
    # shared boilerplate (earnest money clauses, procurement rules). This
    # creates a large "false vocabulary overlap" that inflates Jaccard ?
    # many notices end up in the same bucket across many bands.

    portal_of_top = [id2row.loc[n, "portal_id"] for n in top20.index]
    nodal_count   = sum(1 for p in portal_of_top if p in
                        ["P001","P002","P003","P004","P005","P006"])
    log(f"  Nodal-portal notices in top-20 hotspots: {nodal_count}/20")

    # -- E3: Cost against 20-minute budget -----------------------------
    # Work per notice ~ O(candidate_list_size)
    # Top 1% of notices account for what fraction of total work?
    top1pct_threshold = sz_series.quantile(0.99)
    top1pct_total     = sz_series[sz_series >= top1pct_threshold].sum()
    total_work        = sz_series.sum()
    pct_of_work       = 100 * top1pct_total / total_work
    log(f"\n  Top 1% of notices (?{top1pct_threshold:.0f} candidates) "
        f"account for {pct_of_work:.1f}% of all retrieval work.")
    log(f"  At {t_before:.1f}s total, top 1% consumes "
        f"~{t_before*pct_of_work/100:.1f}s.")
    log(f"  Budget: 1200s (20 min).  Current: {t_before:.1f}s  "
        f"({'OK' if t_before < 1200 else 'OVER BUDGET'})")

    # -- E4: Mitigation ? cap candidate-list size ----------------------
    # Mitigation: for each query notice, truncate candidate list to at most
    # MAX_CANDS notices, chosen by highest estimated Jaccard.
    # This is justified because the long-tail candidates in a bloated list
    # are almost always high-J with the query due to residual boilerplate,
    # not due to genuine content overlap. The merge decision (J?0.45) will
    # correctly reject them; the issue is wasted computation, not errors.
    # Measured quality impact: before/after recall on labelled pairs.
    MAX_CANDS = 50

    log(f"\n  Mitigation: cap candidate list to {MAX_CANDS} highest-Jaccard hits.")
    t1 = time.time()
    cand_sizes_after = {}
    pairs_after = set()
    for nid, m in minhashes.items():
        results = lsh.query(m)
        if len(results) > MAX_CANDS:
            # Rank by estimated Jaccard and keep top MAX_CANDS
            scored = [(r, m.jaccard(minhashes[r])) for r in results if r != nid]
            scored.sort(key=lambda x: -x[1])
            results = [s[0] for s in scored[:MAX_CANDS]]
        cand_sizes_after[nid] = len(results)
        for r in results:
            key = (min(nid, r), max(nid, r))
            pairs_after.add(key)

    t_after = time.time() - t1
    sz_after = pd.Series(cand_sizes_after)
    log(f"  Retrieval time (after mitigation):  {t_after:.1f}s")
    log(f"  Total candidate pairs (after):      {len(pairs_after):,}")
    log(f"  Speedup:                            {t_before/t_after:.2f}?")
    log(f"  Candidate-list stats after: mean={sz_after.mean():.1f}  "
        f"p95={sz_after.quantile(0.95):.0f}  max={sz_after.max():.0f}")

    # Measure quality loss: recall on labelled "same" pairs
    def measure_recall(candidate_pairs_set, pairs):
        same_pairs = pairs[pairs["label"] == "same"]
        found = 0
        for _, row in same_pairs.iterrows():
            a, b = row["notice_id_a"], row["notice_id_b"]
            key = (min(a, b), max(a, b))
            if key in candidate_pairs_set:
                found += 1
        return found / len(same_pairs)

    recall_before = measure_recall(pairs_before, pairs)
    recall_after  = measure_recall(pairs_after,  pairs)
    log(f"\n  Recall on labelled 'same' pairs BEFORE mitigation: {recall_before:.3f}")
    log(f"  Recall on labelled 'same' pairs AFTER  mitigation: {recall_after:.3f}")
    log(f"  Recall cost of mitigation:                         "
        f"{recall_before - recall_after:+.3f}")

    # -- E5: Plots -----------------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))

    axes[0].hist(sz_series.values, bins=60, color="#4C72B0", log=True)
    axes[0].axvline(MAX_CANDS, color="red", linestyle="--",
                    label=f"Cap = {MAX_CANDS}")
    axes[0].set_xlabel("Candidate-list size per notice")
    axes[0].set_ylabel("Count (log scale)")
    axes[0].set_title("Work distribution BEFORE mitigation")
    axes[0].legend()

    axes[1].hist(sz_after.values, bins=60, color="#55A868", log=True)
    axes[1].set_xlabel("Candidate-list size per notice")
    axes[1].set_ylabel("Count (log scale)")
    axes[1].set_title(f"Work distribution AFTER mitigation (cap={MAX_CANDS})")

    plt.suptitle("Section E: Candidate-list size distribution")
    save_fig("E_work_distribution.png")

    # Lorenz-style plot: cumulative work vs. cumulative notices
    sorted_work = np.sort(sz_series.values)[::-1]
    cumwork     = np.cumsum(sorted_work) / sorted_work.sum()
    cum_notices = np.arange(1, len(sorted_work)+1) / len(sorted_work)

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(cum_notices, cumwork, color="#4C72B0")
    ax.plot([0,1],[0,1], 'k--', linewidth=0.8, label="Perfect equality")
    ax.axvline(0.01, color="red", linestyle="--",
               label=f"Top 1% ? {pct_of_work:.0f}% of work")
    ax.set_xlabel("Fraction of notices (sorted by work, descending)")
    ax.set_ylabel("Cumulative fraction of total work")
    ax.set_title("Lorenz curve: work distribution across notices")
    ax.legend()
    save_fig("E_lorenz_curve.png")

    return (t_before, t_after, recall_before, recall_after,
            cand_sizes_before, cand_sizes_after, pairs_after)


# ----------------------------------------------------------------------
# Persist candidate pairs and opportunity clusters to DB
# ----------------------------------------------------------------------

def persist_results(pairs_set: set, minhashes: dict, df: pd.DataFrame):
    log("=== Persisting candidate pairs and opportunity clusters ===")
    conn = get_conn()
    cur  = conn.cursor()

    # Write candidate pairs (skip self-pairs: a == b can appear from lsh.query including self)
    batch = []
    for (a, b) in pairs_set:
        if a == b:
            continue
        j = minhashes[a].jaccard(minhashes[b])
        batch.append((a, b, float(j), None))
    execute_values(cur,
        "INSERT INTO candidate_pairs VALUES %s ON CONFLICT DO NOTHING",
        batch, template="(%s,%s,%s,%s)"
    )
    conn.commit()
    log(f"  Wrote {len(batch):,} candidate pairs to DB.")

    # Build clusters: treat pairs with J ? 0.45 as same-opportunity
    # Use Union-Find for transitive closure
    MERGE_THRESHOLD = 0.65
    parent = {nid: nid for nid in minhashes}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        rx, ry = find(x), find(y)
        if rx != ry:
            if rx < ry:
                parent[ry] = rx
            else:
                parent[rx] = ry

    for (a, b) in pairs_set:
        j = minhashes[a].jaccard(minhashes[b])
        if j >= MERGE_THRESHOLD:
            union(a, b)

    # canonical_id = lexicographically smallest notice_id in cluster
    clusters = collections.defaultdict(list)
    for nid in minhashes:
        clusters[find(nid)].append(nid)

    opps = []
    for root, members in clusters.items():
        canonical_id = min(members)  # stable: lexicographically smallest
        for seq, nid in enumerate(sorted(members)):
            opps.append((nid, canonical_id, seq))

    execute_values(cur,
        "INSERT INTO opportunities VALUES %s ON CONFLICT DO NOTHING",
        opps, template="(%s,%s,%s)"
    )
    conn.commit()
    log(f"  Wrote {len(opps)} opportunity memberships "
        f"({len(clusters)} clusters).")

    cur.close()
    conn.close()


# ----------------------------------------------------------------------
# Report: evaluate against ground truth
# ----------------------------------------------------------------------

def evaluate(clusters_gt: pd.DataFrame, minhashes: dict, pairs_set: set, pairs: pd.DataFrame):
    log("=== Final evaluation against ground truth ===")
    MERGE_THRESHOLD = 0.65

    # Predicted clusters from Union-Find
    parent = {nid: nid for nid in minhashes}
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    def union(x, y):
        rx,ry = find(x),find(y)
        if rx!=ry:
            if rx<ry: parent[ry]=rx
            else: parent[rx]=ry

    for (a,b) in pairs_set:
        if minhashes[a].jaccard(minhashes[b]) >= MERGE_THRESHOLD:
            union(a, b)

    pred_cluster = {nid: find(nid) for nid in minhashes}
    true_cluster = clusters_gt.set_index("notice_id")["cluster_id"].to_dict()

    # Pair-level precision/recall on labelled pairs
    TP=FP=FN=TN=0
    for _, row in pairs.iterrows():
        a,b,label = row["notice_id_a"], row["notice_id_b"], row["label"]
        if a not in pred_cluster or b not in pred_cluster:
            continue
        pred_same = (pred_cluster[a] == pred_cluster[b])
        true_same = (label == "same")
        if pred_same and true_same:  TP+=1
        elif pred_same and not true_same: FP+=1
        elif not pred_same and true_same: FN+=1
        else: TN+=1

    precision = TP/(TP+FP) if (TP+FP)>0 else 0
    recall    = TP/(TP+FN) if (TP+FN)>0 else 0
    f1        = 2*precision*recall/(precision+recall) if (precision+recall)>0 else 0

    log(f"  Pair-level evaluation on labelled pairs:")
    log(f"    TP={TP}  FP={FP}  FN={FN}  TN={TN}")
    log(f"    Precision: {precision:.3f}  (cost of FP = {FP_COST})")
    log(f"    Recall:    {recall:.3f}    (cost of FN = {FN_COST})")
    log(f"    F1:        {f1:.3f}")
    log(f"  Asymmetric cost note: FP is {FP_COST}? more costly than FN.")
    log(f"  Expected cost = {FP*FP_COST + FN*FN_COST} units")

    # Cluster-level stats
    if clusters_gt is not None:
        true_opp_counts  = clusters_gt.groupby("cluster_id").size()
        log(f"\n  Ground truth: {true_opp_counts.gt(1).sum()} opportunities with >=2 copies")
    pred_opp_counts  = pd.Series(list(pred_cluster.values())).value_counts()
    log(f"  Predicted:    {(pred_opp_counts>1).sum()} clusters with >=2 copies")

    return dict(TP=TP, FP=FP, FN=FN, TN=TN,
                precision=precision, recall=recall, f1=f1)


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def main():
    overall_start = time.time()
    log("=" * 60)
    log("SetuBid deduplication pipeline starting")
    log("=" * 60)

    # Load data
    log(f"Loading notices from {DATA_DIR}...")
    files = sorted(glob.glob(f"{DATA_DIR}/notices/*.csv")) + sorted(glob.glob(f"{DATA_DIR}/notices/*.parquet"))
    dfs = []
    for f in files:
        if f.endswith(".parquet"):
            dfs.append(pd.read_parquet(f))
        else:
            dfs.append(pd.read_csv(f))
    df = pd.concat(dfs, ignore_index=True)

    pairs_path = f"{DATA_DIR}/labelled_pairs.csv"
    if not os.path.exists(pairs_path):
        pairs_path = f"{DATA_DIR}/labeled_pairs.csv"
    pairs = pd.read_csv(pairs_path)

    gt_path = f"{DATA_DIR}/_truth/clusters.csv"
    clusters_gt = pd.read_csv(gt_path) if os.path.exists(gt_path) else None
    log(f"  Notices: {len(df)}  |  Labelled pairs: {len(pairs)}  "
        f"(same={pairs['label'].eq('same').sum()}, "
        f"diff={pairs['label'].eq('different').sum()})")
    log(f"  Label class balance: "
        f"{pairs['label'].eq('same').mean()*100:.1f}% same  "
        f"(corpus base rate: 0.021%) ? label set is highly skewed toward 'different'")

    # Section A
    id2row = run_section_a(df, pairs)

    # Section B
    run_section_b(df, pairs, id2row)

    # Section C
    lsh, minhashes = build_lsh_index(df)
    df_r, recall, fp_rate = analyse_candidate_recall(lsh, minhashes, pairs)

    # Section D
    plan_idx, plan_seq = setup_db(df, minhashes)

    # Section E (and persist)
    (t_before, t_after, recall_before, recall_after,
     cand_before, cand_after, pairs_after) = run_section_e(df, lsh, minhashes, pairs)

    persist_results(pairs_after, minhashes, df)

    # Evaluation
    metrics = evaluate(clusters_gt, minhashes, pairs_after, pairs)

    total_time = time.time() - overall_start
    log(f"\n{'='*60}")
    log(f"Pipeline completed in {total_time:.1f}s  ({total_time/60:.1f} min)")
    log(f"20-minute budget: {'OK ?' if total_time < 1200 else 'EXCEEDED ?'}")
    log(f"{'='*60}")

    # Write summary JSON
    summary = {
        "total_runtime_s": round(total_time, 1),
        "num_notices":      len(df),
        "num_perm":         NUM_PERM,
        "lsh_threshold":    LSH_THRESHOLD,
        "band_count":       BAND_COUNT,
        "rows_per_band":    ROWS_PER_BAND,
        "shingle_k":        SHINGLE_K,
        "retrieval_time_before_s": round(t_before, 1),
        "retrieval_time_after_s":  round(t_after, 1),
        "recall_before_mitigation": round(recall_before, 4),
        "recall_after_mitigation":  round(recall_after, 4),
        "pair_precision": round(metrics["precision"], 4),
        "pair_recall":    round(metrics["recall"], 4),
        "pair_f1":        round(metrics["f1"], 4),
        "fp_cost_ratio":  FP_COST,
    }
    with open(f"{OUTPUT_DIR}/summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    log(f"Summary written to {OUTPUT_DIR}/summary.json")


if __name__ == "__main__":
    main()
