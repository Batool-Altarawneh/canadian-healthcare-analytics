"""
02_ingest_er_wait_times.py
---------------------------
Reads the raw ER wait-time dataset, applies basic cleaning,and saves a processed version ready for SQL Server loading and Power BI analysis.

Input  : data/raw/ER Wait Time Dataset.csv
Output : data/processed/er_visits_clean.csv
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

RAW_FILE = RAW_DIR / "ER Wait Time Dataset.csv"
OUTPUT_FILE = PROCESSED_DIR / "er_visits_clean.csv"


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
#! Load raw ER wait-time data
#! ─────────────────────────────────────────────────────────────

src = RAW_DIR / "ER Wait Time Dataset.csv"

log.info(f"Reading raw file: {src}")


if not src.exists():
    raise FileNotFoundError(
        f"Raw file not found: {src}. "
        "Please place ER Wait Time Dataset.csv inside the data/raw folder."
    )

df = pd.read_csv(src)

raw_row_count = len(df)

log.info(f"Loaded {raw_row_count:,} rows x {df.shape[1]} columns")


#! ─────────────────────────────────────────────────────────────
#! Rename columns to clean snake_case
#! ─────────────────────────────────────────────────────────────


rename_map = {
    "Visit ID": "visit_id",
    "Patient ID": "patient_id",
    "Hospital ID": "hospital_id",
    "Hospital Name": "hospital_name",
    "Region": "region",
    "Visit Date": "visit_datetime",
    "Day of Week": "day_of_week",
    "Season": "season",
    "Time of Day": "time_of_day",
    "Urgency Level": "urgency_level",
    "Nurse-to-Patient Ratio": "nurse_patient_ratio",
    "Specialist Availability": "specialist_count",
    "Facility Size (Beds)": "facility_beds",
    "Time to Registration (min)": "time_to_registration_min",
    "Time to Triage (min)": "time_to_triage_min",
    "Time to Medical Professional (min)": "time_to_doctor_min",
    "Total Wait Time (min)": "total_wait_time_min",
    "Patient Outcome": "patient_outcome",
    "Patient Satisfaction": "patient_satisfaction",
}

df = df.rename(columns=rename_map)

log.info(f"Columns renamed: {df.columns.tolist()}")

#! ─────────────────────────────────────────────────────────────
#! Parse visit datetime
#! ─────────────────────────────────────────────────────────────
df["visit_datetime"] = pd.to_datetime(
    df["visit_datetime"],
    errors="coerce"
)


null_dates = df["visit_datetime"].isna().sum()

log.info(f"Datetime parsing complete - nulls created: {null_dates}")



if null_dates > 0:
    log.warning(f"Dropping {null_dates} rows with unparseable dates")
    df = df[df["visit_datetime"].notna()].copy()


#! ─────────────────────────────────────────────────────────────
#! Extract date components
#! ─────────────────────────────────────────────────────────────
# visit_date  : calendar date only
# visit_year  : year of the ER visit
# visit_month : month number
# visit_hour  : hour of day, for peak-time analysis

df["visit_date"] = df["visit_datetime"].dt.date
df["visit_year"] = df["visit_datetime"].dt.year
df["visit_month"] = df["visit_datetime"].dt.month
df["visit_hour"] = df["visit_datetime"].dt.hour

log.info("Date components extracted")

log.info(
    f"Date range: {df['visit_date'].min()} to {df['visit_date'].max()}"
)

log.info(
    f"Years in data: {sorted(df['visit_year'].unique())}"
)

#! ─────────────────────────────────────────────────────────────
#! Validate wait-time columns
#! ─────────────────────────────────────────────────────────────

wait_cols = [
    "time_to_registration_min",
    "time_to_triage_min",
    "time_to_doctor_min",
    "total_wait_time_min",
]

for col in wait_cols:
    # Count how many rows have a negative value in this wait-time column.
    neg = (df[col] < 0).sum()

    if neg:
        log.warning(f"{neg} negative values in {col} — setting to NaN")

        # Replace negative wait times with NaN.
        df.loc[df[col] < 0, col] = np.nan

    else:
        log.info(f"{col}: no negative values")

# Log a quick summary of wait-time columns after validation.
log.info("Wait-time summary after validation:")
log.info(f"\n{df[wait_cols].describe()}")


# ─────────────────────────────────────────────────────────────
# Standardize categorical columns
# ─────────────────────────────────────────────────────────────
# I clean the main text/category columns before creating benchmark flags.
# This is important because benchmark_met depends on urgency_level values
# matching the CTAS_BENCHMARKS dictionary exactly.

cat_cols = [
    "region",
    "day_of_week",
    "season",
    "time_of_day",
    "urgency_level",
    "patient_outcome",
]

for col in cat_cols:
    df[col] = df[col].str.strip().str.title()

log.info("Categorical columns standardized")


# ─────────────────────────────────────────────────────────────
# Derive wait-time category
# ─────────────────────────────────────────────────────────────
# These are project-level reporting labels, not official CTAS categories.
# They describe the full patient wait experience using total_wait_time_min.

def wait_category(minutes: float) -> str:
    """
    Bucket total ER wait time into simple reporting categories.

    Parameters:
        minutes: Total ER wait time in minutes.

    Returns:
        A readable wait-time category for reporting.
    """

    if pd.isna(minutes):
        return "Unknown"
    elif minutes <= 30:
        return "Fast (<=30 min)"
    elif minutes <= 120:
        return "Moderate (31-120 min)"
    elif minutes <= 240:
        return "Slow (121-240 min)"
    else:
        return "Critical (>240 min)"


df["wait_time_category"] = df["total_wait_time_min"].apply(wait_category)

log.info(
    f"Wait time categories:\n"
    f"{df['wait_time_category'].value_counts()}"
)


#! ─────────────────────────────────────────────────────────────
#! Derive benchmark-met flag
#! ─────────────────────────────────────────────────────────────
# Canadian Triage and Acuity Scale (CTAS) National Guidelines
# Source: https://pub-haldimandcounty.escribemeetings.com/filestream.ashx?DocumentId=3293
#
# Benchmark = time to physician initial assessment.
#
# I use time_to_doctor_min, not total_wait_time_min, because CTAS-style benchmarks measure time to first physician contact rather than the full patient wait experience.

# 4-level mapping:
#   Critical : CTAS I   : 0  min / immediate
#   High     : CTAS II  : 15 min
#   Medium   : CTAS III : 30 min
#   Low      : CTAS IV  : 60 min
#
# Note:
# Critical benchmark_met may be near 0% by design because the benchmark is immediate, and this dataset records wait time in whole minutes.

CTAS_BENCHMARKS = {
    "Critical": 0,
    "High": 15,
    "Medium": 30,
    "Low": 60,
}


def benchmark_met(row: pd.Series) -> bool:
    """
    Return True if the patient was seen by a medical professional within the CTAS-style benchmark for their urgency level.

    Parameters:
        row: One ER visit record from the DataFrame.

    Returns:
        True if time_to_doctor_min is within the urgency-level benchmark.
        False if urgency level is unrecognized or doctor wait time is missing.
    """

    threshold = CTAS_BENCHMARKS.get(row["urgency_level"])

    if threshold is None or pd.isna(row["time_to_doctor_min"]):
        return False

    return row["time_to_doctor_min"] <= threshold


df["benchmark_met"] = df.apply(benchmark_met, axis=1)

log.info(
    f"Benchmark met: {df['benchmark_met'].sum():,} of {len(df):,} "
    f"({df['benchmark_met'].mean() * 100:.1f}%)"
)


#! ─────────────────────────────────────────────────────────────
#! Quality report
#! ─────────────────────────────────────────────────────────────

log.info("=== QUALITY REPORT ===")
log.info(f"Rows in  : {raw_row_count:,}")
log.info(f"Rows out : {len(df):,}")
log.info(f"Dropped  : {raw_row_count - len(df):,}")
log.info(f"Avg total wait time : {df['total_wait_time_min'].mean():.1f} min")
log.info(f"Avg time to doctor  : {df['time_to_doctor_min'].mean():.1f} min")

remaining_nulls = df.isnull().sum()
remaining_nulls = remaining_nulls[remaining_nulls > 0]

if remaining_nulls.empty:
    log.info("Remaining nulls     : 0")
else:
    log.info(f"Remaining nulls     :\n{remaining_nulls}")


#! ─────────────────────────────────────────────────────────────
#! Save cleaned output
#! ─────────────────────────────────────────────────────────────

out_path = PROCESSED_DIR / "er_visits_clean.csv"

df.to_csv(out_path, index=False)

if out_path.exists():
    log.info(f"Saved cleaned file to: {out_path}")
else:
    raise FileNotFoundError(f"Output file was not created: {out_path}")

log.info("Script complete")