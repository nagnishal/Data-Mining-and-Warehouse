#!/usr/bin/env python3
"""
generate_plots.py
=================
Generates high-resolution analytical visual charts for Question 1:
1. output/A_scan_pruning_comparison.png
2. output/C_line_types_and_october_pitfall.png
3. output/F_monthly_revenue_reconciliation.png
"""

import os
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Set global aesthetic style
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.size'] = 10
plt.rcParams['axes.edgecolor'] = '#CBD5E0'
plt.rcParams['axes.linewidth'] = 0.8


def plot_task_a():
    """Task A: Scan Pruning Comparison (Flat vs Partitioned)"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5), dpi=300)

    categories = ['Flat Folder Layout\n(All Files in 1 Folder)', 'Partitioned Parquet\n(store_id=S01/month=2024-10)']
    
    # 1. File count
    files = [4457, 1]
    bars1 = ax1.bar(categories, files, color=['#E53E3E', '#3182CE'], width=0.55, edgecolor='black', linewidth=0.8)
    ax1.set_title('Files Opened / Inspected\n(Target: Store S01, Oct 2024)', fontsize=11, fontweight='bold', pad=12)
    ax1.set_ylabel('Number of Files (Log Scale)', fontsize=10)
    ax1.set_yscale('log')
    ax1.set_ylim(0.5, 10000)
    
    for bar, val in zip(bars1, files):
        yval = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2.0, yval * 1.3, f"{val:,} file{'s' if val>1 else ''}",
                 ha='center', va='bottom', fontweight='bold', fontsize=10)
    ax1.text(0.5, 0.78, '99.98% Pruning\n(4,456 files skipped)', transform=ax1.transAxes,
             ha='center', bbox=dict(boxstyle='round,pad=0.5', facecolor='#EBF8FF', edgecolor='#3182CE'))

    # 2. Bytes scanned
    mbytes = [65.52, 0.156]
    bars2 = ax2.bar(categories, mbytes, color=['#E53E3E', '#38A169'], width=0.55, edgecolor='black', linewidth=0.8)
    ax2.set_title('Total Bytes Scanned (MB)\n(Target: Store S01, Oct 2024)', fontsize=11, fontweight='bold', pad=12)
    ax2.set_ylabel('Data Volume Scanned (MB)', fontsize=10)
    ax2.set_ylim(0, 75)
    
    for bar, val in zip(bars2, mbytes):
        yval = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2.0, yval + 1.8, f"{val:.2f} MB",
                 ha='center', va='bottom', fontweight='bold', fontsize=10)
    ax2.text(0.5, 0.78, '99.77% Data Saved\n(430x Byte Throughput)', transform=ax2.transAxes,
             ha='center', bbox=dict(boxstyle='round,pad=0.5', facecolor='#F0FFF4', edgecolor='#38A169'))

    plt.tight_layout()
    out_path = os.path.join(OUTPUT_DIR, "A_scan_pruning_comparison.png")
    plt.savefig(out_path)
    plt.close()
    print(f"Saved: {out_path}")


def plot_task_c():
    """Task C: Line Type Breakdown & October Revenue Warning (2.17x)"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5), dpi=300)

    # 1. Line Type Row Counts
    line_types = ['SALE', 'TENDER\n(Bill Total)', 'TAX\n(GST)', 'DISCOUNT', 'RETURN', 'VOID']
    counts = [745860, 165704, 165704, 22603, 16161, 4892]
    colors_list = ['#3182CE', '#E53E3E', '#ED8936', '#805AD5', '#D69E2E', '#718096']
    
    bars1 = ax1.bar(line_types, counts, color=colors_list, edgecolor='black', linewidth=0.7)
    ax1.set_title('Line Types Distribution Across 1.12M Rows\n(Red/Orange = Non-Revenue Accounting Lines)', fontsize=11, fontweight='bold', pad=10)
    ax1.set_ylabel('Record Count', fontsize=10)
    for bar, val in zip(bars1, counts):
        ax1.text(bar.get_x() + bar.get_width()/2.0, val + 15000, f"{val:,}",
                 ha='center', va='bottom', fontsize=8.5, fontweight='bold')
    ax1.set_ylim(0, 850000)

    # 2. October Revenue: Naive vs Correct
    oct_scenarios = ['Naive Sum\n(All lines including TENDER & TAX)', 'Correct Net Revenue\n(SALE + RETURN + DISCOUNT + VOID)']
    oct_values = [122.50, 56.36]
    bars2 = ax2.bar(oct_scenarios, oct_values, color=['#E53E3E', '#38A169'], width=0.5, edgecolor='black', linewidth=0.8)
    ax2.set_title('October Revenue Gotcha: The 2.17x Warning\n(TENDER lines double-count bill totals)', fontsize=11, fontweight='bold', pad=10)
    ax2.set_ylabel('Revenue in Crores (₹ Cr)', fontsize=10)
    ax2.set_ylim(0, 145)
    
    for bar, val in zip(bars2, oct_values):
        ax2.text(bar.get_x() + bar.get_width()/2.0, val + 3.0, f"₹{val:.2f} Cr\n(₹{val*10000000:,.0f})",
                 ha='center', va='bottom', fontsize=9.5, fontweight='bold')
    ax2.text(0.5, 0.75, '2.17x False Inflation!\nFilter: WHERE line_type IN\n(\'SALE\',\'RETURN\',\'DISCOUNT\',\'VOID\')',
             transform=ax2.transAxes, ha='center', bbox=dict(boxstyle='round,pad=0.5', facecolor='#FFF5F5', edgecolor='#E53E3E'))

    plt.tight_layout()
    out_path = os.path.join(OUTPUT_DIR, "C_line_types_and_october_pitfall.png")
    plt.savefig(out_path)
    plt.close()
    print(f"Saved: {out_path}")


def plot_task_f():
    """Task F: 12-Month Financial Reconciliation"""
    recon_csv = os.path.join(OUTPUT_DIR, 'monthly_reconciliation.csv')
    if not os.path.exists(recon_csv):
        return

    df = pd.read_csv(recon_csv)
    fig, ax = plt.subplots(figsize=(12, 5.5), dpi=300)

    months = df['month'].tolist()
    pipeline_rev = (df['pipeline_revenue'] / 1e7).tolist()  # Crores
    finance_rev = (df['revenue_inr'] / 1e7).tolist()

    x = np.arange(len(months))
    width = 0.35

    rects1 = ax.bar(x - width/2, pipeline_rev, width, label='Pipeline Net Revenue (POS Lake)', color='#3182CE', edgecolor='black', linewidth=0.6)
    rects2 = ax.bar(x + width/2, finance_rev, width, label='Finance Signed-Off (finance_monthly.csv)', color='#48BB78', edgecolor='black', linewidth=0.6)

    ax.set_title('Full 12-Month Financial Reconciliation: Pipeline vs Signed-Off Finance Targets\n(9 Months Exact Match · 3 Discrepancy Months Fully Defended)',
                 fontsize=12, fontweight='bold', pad=15)
    ax.set_xlabel('Month (Calendar Year 2024)', fontsize=10, labelpad=8)
    ax.set_ylabel('Revenue in Crores (₹ Cr)', fontsize=10)
    ax.set_xticks(x)
    ax.set_xticklabels(months, rotation=35, ha='right', fontsize=9)
    ax.set_ylim(0, 6.8)
    ax.legend(loc='upper left', frameon=True, facecolor='white', framealpha=0.95)

    # Annotate Discrepancies
    # March (index 2): -4.86 Lakhs
    ax.annotate('March: -₹4.86L\n(Institutional Bulk Order\noutside POS till)',
                xy=(2, pipeline_rev[2]), xytext=(1.8, 5.8),
                arrowprops=dict(facecolor='#E53E3E', shrink=0.08, width=1.5, headwidth=6),
                bbox=dict(boxstyle='round,pad=0.3', facecolor='#FFF5F5', edgecolor='#E53E3E'),
                fontsize=8, ha='center')

    # July (index 6): -2.32 Lakhs
    ax.annotate('July: -₹2.32L\n(Pune S07 Outage July 9-11;\nFinance used phone estimate)',
                xy=(6, pipeline_rev[6]), xytext=(5.9, 5.4),
                arrowprops=dict(facecolor='#DD6B20', shrink=0.08, width=1.5, headwidth=6),
                bbox=dict(boxstyle='round,pad=0.3', facecolor='#FFFAF0', edgecolor='#DD6B20'),
                fontsize=8, ha='center')

    # Dec (index 11): +₹50.48
    ax.annotate('Dec: +₹50.48\n(Rupee Rounding)',
                xy=(11, pipeline_rev[11]), xytext=(10.7, 6.1),
                arrowprops=dict(facecolor='#3182CE', shrink=0.08, width=1.5, headwidth=6),
                bbox=dict(boxstyle='round,pad=0.3', facecolor='#EBF8FF', edgecolor='#3182CE'),
                fontsize=8, ha='center')

    plt.tight_layout()
    out_path = os.path.join(OUTPUT_DIR, "F_monthly_revenue_reconciliation.png")
    plt.savefig(out_path)
    plt.close()
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    plot_task_a()
    plot_task_c()
    plot_task_f()
