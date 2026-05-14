"""
01_ingest_patient_admissions.py
--------------------------------
Reads the raw patient admissions dataset, applies basic cleaning, and saves a processed version that is ready for SQL Server loading
and Power BI analysis.

Input  : data/raw/healthcare_dataset.csv
Output : data/processed/admissions_clean.csv
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd


#! ─────────────────────────────────────────────────────────────
#! Paths
#! ─────────────────────────────────────────────────────────────
# I use pathlib instead of plain strings because it handles file paths in a cleaner and more readable way.
#
# These paths are written relative to the project root.
# 

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")

RAW_FILE = RAW_DIR / "healthcare_dataset.csv"
OUTPUT_FILE = PROCESSED_DIR / "admissions_clean.csv"

# Create the processed folder if it does not already exist.
# This prevents an error when saving the cleaned CSV later.
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


#! ─────────────────────────────────────────────────────────────
#! Logging
#! ─────────────────────────────────────────────────────────────
# Logging is better than using only print statements because it gives a timestamp and message level, which makes the script easier to debug when the project becomes larger.

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)

log = logging.getLogger(__name__)

log.info("Script started")


#! ─────────────────────────────────────────────────────────────
#! Load raw patient admissions data
#! ─────────────────────────────────────────────────────────────
# In this step, I read the original CSV file from the raw data folder.
# I also save the original row count so I can validate later that the cleaning process did not accidentally remove or duplicate records.

src = RAW_DIR / "healthcare_dataset.csv"

log.info(f"Reading raw file: {src}")

# Stop the script early with a clear message if the file is missing.
# This is better than letting pandas throw a longer, less friendly error.
if not src.exists():
    raise FileNotFoundError(
        f"Raw file not found: {src}. "
        "Please place healthcare_dataset.csv inside the data/raw folder."
    )
df = pd.read_csv(src)

# Store the number of rows before cleaning. This is useful for a final quality check after all transformations.
raw_row_count = len(df)

log.info(f"Loaded {raw_row_count:,} rows x {df.shape[1]} columns")

#! ─────────────────────────────────────────────────────────────
#! Normalize column names
#! ─────────────────────────────────────────────────────────────
# The raw dataset has column names with spaces and capital letters,such as "Date of Admission" and "Billing Amount".
#
# I will use clean snake_case column names which This step makes the column names consistent and easier to reference later.

df.columns = (
    df.columns
    .str.strip()                              
    .str.lower()                              
    .str.replace(" ", "_", regex=False)       
    .str.replace(r"[^a-z0-9_]", "", regex=True)  
)

log.info(f"Columns normalized: {df.columns.tolist()}")

#! ─────────────────────────────────────────────────────────────
#! Fix inconsistent patient name casing
#! ─────────────────────────────────────────────────────────────
# In the raw dataset, some patient names have inconsistent capitalization,such as "Bobby JacksOn" or "DaNnY sMitH".
#
# This step standardizes the names into title case so the values look cleaner and more consistent in reports or validation checks.

df["name"] = df["name"].str.strip().str.title()

log.info(f"Sample names after fix: {df['name'].head(3).tolist()}")

#! ─────────────────────────────────────────────────────────────
#! Parse date columns
#! ─────────────────────────────────────────────────────────────
# The raw dataset stores date fields as text.
# I convert them to real datetime values so pandas can understand them as dates.
#
#
# errors="coerce" means:
#   If pandas finds an invalid date, it will convert it to NaT instead of crashing the script.
#

df["date_of_admission"] = pd.to_datetime(
    df["date_of_admission"],
    errors="coerce"
)

df["discharge_date"] = pd.to_datetime(
    df["discharge_date"],
    errors="coerce"
)

# Count how many missing/invalid dates exist after conversion.
null_admissions = df["date_of_admission"].isna().sum()
null_discharges = df["discharge_date"].isna().sum()

log.info(
    f"Date parsing complete - nulls created: "
    f"admissions={null_admissions}, discharges={null_discharges}"
)

#! ─────────────────────────────────────────────────────────────
#! Derive length of stay
#! ─────────────────────────────────────────────────────────────
# Length of stay is one of the most important healthcare metrics.
# It shows how many days a patient stayed in the hospital.
#
# I calculate it by subtracting the admission date from the discharge date.


df["length_of_stay_days"] = (
    df["discharge_date"] - df["date_of_admission"]
).dt.days


# Check for impossible records.
# A negative length of stay means the discharge date happened before admission,which is a data quality issue.
#
# I use < 0 instead of <= 0 because same-day discharge can be valid in healthcare.
invalid_los = df["length_of_stay_days"] < 0

n_invalid = invalid_los.sum()

log.info(f"Length of stay calculated - invalid rows (LOS < 0): {n_invalid}")


# Drop only records with impossible date logic.
#
if n_invalid > 0:
    log.warning(
        f"Dropping {n_invalid} rows where discharge date is before admission date"
    )
    df = df[~invalid_los].copy()

#* ─────────────────────────────────────────────────────────────
#* Derive age groups
#* ─────────────────────────────────────────────────────────────

def assign_age_group(age) -> str:
    """
    Map a patient age to a reporting age group.
    Invalid or missing ages are labelled as Unknown.
    """

    if pd.isna(age):
        return "Unknown"

    if age < 0:
        return "Unknown"
    elif age < 18:
        return "0-17"
    elif age < 35:
        return "18-34"
    elif age < 55:
        return "35-54"
    elif age < 75:
        return "55-74"
    else:
        return "75+"


df["age_group"] = df["age"].apply(assign_age_group)

log.info(
    f"Age group distribution:\n"
    f"{df['age_group'].value_counts().sort_index()}"
)

#* ─────────────────────────────────────────────────────────────
#* Standardize categorical columns
#* ─────────────────────────────────────────────────────────────

cat_cols = [
    "gender",
    "blood_type",
    "medical_condition",
    "insurance_provider",
    "admission_type",
    "medication",
    "test_results"
]

missing_cat_cols = [col for col in cat_cols if col not in df.columns]

if missing_cat_cols:
    raise KeyError(f"Missing expected categorical columns: {missing_cat_cols}")

for col in cat_cols:
    df[col] = df[col].astype(str).str.strip().str.title()


#* ─────────────────────────────────────────────────────────────
#* Round billing amount
#* ─────────────────────────────────────────────────────────────

df["billing_amount"] = df["billing_amount"].round(2)

log.info("Categorical columns standardized and billing amount rounded")
# ── Validate billing amount ────────────────────────────────────
# after testing i found that 108 rows have negative billing amounts in the raw data.
# Negative billing is not physically meaningful for this dataset.
# i drop these rows and log them for transparency.

invalid_billing = df["billing_amount"] < 0
n_invalid_billing = invalid_billing.sum()

if n_invalid_billing > 0:
    log.warning(
        f"Dropping {n_invalid_billing} rows with negative billing_amount "
        f"(min value: ${df.loc[invalid_billing, 'billing_amount'].min():,.2f})"
    )
    df = df[~invalid_billing].copy()

#* ─────────────────────────────────────────────────────────────
#* Add surrogate key
#* ─────────────────────────────────────────────────────────────
# The raw admissions dataset does not have a dedicated admission ID.
# I create one here so every row has a simple unique identifier.
#
#
# I reset the index first to make sure the IDs are continuous after any rows were removed during cleaning.

df = df.reset_index(drop=True)

# Insert admission_id as the first column.
# df.index starts at 0, so I add 1 to make the IDs start at 1.
df.insert(0, "admission_id", df.index + 1)

log.info(
    f"Surrogate key added - admission_id range: "
    f"1 to {df['admission_id'].max()}"
)

#* ─────────────────────────────────────────────────────────────
#* Quality report
#* ─────────────────────────────────────────────────────────────
# This final report helps me quickly validate the cleaning process.
#
# I compare the row count before and after cleaning to make sure I know whether any records were removed.
#
# I also log a few important business checks:
#   - date range of admissions
#   - average billing amount
#   - average length of stay
#   - any remaining null values
#


log.info("=== QUALITY REPORT ===")

# Original number of rows loaded from the raw CSV.
log.info(f"Rows in  : {raw_row_count:,}")

# Number of rows remaining after cleaning.
log.info(f"Rows out : {len(df):,}")

# Number of rows removed during cleaning.
log.info(f"Dropped  : {raw_row_count - len(df):,}")

# Shows the earliest and latest admission dates in the cleaned dataset.
log.info(
    f"Date range: "
    f"{df['date_of_admission'].min().date()} "
    f"to {df['date_of_admission'].max().date()}"
)

# Average billing amount, formatted as currency.
log.info(f"Avg billing amount : ${df['billing_amount'].mean():,.2f}")

# Average hospital stay length, rounded to 1 decimal place.
log.info(f"Avg length of stay : {df['length_of_stay_days'].mean():.1f} days")

# Show only columns that still have missing values.
remaining_nulls = df.isnull().sum()
remaining_nulls = remaining_nulls[remaining_nulls > 0]

log.info(f"Remaining nulls    :\n{remaining_nulls}")

#* ─────────────────────────────────────────────────────────────
#* Save cleaned output
#* ─────────────────────────────────────────────────────────────

out_path = PROCESSED_DIR / "admissions_clean.csv"

df.to_csv(out_path, index=False)

if out_path.exists():
    log.info(f"Saved cleaned file to: {out_path}")
else:
    raise FileNotFoundError(f"Output file was not created: {out_path}")

log.info("Script complete")