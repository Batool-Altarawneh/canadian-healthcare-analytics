"""
03_ingest_cihi_wait_times.py
-----------------------------
Reads the real CIHI provincial wait-times Excel file,cleans it, and saves a processed version ready for SQL Server loading and Power BI analysis.

Input  : data/raw/wait-times-priority-procedures-in-canada-2025-data-tables-en.xlsx
Output : data/processed/cihi_wait_times_clean.csv
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd


#! ─────────────────────────────────────────────────────────────
#! Paths
#! ─────────────────────────────────────────────────────────────

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")

RAW_FILE = RAW_DIR / "wait-times-priority-procedures-in-canada-2025-data-tables-en.xlsx"
OUTPUT_FILE = PROCESSED_DIR / "cihi_wait_times_clean.csv"


PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


#! ─────────────────────────────────────────────────────────────
#! Logging
#! ─────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)

log = logging.getLogger(__name__)

log.info("Script started")

#! ─────────────────────────────────────────────────────────────
#! Load raw CIHI wait-times data
#! ─────────────────────────────────────────────────────────────
# The CIHI source file is an Excel workbook, not a CSV file.
# In the Excel sheet, row 0 contains a title or merged header.
# The actual column names start on row 1, so I use header=1.


src = RAW_DIR / "wait-times-priority-procedures-in-canada-2025-data-tables-en.xlsx"

log.info(f"Reading raw file: {src}")


if not src.exists():
    raise FileNotFoundError(
        f"Raw file not found: {src}. "
        "Please place the CIHI Excel file inside the data/raw folder."
    )

df = pd.read_excel(
    src,
    sheet_name="Table 1",
    header=1
)

raw_row_count = len(df)

log.info(f"Loaded {raw_row_count:,} rows x {df.shape[1]} columns")
log.info(f"Raw columns: {df.columns.tolist()}")

#! ─────────────────────────────────────────────────────────────
#! Drop empty trailing columns
#! ─────────────────────────────────────────────────────────────
# The CIHI Excel file includes extra trailing columns after the actual data.
# These usually come from Excel formatting or blank note columns.
#
# I keep only the columns needed for wait-time analysis.

cols_to_keep = [
    "Reporting level",
    "Province",
    "Region",
    "Indicator",
    "Metric",
    "Data year",
    "Unit of measurement",
    "Indicator result",
]

missing_cols = [col for col in cols_to_keep if col not in df.columns]

if missing_cols:
    raise KeyError(f"Missing expected CIHI columns: {missing_cols}")

df = df[cols_to_keep].copy()

log.info(f"Kept {len(cols_to_keep)} columns, dropped trailing empty columns")

#! ─────────────────────────────────────────────────────────────
#! Normalize column names
#! ─────────────────────────────────────────────────────────────

df.columns = (
    df.columns
    .str.strip()                                
    .str.lower()                                
    .str.replace(" ", "_", regex=False)         
    .str.replace(r"[^a-z0-9_]", "", regex=True) 
)

log.info(f"Columns normalized: {df.columns.tolist()}")

#! ─────────────────────────────────────────────────────────────
#! Filter to clean calendar years only
#! ─────────────────────────────────────────────────────────────
# The CIHI data_year column contains mixed reporting periods:
#
#   - Calendar years : 2008, 2009, ..., 2024
#   - Fiscal years   : 2019FY, 2020FY
#   - Partial periods: 2019Q3Q4, 2020Q3Q4
#
# For this project, I keep only full calendar years.
# This makes trend analysis cleaner and avoids mixing full-year results with partial-year or fiscal-year reporting periods.

before_filter = len(df)

# Convert data_year to string first because the column contains mixed types.

df["data_year"] = df["data_year"].astype(str).str.strip()

# Keep only values that are exactly 4 digits.

df = df[df["data_year"].str.match(r"^\d{4}$")].copy()

# After filtering, all remaining values are clean years, so it is safe to convert the column to integer.
df["data_year"] = df["data_year"].astype(int)

after_filter = len(df)

log.info(
    f"Year filter: kept {after_filter:,} rows, "
    f"dropped {before_filter - after_filter:,} non-calendar-year rows"
)

log.info(f"Year range: {df['data_year'].min()} to {df['data_year'].max()}")
log.info(f"Unique years: {sorted(df['data_year'].unique())}")

#! ─────────────────────────────────────────────────────────────
#! Handle suppressed indicator results
#! ─────────────────────────────────────────────────────────────
# CIHI uses non-numeric markers such as "n/a" when a result is not available, not reported, or suppressed.
#
# Since indicator_result is the main numeric value in this dataset, I convert these markers to NaN before casting the column to a numeric type.

missing_markers = ["n/a", "N/A", "NA", "na", "--", ".", ""]

df["indicator_result"] = df["indicator_result"].replace(missing_markers, np.nan)

df["indicator_result"] = pd.to_numeric(
    df["indicator_result"],
    errors="coerce"
)

null_count = df["indicator_result"].isna().sum()
total = len(df)

log.info(
    f"Suppressed or missing values: {null_count:,} nulls in indicator_result "
    f"({null_count / total * 100:.1f}%)"
)

#! ─────────────────────────────────────────────────────────────
#! Clean remaining text columns
#! ─────────────────────────────────────────────────────────────
# This step standardizes text fields after the main numeric cleaning.
#
# I clean spaces first, then apply controlled formatting.
# This is safer than applying .str.title() to every column because some healthcare terms contain acronyms such as CABG, CT, and MRI.

text_cols = [
    "reporting_level",
    "province",
    "indicator",
    "metric",
    "unit_of_measurement",
]

for col in text_cols:
    df[col] = df[col].astype(str).str.strip()


# Reporting level and province are safe to title-case.
df["reporting_level"] = df["reporting_level"].str.title()
df["province"] = df["province"].str.title()


# Region is often missing for provincial-level rows.
# I fill missing region values with "Provincial" to make the level clear.
df["region"] = (
    df["region"]
    .fillna("Provincial")
    .astype(str)
    .str.strip()
    .str.title()
)


# Indicator contains procedure names and medical acronyms.
# I use title case for readability, then restore known acronyms.
df["indicator"] = df["indicator"].str.title()

indicator_fixes = {
    "Cabg": "CABG",
    "Ct Scan": "CT Scan",
    "Mri Scan": "MRI Scan",
}

df["indicator"] = df["indicator"].replace(indicator_fixes)


# Metric values need controlled labels because .str.title()
# would turn "90th Percentile" into "90Th Percentile".
metric_fixes = {
    "50th percentile": "50th Percentile",
    "90th percentile": "90th Percentile",
    "volume": "Volume",
    "% meeting benchmark": "% Meeting Benchmark",
}

df["metric"] = (
    df["metric"]
    .str.lower()
    .map(metric_fixes)
    .fillna(df["metric"])
)


# Unit labels are standardized for clearer reporting.
unit_fixes = {
    "days": "Days",
    "number of cases": "Number of cases",
    "percent": "Percent",
    "%": "Percent",
}

df["unit_of_measurement"] = (
    df["unit_of_measurement"]
    .str.lower()
    .map(unit_fixes)
    .fillna(df["unit_of_measurement"])
)


log.info(f"Provinces  : {sorted(df['province'].unique())}")
log.info(f"Indicators : {sorted(df['indicator'].unique())}")
log.info(f"Metrics    : {sorted(df['metric'].unique())}")

#! ─────────────────────────────────────────────────────────────
#! Add surrogate key
#! ─────────────────────────────────────────────────────────────
df = df.reset_index(drop=True)
df.insert(0, "wait_time_id", df.index + 1)

log.info(
    f"Surrogate key added — wait_time_id range: "
    f"1 to {df['wait_time_id'].max()}"
)


#! ─────────────────────────────────────────────────────────────
#! Quality report
#! ─────────────────────────────────────────────────────────────

null_results = df["indicator_result"].isna().sum()
null_results_pct = df["indicator_result"].isna().mean() * 100

log.info("=== QUALITY REPORT ===")
log.info(f"Rows in  : {raw_row_count:,}")
log.info(f"Rows out : {len(df):,}")
log.info(f"Dropped  : {raw_row_count - len(df):,}")
log.info(f"Year range    : {df['data_year'].min()} to {df['data_year'].max()}")
log.info(f"Provinces     : {df['province'].nunique()} unique")
log.info(f"Indicators    : {df['indicator'].nunique()} unique")
log.info(f"Null results  : {null_results:,} ({null_results_pct:.1f}%)")


#! ─────────────────────────────────────────────────────────────
#! Save cleaned output
#! ─────────────────────────────────────────────────────────────

out_path = PROCESSED_DIR / "cihi_wait_times_clean.csv"

df.to_csv(out_path, index=False)

if out_path.exists():
    log.info(f"Saved cleaned file to: {out_path}")
else:
    raise FileNotFoundError(f"Output file was not created: {out_path}")

log.info("Script complete")