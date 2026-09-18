#!/usr/bin/env python3
"""
report_generater.py
===================
Generates comprehensive Word (.docx) and PDF (.pdf) solution reports for
Question 1: Annapurna Stores Data Warehouse & Analytics Platform,
embedding MinIO UI screenshots and analytical benchmark plots.
"""

import os
import sys
import json
import pandas as pd
from datetime import datetime

import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    Table as RLTable, TableStyle, PageBreak, KeepTogether, HRFlowable, Image as RLImage
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

DOCX_OUT = os.path.join(BASE_DIR, "SOLUTION_REPORT.docx")
PDF_OUT = os.path.join(BASE_DIR, "SOLUTION_REPORT.pdf")

# Images
SHOT_1 = os.path.join(BASE_DIR, "Screenshot 2026-09-18 151840.png")
SHOT_2 = os.path.join(BASE_DIR, "Screenshot 2026-09-18 151849.png")
SHOT_3 = os.path.join(BASE_DIR, "Screenshot 2026-09-18 151858.png")

PLOT_A = os.path.join(OUTPUT_DIR, "A_scan_pruning_comparison.png")
PLOT_C = os.path.join(OUTPUT_DIR, "C_line_types_and_october_pitfall.png")
PLOT_F = os.path.join(OUTPUT_DIR, "F_monthly_revenue_reconciliation.png")

RECON_CSV = os.path.join(OUTPUT_DIR, "monthly_reconciliation.csv")
TASK_B_JSON = os.path.join(OUTPUT_DIR, "task_b_idempotence.json")


def set_cell_background(cell, fill_hex):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)


def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(
        f'<w:tcMar {nsdecls("w")}>'
        f'<w:top w:w="{top}" w:type="dxa"/>'
        f'<w:bottom w:w="{bottom}" w:type="dxa"/>'
        f'<w:left w:w="{left}" w:type="dxa"/>'
        f'<w:right w:w="{right}" w:type="dxa"/>'
        f'</w:tcMar>'
    )
    tcPr.append(tcMar)


def add_styled_table(doc, headers, data, col_widths=None):
    table = doc.add_table(rows=len(data) + 1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False

    hdr_cells = table.rows[0].cells
    for i, title in enumerate(headers):
        hdr_cells[i].text = title
        set_cell_background(hdr_cells[i], "1A365D")
        set_cell_margins(hdr_cells[i], top=120, bottom=120, left=160, right=160)
        p = hdr_cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        for run in p.runs:
            run.font.bold = True
            run.font.color.rgb = RGBColor(255, 255, 255)
            run.font.size = Pt(9)
            run.font.name = "Calibri"

    for r_idx, row_data in enumerate(data):
        row_cells = table.rows[r_idx + 1].cells
        bg_color = "F7FAFC" if r_idx % 2 == 1 else "FFFFFF"
        for c_idx, val in enumerate(row_data):
            row_cells[c_idx].text = str(val)
            set_cell_background(row_cells[c_idx], bg_color)
            set_cell_margins(row_cells[c_idx], top=80, bottom=80, left=160, right=160)
            p = row_cells[c_idx].paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            for run in p.runs:
                run.font.size = Pt(8.5)
                run.font.name = "Calibri"
                run.font.color.rgb = RGBColor(45, 55, 72)

    if col_widths:
        for row in table.rows:
            for idx, width in enumerate(col_widths):
                row.cells[idx].width = Inches(width)

    p_after = doc.add_paragraph()
    p_after.paragraph_format.space_after = Pt(8)
    return table


def add_image_with_caption(doc, img_path, caption_text, width=Inches(5.5)):
    if os.path.exists(img_path):
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img.paragraph_format.space_before = Pt(6)
        p_img.paragraph_format.space_after = Pt(2)
        run = p_img.add_run()
        run.add_picture(img_path, width=width)

        p_cap = doc.add_paragraph()
        p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_cap.paragraph_format.space_before = Pt(2)
        p_cap.paragraph_format.space_after = Pt(12)
        r_cap = p_cap.add_run(caption_text)
        r_cap.font.size = Pt(8.5)
        r_cap.font.italic = True
        r_cap.font.color.rgb = RGBColor(113, 128, 150)


def build_docx():
    print("Generating DOCX report with embedded screenshots and plots...")
    doc = docx.Document()

    for s in doc.sections:
        s.top_margin = Inches(0.8)
        s.bottom_margin = Inches(0.8)
        s.left_margin = Inches(0.8)
        s.right_margin = Inches(0.8)

    # Title Block
    p_title = doc.add_paragraph()
    run = p_title.add_run("Question 1: Annapurna Stores Data Warehouse Platform")
    run.font.size = Pt(20)
    run.font.bold = True
    run.font.color.rgb = RGBColor(26, 54, 93)

    p_sub = doc.add_paragraph()
    run_sub = p_sub.add_run("Three Answers to One Question — Architecture, Gotchas, and Empirical Defense Report")
    run_sub.font.size = Pt(12.5)
    run_sub.font.color.rgb = RGBColor(74, 85, 104)

    p_meta = doc.add_paragraph()
    p_meta.add_run("Stack: PostgreSQL 16 · MinIO S3 Object Store · DuckDB In-Memory Engine\n"
                   "Execution: Reproducible via single cold-start command: docker compose up --build")
    p_meta.runs[0].font.size = Pt(9.5)
    p_meta.runs[0].font.color.rgb = RGBColor(113, 128, 150)

    doc.add_heading("1. Executive Summary & CFO Mandate", level=1)
    doc.add_paragraph(
        "Annapurna Stores operates 12 supermarkets across India. The CFO discovered that three different people "
        "reported three different revenue figures for October from the same data folder, while biscuit pricing inquiries "
        "returned current shelf prices rather than historical prices.\n\n"
        "This platform solves every challenge through cold-start containerization, schema normalization, idempotence "
        "proofs, SCD Type 2 dimension mapping, non-revenue line type filtering, and cross-system federated querying."
    )

    doc.add_heading("2. Task A: Platform Standup & MinIO Object Store Landing", level=1)
    doc.add_paragraph(
        "We organized raw daily exports into Hive-style Partitioned Columnar Parquet layout:\n"
        "  s3://annapurna-sales/store_id={store_id}/month={YYYY-MM}/data.parquet\n"
        "Exactly 144 partitions (12 stores x 12 months) are populated and verifiable via MinIO S3 Object Store."
    )

    # Embed MinIO Screenshots
    add_image_with_caption(doc, SHOT_1, "Figure 1: MinIO S3 Object Store Browser showing annapurna-sales bucket with 144 partitions across store_id=S01 to S12.", Inches(4.5))
    add_image_with_caption(doc, SHOT_2, "Figure 2: MinIO directory view inside store_id=S01 showing monthly subpartitions month=2024-01 through 2024-12.", Inches(4.5))
    add_image_with_caption(doc, SHOT_3, "Figure 3: MinIO columnar Parquet data file (data_0.parquet, 115.1 KiB) inside store_id=S01/month=2024-01.", Inches(4.5))

    doc.add_paragraph("Empirical scan comparison for single store-month query (Store S01, October 2024):")
    t1_headers = ["Metric", "Flat Folder Layout (CSV)", "Partitioned Parquet Layout", "Efficiency Gain"]
    t1_data = [
        ["Files Inspected", "4,457 files", "1 file", "99.98% pruned (4,456 skipped)"],
        ["Bytes Scanned", "68,706,877 bytes (65.52 MB)", "159,723 bytes (155.98 KB)", "99.77% pruned (68.55 MB saved)"],
        ["I/O Complexity", "O(N) full directory scan", "O(1) direct partition seek", "430x faster byte throughput"]
    ]
    add_styled_table(doc, t1_headers, t1_data, [1.5, 1.8, 1.8, 1.7])
    add_image_with_caption(doc, PLOT_A, "Figure 4: Task A Scan Efficiency & Pruning Comparison (Files inspected and MB volume scanned).", Inches(5.8))

    doc.add_heading("3. Task B: Idempotence & Safe Loading Proof", level=1)
    doc.add_paragraph(
        "Billing system re-sends occur when tills report transmission errors (68 re-sent files). We identify transactions "
        "using immutable composite key (bill_no, line_no). Running the ingestion step three times sequentially produces "
        "strictly identical output:"
    )

    t2_headers = ["Run", "Raw Ingested", "Deduplicated Rows", "Dropped Duplicates", "Deterministic SHA-256 Checksum"]
    t2_data = [
        ["Run 1", "1,137,585", "1,120,924", "16,661", "877893f7e480a216adcac651a3fb161ca38ee35effd068203b8e8aaf96a5eb5c"],
        ["Run 2", "1,137,585", "1,120,924", "16,661", "877893f7e480a216adcac651a3fb161ca38ee35effd068203b8e8aaf96a5eb5c"],
        ["Run 3", "1,137,585", "1,120,924", "16,661", "877893f7e480a216adcac651a3fb161ca38ee35effd068203b8e8aaf96a5eb5c"]
    ]
    add_styled_table(doc, t2_headers, t2_data, [0.8, 1.2, 1.3, 1.2, 2.3])

    doc.add_heading("4. Task C: Dimensional Schema & Source Data Gotchas", level=1)
    doc.add_paragraph(
        "Gotcha #1: Line Types & The October Revenue Double Warning (2.17x)\n"
        "The vendor files contain 165,704 TENDER rows (bill totals) and 165,704 TAX rows (GST liability). "
        "A naive sum yields INR 122,501,668.06 in October — exactly 2.17x higher than true net revenue (INR 56,359,195.92).\n"
        "Filtering WHERE line_type IN ('SALE', 'RETURN', 'DISCOUNT', 'VOID') completely eliminates double-counting.\n\n"
        "Gotcha #2: Reissued Product Codes (SCD Type 2)\n"
        "24 product codes were retired and reissued to different products in June 2024. Joining on product_code alone corrupts "
        "category allocations. Joining with business_date BETWEEN valid_from AND valid_to guarantees accurate attribution."
    )
    add_image_with_caption(doc, PLOT_C, "Figure 5: Task C Line Types Distribution and October Revenue Inflation Pitfall (2.17x).", Inches(6.0))

    doc.add_heading("5. Task D: SCD Type 2 Historical Price Revisions", level=1)
    doc.add_paragraph(
        "Using PostgreSQL table price_revisions, a single parameterized query returns period-accurate pricing for Britannia Cream Biscuit 60g (P100049):\n"
        "  - March 2024 (2024-03-15): MRP = INR 74.98 | Selling Price = INR 66.95\n"
        "  - August 2024 / Today (2024-08-15): MRP = INR 77.20 | Selling Price = INR 68.93"
    )

    doc.add_heading("6. Task E: Federated Cross-System Query Execution", level=1)
    doc.add_paragraph(
        "DuckDB executes federated queries joining Parquet files from the object store with PostgreSQL master tables "
        "without intermediate copying. EXPLAIN ANALYZE proves PARQUET_SCAN executes at the storage layer with partition pruning, "
        "while dimensions stream from PostgreSQL."
    )

    t3_headers = ["Region", "Category Name", "Total Bills", "Category Revenue (INR)"]
    t3_data = [
        ["South", "Staples & Grains", "2,446", "4,940,102.53"],
        ["South", "Baby Care", "2,263", "4,264,328.55"],
        ["South", "Edible Oils", "2,372", "4,060,432.88"],
        ["West", "Staples & Grains", "1,287", "2,373,386.42"],
        ["North", "Staples & Grains", "1,169", "2,345,071.42"]
    ]
    add_styled_table(doc, t3_headers, t3_data, [1.2, 2.3, 1.3, 2.0])

    doc.add_heading("7. Task F: Full 12-Month Financial Reconciliation", level=1)
    if os.path.exists(RECON_CSV):
        rdf = pd.read_csv(RECON_CSV)
        t4_headers = ["Month", "Pipeline Revenue (INR)", "Finance Signed-Off (INR)", "Variance (INR)", "Status"]
        t4_data = []
        for _, r in rdf.iterrows():
            t4_data.append([
                str(r['month']),
                f"{float(r['pipeline_revenue']):,.2f}",
                f"{float(r['revenue_inr']):,.2f}",
                f"{float(r['variance']):,.2f}",
                str(r['status'])
            ])
        add_styled_table(doc, t4_headers, t4_data, [1.1, 1.8, 1.8, 1.1, 1.2])

    add_image_with_caption(doc, PLOT_F, "Figure 6: Full 12-Month Reconciliation: Pipeline Net Revenue vs Finance Signed-Off Targets.", Inches(6.0))

    doc.add_paragraph(
        "Root Causes for Discrepancy Months & Recommended Finance Actions:\n"
        "1. March 2024 (-₹486,250.00): Revenue Definition (Scope) — Institutional bulk order invoiced outside POS tills. Recommendation: add ERP feed integration.\n"
        "2. July 2024 (-₹232,131.70): Source Data Gap — Hardware failure at Pune store (S07) on July 9-11; phone-in estimate by finance. Recommendation: add store outage journal adjustment table.\n"
        "3. December 2024 (+₹50.48): Revenue Definition (Rounding) — Bill-level integer rounding vs exact decimal summation. Recommendation: standardize on line-item decimals."
    )

    doc.save(DOCX_OUT)
    print(f"DOCX saved to: {DOCX_OUT}")


def build_pdf():
    print("Generating PDF report with embedded screenshots and plots...")
    doc = SimpleDocTemplate(
        PDF_OUT,
        pagesize=letter,
        leftMargin=0.5 * inch,
        rightMargin=0.5 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=17,
        leading=21,
        textColor=colors.HexColor('#1A365D'),
        spaceAfter=3
    )
    sub_style = ParagraphStyle(
        'DocSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor('#4A5568'),
        spaceAfter=8
    )
    h1_style = ParagraphStyle(
        'H1',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=11.5,
        leading=15,
        textColor=colors.HexColor('#1A365D'),
        spaceBefore=8,
        spaceAfter=4
    )
    body_style = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor('#2D3748'),
        spaceAfter=4
    )
    cap_style = ParagraphStyle(
        'Caption',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=7.5,
        leading=9.5,
        alignment=1, # Center
        textColor=colors.HexColor('#718096'),
        spaceBefore=2,
        spaceAfter=6
    )

    story = []
    story.append(Paragraph("Question 1: Annapurna Stores Data Warehouse Platform", title_style))
    story.append(Paragraph("Three Answers to One Question — Implementation & Empirical Defense Report<br/>"
                           "Stack: PostgreSQL 16 · MinIO S3 Object Store · DuckDB Engine | Cold-start: docker compose up --build", sub_style))
    story.append(HRFlowable(width="100%", thickness=1.2, color=colors.HexColor('#1A365D'), spaceAfter=6))

    story.append(Paragraph("1. Executive Summary & Problem Context", h1_style))
    story.append(Paragraph(
        "Annapurna Stores operates 12 supermarkets across India. The CFO discovered that three people reported different "
        "October revenue numbers from the same folder, and biscuit pricing queries returned today's shelf prices. "
        "This platform provides cold-start containerization, SCD Type 2 dimension mapping, non-revenue line type filtering, and federated querying.",
        body_style
    ))

    story.append(Paragraph("2. Task A: Storage Layout & MinIO Object Store Verification", h1_style))
    story.append(Paragraph(
        "Hive-style Parquet layout: <b>s3://annapurna-sales/store_id={store_id}/month={YYYY-MM}/data.parquet</b> (144 partitions).",
        body_style
    ))

    # MinIO Screenshots side-by-side or stacked
    if os.path.exists(SHOT_1):
        story.append(RLImage(SHOT_1, width=3.8 * inch, height=3.9 * inch))
        story.append(Paragraph("<b>Figure 1</b>: MinIO Object Store UI showing annapurna-sales bucket with 144 partitions across 12 stores.", cap_style))

    if os.path.exists(SHOT_2) and os.path.exists(SHOT_3):
        t_shots = RLTable([
            [RLImage(SHOT_2, width=3.2 * inch, height=3.3 * inch),
             RLImage(SHOT_3, width=3.2 * inch, height=3.3 * inch)],
            [Paragraph("<b>Figure 2</b>: Store S01 monthly subpartitions.", cap_style),
             Paragraph("<b>Figure 3</b>: Parquet data file in month=2024-01.", cap_style)]
        ], colWidths=[3.5 * inch, 3.5 * inch])
        t_shots.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(t_shots)

    # Scan Comparison Table & Plot
    t1_data = [
        ["Metric", "Flat CSV Layout", "Partitioned Parquet Layout", "Improvement"],
        ["Files Inspected", "4,457 files", "1 file", "99.98% pruned (4,456 skipped)"],
        ["Bytes Scanned", "68,706,877 bytes (65.5 MB)", "159,723 bytes (156 KB)", "99.77% pruned (68.55 MB saved)"],
        ["I/O Pattern", "O(N) full directory scan", "O(1) direct partition seek", "430x faster byte throughput"]
    ]
    t1 = RLTable(t1_data, colWidths=[1.8 * inch, 1.8 * inch, 1.8 * inch, 1.6 * inch])
    t1.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1A365D')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 7.5),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 3),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F7FAFC')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E0')),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
    ]))
    story.append(t1)

    if os.path.exists(PLOT_A):
        story.append(Spacer(1, 4))
        story.append(RLImage(PLOT_A, width=5.8 * inch, height=2.3 * inch))
        story.append(Paragraph("<b>Figure 4</b>: Task A Scan Efficiency & Pruning Benchmark.", cap_style))

    story.append(Paragraph("3. Task B: Idempotence & Safe Loading (3 Consecutive Runs)", h1_style))
    t2_data = [
        ["Run", "Raw Rows", "Dedup Rows", "Dropped", "Deterministic SHA-256 Checksum"],
        ["Run 1", "1,137,585", "1,120,924", "16,661", "877893f7e480a216adcac651a3fb161ca38ee35effd068203b8e8aaf96a5eb5c"],
        ["Run 2", "1,137,585", "1,120,924", "16,661", "877893f7e480a216adcac651a3fb161ca38ee35effd068203b8e8aaf96a5eb5c"],
        ["Run 3", "1,137,585", "1,120,924", "16,661", "877893f7e480a216adcac651a3fb161ca38ee35effd068203b8e8aaf96a5eb5c"]
    ]
    t2 = RLTable(t2_data, colWidths=[0.7 * inch, 1.0 * inch, 1.0 * inch, 0.9 * inch, 3.4 * inch])
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1A365D')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 7.5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F7FAFC')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E0')),
        ('FONTSIZE', (0, 1), (-1, -1), 6.5),
    ]))
    story.append(t2)

    story.append(Paragraph("4. Task C: Dimensional Schema & Source Gotchas", h1_style))
    story.append(Paragraph(
        "<b>October Double Revenue (2.17x)</b>: 165,704 TENDER rows (bill totals) and 165,704 TAX rows must not be summed in revenue. "
        "Naive sum yields INR 122.50 Cr; net revenue is INR 56.36 Cr.<br/>"
        "<b>Reissued Product Codes</b>: 24 retired codes reissued in June 2024. Handled via SCD Type 2 valid_from/valid_to join.",
        body_style
    ))
    if os.path.exists(PLOT_C):
        story.append(RLImage(PLOT_C, width=6.0 * inch, height=2.4 * inch))
        story.append(Paragraph("<b>Figure 5</b>: Line Types Distribution & The October 2.17x Inflation Warning.", cap_style))

    story.append(Paragraph("5. Task D: March vs August Historical Prices (P100049)", h1_style))
    story.append(Paragraph(
        "Single SQL query executed with :target_date parameter:<br/>"
        "• <b>March 2024 (2024-03-15)</b>: MRP = INR 74.98 | Selling Price = <b>INR 66.95</b><br/>"
        "• <b>August 2024 (2024-08-15)</b>: MRP = INR 77.20 | Selling Price = <b>INR 68.93</b>",
        body_style
    ))

    story.append(Paragraph("6. Task E: Federated Query & Execution Profile", h1_style))
    t3_data = [
        ["Region", "Category Name", "Total Bills", "Category Revenue (INR)"],
        ["South", "Staples & Grains", "2,446", "4,940,102.53"],
        ["South", "Baby Care", "2,263", "4,264,328.55"],
        ["South", "Edible Oils", "2,372", "4,060,432.88"],
        ["West", "Staples & Grains", "1,287", "2,373,386.42"],
        ["North", "Staples & Grains", "1,169", "2,345,071.42"]
    ]
    t3 = RLTable(t3_data, colWidths=[1.4 * inch, 2.1 * inch, 1.2 * inch, 2.3 * inch])
    t3.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1A365D')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 7.5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F7FAFC')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E0')),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
    ]))
    story.append(t3)

    story.append(Paragraph("7. Task F: 12-Month Financial Reconciliation", h1_style))
    if os.path.exists(RECON_CSV):
        rdf = pd.read_csv(RECON_CSV)
        t4_data = [["Month", "Pipeline Net Rev (INR)", "Finance Target (INR)", "Variance (INR)", "Status"]]
        for _, r in rdf.iterrows():
            t4_data.append([
                str(r['month']),
                f"{float(r['pipeline_revenue']):,.2f}",
                f"{float(r['revenue_inr']):,.2f}",
                f"{float(r['variance']):,.2f}",
                str(r['status'])
            ])
        t4 = RLTable(t4_data, colWidths=[1.0 * inch, 1.8 * inch, 1.8 * inch, 1.1 * inch, 1.3 * inch])
        t4.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1A365D')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 7.5),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F7FAFC')]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E0')),
            ('FONTSIZE', (0, 1), (-1, -1), 7),
        ]))
        story.append(t4)

    if os.path.exists(PLOT_F):
        story.append(Spacer(1, 4))
        story.append(RLImage(PLOT_F, width=6.0 * inch, height=2.6 * inch))
        story.append(Paragraph("<b>Figure 6</b>: Full 12-Month Reconciliation: Pipeline vs Signed-Off Finance Targets.", cap_style))

    story.append(Paragraph(
        "<b>Discrepancy Root Causes & Guidance for Finance</b>:<br/>"
        "• <b>March (-₹486,250.00)</b>: Scope Difference — Institutional bulk order invoiced outside POS tills. Recommend ERP feed.<br/>"
        "• <b>July (-₹232,131.70)</b>: Source Data Gap — Pune (S07) hardware outage on July 9-11; booked via phone estimates.<br/>"
        "• <b>December (+₹50.48)</b>: Rounding Convention — Bill-level integer rounding vs exact decimal precision.",
        body_style
    ))

    doc.build(story)
    print(f"PDF saved to: {PDF_OUT}")


if __name__ == "__main__":
    build_docx()
    build_pdf()
