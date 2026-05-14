"""
04_load_to_sql_server.py
------------------------

Loads the cleaned healthcare CSV files into the SQL Server star schema.

This script should be run after the ingestion scripts finish and the clean CSV files are available inside data/processed.

Loading order matters:
    1. Dimension tables first
       These tables do not depend on other tables.

    2. Fact tables second
       These tables contain foreign keys that reference the dimensions.

Input files:
    data/processed/admissions_clean.csv
    data/processed/er_visits_clean.csv
    data/processed/cihi_wait_times_clean.csv

Output:
    Populated star schema tables inside the HealthcareAnalytics database.
"""

import logging
import os

from pathlib import Path
from urllib.parse import quote_plus

import numpy as np
import pandas as pd
from dotenv import load_dotenv

from sqlalchemy import create_engine, text


#! ─────────────────────────────────────────────────────────────
#! Paths
#! ─────────────────────────────────────────────────────────────

PROCESSED_DIR = Path("data/processed")

load_dotenv()

#!─────────────────────────────────────────────────────────────
#!Logging
#!─────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)

log = logging.getLogger(__name__)


#!─────────────────────────────────────────────────────────────
#!Database connection settings
#!────────────────────────────────────────────────────────────

# Local SQL Server Express instance.
SQL_SERVER = os.getenv("SQL_SERVER")
SQL_DATABASE = os.getenv("SQL_DATABASE")
SQL_DRIVER = os.getenv("SQL_DRIVER", "ODBC Driver 17 for SQL Server")
SQL_TRUSTED_CONNECTION = os.getenv("SQL_TRUSTED_CONNECTION", "yes")

# SQLAlchemy connection string using pyodbc and Windows Authentication.
# trusted_connection=yes means SQL Server uses the current Windows user, so no username or password is needed for the local setup.
def build_connection_string() -> str:
    """
    Build the SQLAlchemy connection string from .env settings.

    quote_plus is used because the driver name contains spaces, for example: ODBC Driver 17 for SQL Server.
    """

    if not SQL_SERVER or not SQL_DATABASE:
        raise ValueError(
            "Missing SQL_SERVER or SQL_DATABASE in .env file. "
            "Please check your .env settings."
        )

    driver_encoded = quote_plus(SQL_DRIVER)

    connection_string = (
        f"mssql+pyodbc://{SQL_SERVER}/{SQL_DATABASE}"
        f"?driver={driver_encoded}"
        f"&trusted_connection={SQL_TRUSTED_CONNECTION}"
    )

    return connection_string


def get_engine():
    """
    Create and return a SQLAlchemy engine for SQL Server.
    """
    connection_string = build_connection_string()
    return create_engine(connection_string, fast_executemany=True)


def test_connection(engine) -> None:
    """
    Confirm that Python can connect to SQL Server before loading data.
    """
    log.info("Connecting to SQL Server...")

    with engine.connect() as conn:
        result = conn.execute(text("SELECT @@VERSION"))
        version = result.fetchone()[0]

    log.info("Connected successfully")
    log.info(f"SQL Server version: {version[:50]}...")

#! ─────────────────────────────────────────────────────────────
#! Generic table loader
#! ─────────────────────────────────────────────────────────────

def load_table(
    engine,
    df: pd.DataFrame,
    table_name: str,
    if_exists: str = "append",
    chunksize: int = 1000
) -> None:
    """
    Load a pandas DataFrame into an existing SQL Server table.

    This function is used for both dimension and fact tables.

    chunksize:  Number of rows inserted per batch. This helps avoid memory issues and makes large loads more stable.
    """

    if df.empty:
        log.warning(f"{table_name} is empty. Skipping load.")
        return

    log.info(f"Loading {len(df):,} rows into dbo.{table_name}...")

    try:
        df.to_sql(
            name=table_name,
            con=engine,
            schema="dbo",
            if_exists=if_exists,
            index=False,
            chunksize=chunksize,
        )

        log.info(f"dbo.{table_name} loaded successfully")

    except Exception as e:
        log.error(f"Failed to load dbo.{table_name}")
        log.error(str(e))
        raise


#! ─────────────────────────────────────────────────────────────
#! Clear existing data
#! ─────────────────────────────────────────────────────────────

def clear_tables(engine) -> None:
    """
    Delete all existing rows from the star schema tables before reloading.

    Why facts are cleared first:
        Fact tables contain foreign keys that reference dimension tables.
        If we try to delete dimensions first, SQL Server will block the delete because fact rows still depend on those dimension rows.

       """

    # Delete order is the reverse of load order.
    # Facts must be deleted before dimensions because facts depend on dimension keys through foreign key constraints.
    tables_to_clear = [
        # Fact tables first
        "fact_admissions",
        "fact_er_visits",
        "fact_provincial_wait_times",

        # Dimension tables second
        "dim_patient",
        "dim_hospital",
        "dim_condition",
        "dim_region",
        "dim_procedure",
        "dim_date",
    ]

    log.info("Clearing existing data from SQL Server tables...")

    try:
        # engine.begin() runs the deletes inside a transaction.
        # If one delete fails, the transaction will be rolled back.
        with engine.begin() as conn:
            for table in tables_to_clear:
                conn.execute(text(f"DELETE FROM dbo.{table}"))
                log.info(f"Cleared dbo.{table}")

        log.info("All tables cleared successfully")

    except Exception as e:
        log.error("Failed while clearing existing tables")
        log.error(str(e))
        raise


#! ─────────────────────────────────────────────────────────────
#! Load dimension tables
#! ─────────────────────────────────────────────────────────────

def load_dim_date(
    engine,
    df_admissions: pd.DataFrame,
    df_er: pd.DataFrame
) -> pd.DataFrame:
   
    log.info("Building dim_date...")

    
    admission_dates = pd.to_datetime(
        df_admissions["date_of_admission"],
        errors="coerce"
    ).dt.normalize()

    discharge_dates = pd.to_datetime(
        df_admissions["discharge_date"],
        errors="coerce"
    ).dt.normalize()

    er_dates = pd.to_datetime(
        df_er["visit_date"],
        errors="coerce"
    ).dt.normalize()

    # Combine all date columns into one list of unique calendar dates.
    all_dates = (
        pd.concat([admission_dates, discharge_dates, er_dates])
        .dropna()
        .drop_duplicates()
        .sort_values()
        .reset_index(drop=True)
    )

    # Build the actual date dimension.
    # date_id uses YYYYMMDD format, for example 20260513.
    dim_date = pd.DataFrame({
        "date_id": all_dates.dt.strftime("%Y%m%d").astype(int),
        "full_date": all_dates.dt.date,
        "year": all_dates.dt.year,
        "quarter": all_dates.dt.quarter,
        "month_num": all_dates.dt.month,
        "month_name": all_dates.dt.strftime("%B"),
        "day_of_month": all_dates.dt.day,

        # pandas uses 0=Monday and 6=Sunday.
        "day_of_week": all_dates.dt.dayofweek,
        "day_name": all_dates.dt.strftime("%A"),

        # SQL Server BIT accepts 0/1 values.
        "is_weekend": all_dates.dt.dayofweek.isin([5, 6]).astype(int),
        "is_weekday": (~all_dates.dt.dayofweek.isin([5, 6])).astype(int),
    })

    load_table(engine, dim_date, "dim_date")

    return dim_date


def load_dim_patient(
    engine,
    df_admissions: pd.DataFrame
) -> pd.DataFrame:
   

    log.info("Building dim_patient...")

    dim_patient = (
        df_admissions[["name", "age", "age_group", "gender", "blood_type"]]
        .dropna(subset=["name"])
        .drop_duplicates(subset=["name"])
        .sort_values("name")
        .reset_index(drop=True)
    )

    # Create a simple surrogate key starting from 1.
    dim_patient.insert(0, "patient_id", dim_patient.index + 1)

    # Match the SQL table column name: patient_name.
    dim_patient = dim_patient.rename(columns={"name": "patient_name"})

    load_table(engine, dim_patient, "dim_patient")

    return dim_patient


def load_dim_hospital(
    engine,
    df_admissions: pd.DataFrame,
    df_er: pd.DataFrame
) -> pd.DataFrame:
   

    log.info("Building dim_hospital...")

    # Hospitals from admissions data.
    # Admissions data has hospital names but usually does not include bed count.
    hosp_admissions = (
        df_admissions[["hospital"]]
        .dropna(subset=["hospital"])
        .drop_duplicates()
        .rename(columns={"hospital": "hospital_name"})
    )

    hosp_admissions["region"] = None
    hosp_admissions["facility_beds"] = None
    hosp_admissions["source"] = "admissions"

    # Hospitals from ER data.
    # ER data includes region and facility_beds.
    hosp_er = (
        df_er[["hospital_name", "region", "facility_beds"]]
        .dropna(subset=["hospital_name"])
        .drop_duplicates(subset=["hospital_name"])
    )

    hosp_er["source"] = "er"

    # Combine both sources into one hospital list.
    combined = pd.concat([hosp_admissions, hosp_er], ignore_index=True)

    # Count how many sources each hospital appears in.
    source_count = (
        combined.groupby("hospital_name")["source"]
        .nunique()
        .reset_index(name="source_count")
    )

    combined = combined.merge(source_count, on="hospital_name", how="left")

    # If a hospital appears in both datasets, mark it as both.
    combined["source"] = np.where(
        combined["source_count"] > 1,
        "both",
        combined["source"]
    )

    # Keep one row per hospital.
    # Sorting helps make the generated hospital_id stable across runs.
    dim_hospital = (
        combined
        .sort_values(["hospital_name", "source"])
        .drop_duplicates(subset=["hospital_name"], keep="last")
        .drop(columns=["source_count"])
        .reset_index(drop=True)
    )

    dim_hospital.insert(0, "hospital_id", dim_hospital.index + 1)

    load_table(engine, dim_hospital, "dim_hospital")

    return dim_hospital


def load_dim_condition(
    engine,
    df_admissions: pd.DataFrame
) -> pd.DataFrame:
   

    log.info("Building dim_condition...")

    dim_condition = (
        df_admissions[["medical_condition", "medication"]]
        .dropna(subset=["medical_condition"])
        .drop_duplicates(subset=["medical_condition"])
        .sort_values("medical_condition")
        .reset_index(drop=True)
    )

    dim_condition.insert(0, "condition_id", dim_condition.index + 1)

    dim_condition = dim_condition.rename(columns={
        "medical_condition": "condition_name",
        "medication": "typical_medication",
    })

    load_table(engine, dim_condition, "dim_condition")

    return dim_condition


def load_dim_region(
    engine,
    df_er: pd.DataFrame,
    df_cihi: pd.DataFrame
) -> pd.DataFrame:
   

    log.info("Building dim_region...")

    # Regions from ER dataset.
    er_regions = (
        df_er[["region"]]
        .dropna(subset=["region"])
        .drop_duplicates()
        .rename(columns={"region": "region_name"})
    )

    er_regions["province"] = None
    er_regions["country"] = "Canada"

    # Provinces from CIHI dataset.
    cihi_provinces = (
        df_cihi[["province"]]
        .dropna(subset=["province"])
        .drop_duplicates()
        .rename(columns={"province": "region_name"})
    )

    cihi_provinces["province"] = cihi_provinces["region_name"]
    cihi_provinces["country"] = "Canada"

    dim_region = (
        pd.concat([er_regions, cihi_provinces], ignore_index=True)
        .drop_duplicates(subset=["region_name", "province", "country"])
        .sort_values(["country", "province", "region_name"], na_position="last")
        .reset_index(drop=True)
    )

    dim_region.insert(0, "region_id", dim_region.index + 1)

    load_table(engine, dim_region, "dim_region")

    return dim_region


def load_dim_procedure(
    engine,
    df_cihi: pd.DataFrame
) -> pd.DataFrame:
    

    log.info("Building dim_procedure...")

    dim_procedure = (
        df_cihi[["indicator"]]
        .dropna(subset=["indicator"])
        .drop_duplicates()
        .rename(columns={"indicator": "procedure_name"})
        .sort_values("procedure_name")
        .reset_index(drop=True)
    )

    dim_procedure.insert(0, "procedure_id", dim_procedure.index + 1)

    # These are nullable in SQL, so None is fine.
    dim_procedure["benchmark_days"] = None
    dim_procedure["procedure_category"] = None

    load_table(engine, dim_procedure, "dim_procedure")

    return dim_procedure

# ─────────────────────────────────────────────────────────────
# Fact table helpers
# ─────────────────────────────────────────────────────────────

def validate_foreign_keys(
    df: pd.DataFrame,
    fk_columns: list[str],
    table_name: str
) -> None:
    """
    Check that all foreign key columns were successfully mapped.

    Why this matters:
        Fact tables depend on dimension keys. If a foreign key is missing,
        SQL Server will reject the row because of NOT NULL and FK constraints.

    Instead of allowing the script to fail later during loading, we stop here
    with a clear error message that tells us exactly which key failed.
    """

    missing_summary = {}

    for col in fk_columns:
        missing_count = df[col].isna().sum()

        if missing_count > 0:
            missing_summary[col] = missing_count

    if missing_summary:
        message_lines = [f"{table_name} has unmatched foreign keys:"]

        for col, count in missing_summary.items():
            message_lines.append(f"  - {col}: {count:,} missing values")

        message_lines.append(
            "Fix the dimension mapping before loading this fact table."
        )

        raise ValueError("\n".join(message_lines))


def cast_foreign_keys_to_int(
    df: pd.DataFrame,
    fk_columns: list[str]
) -> pd.DataFrame:
    """
    Convert foreign key columns from float/object to int.

    pandas may turn ID columns into float after a merge if missing values
    exist. After validation confirms there are no missing IDs, we safely
    convert them back to int so they match SQL Server INT columns.
    """

    df = df.copy()

    for col in fk_columns:
        df[col] = df[col].astype(int)

    return df


#! ─────────────────────────────────────────────────────────────
#! Load fact tables
#! ─────────────────────────────────────────────────────────────

def load_fact_admissions(
    engine,
    df_admissions: pd.DataFrame,
    dim_patient: pd.DataFrame,
    dim_hospital: pd.DataFrame,
    dim_condition: pd.DataFrame,
    dim_date: pd.DataFrame,
) -> None:


    log.info("Building fact_admissions...")

    df = df_admissions.copy()

    # ── Map patient_name/name to patient_id ─────────────────────
    patient_lookup = dim_patient[["patient_id", "patient_name"]].rename(
        columns={"patient_name": "name"}
    )

    df = df.merge(
        patient_lookup,
        on="name",
        how="left"
    )

    # ── Map hospital name to hospital_id ────────────────────────
    hospital_lookup = (
    dim_hospital[dim_hospital["source"] == "admissions"]
    [["hospital_id", "hospital_name"]]
    .rename(columns={"hospital_name": "hospital"})
)
    df = df.merge(
    hospital_lookup,
    on="hospital",
    how="left"
)

    # ── Map medical condition to condition_id ───────────────────
    condition_lookup = dim_condition[["condition_id", "condition_name"]].rename(
        columns={"condition_name": "medical_condition"}
    )

    df = df.merge(
        condition_lookup,
        on="medical_condition",
        how="left"
    )

    # ── Map admission date to admission_date_id ─────────────────
    date_lookup = dim_date[["date_id", "full_date"]].copy()

    # Make sure both sides use plain date values, not datetime timestamps.
    date_lookup["full_date"] = pd.to_datetime(
        date_lookup["full_date"],
        errors="coerce"
    ).dt.date

    df["date_of_admission"] = pd.to_datetime(
        df["date_of_admission"],
        errors="coerce"
    ).dt.date

    df = df.merge(
        date_lookup.rename(columns={
            "date_id": "admission_date_id",
            "full_date": "date_of_admission",
        }),
        on="date_of_admission",
        how="left"
    )

    # ── Map discharge date to discharge_date_id ─────────────────
    df["discharge_date"] = pd.to_datetime(
        df["discharge_date"],
        errors="coerce"
    ).dt.date

    df = df.merge(
        date_lookup.rename(columns={
            "date_id": "discharge_date_id",
            "full_date": "discharge_date",
        }),
        on="discharge_date",
        how="left"
    )

    # ── Select columns in the exact same order as SQL table ─────
    fact = df[[
        "admission_id",
        "patient_id",
        "hospital_id",
        "condition_id",
        "admission_date_id",
        "discharge_date_id",
        "doctor",
        "insurance_provider",
        "admission_type",
        "room_number",
        "billing_amount",
        "length_of_stay_days",
        "medication",
        "test_results",
    ]].copy()

    fk_columns = [
        "patient_id",
        "hospital_id",
        "condition_id",
        "admission_date_id",
        "discharge_date_id",
    ]

    validate_foreign_keys(fact, fk_columns, "fact_admissions")
    fact = cast_foreign_keys_to_int(fact, fk_columns)

    load_table(engine, fact, "fact_admissions")


def load_fact_er_visits(
    engine,
    df_er: pd.DataFrame,
    dim_hospital: pd.DataFrame,
    dim_region: pd.DataFrame,
    dim_date: pd.DataFrame,
) -> None:
   

    log.info("Building fact_er_visits...")

    df = df_er.copy()
    df = df.drop(columns=["hospital_id"], errors="ignore")


    # ── Map hospital_name to hospital_id ────────────────────────
    hospital_lookup = dim_hospital[["hospital_id", "hospital_name"]]

    df = df.merge(
        hospital_lookup,
        on="hospital_name",
        how="left"
    )

    # ── Map region to region_id ─────────────────────────────────
    region_lookup = dim_region[["region_id", "region_name"]].rename(
        columns={"region_name": "region"}
    )

    df = df.merge(
        region_lookup,
        on="region",
        how="left"
    )

    # ── Map visit_date to visit_date_id ─────────────────────────
    date_lookup = dim_date[["date_id", "full_date"]].copy()

    date_lookup["full_date"] = pd.to_datetime(
        date_lookup["full_date"],
        errors="coerce"
    ).dt.date

    df["visit_date"] = pd.to_datetime(
        df["visit_date"],
        errors="coerce"
    ).dt.date

    df = df.merge(
        date_lookup.rename(columns={
            "date_id": "visit_date_id",
            "full_date": "visit_date",
        }),
        on="visit_date",
        how="left"
    )

    # ── Select columns in the exact same order as SQL table ─────
    fact = df[[
        "visit_id",
        "patient_id",
        "hospital_id",
        "region_id",
        "visit_date_id",
        "visit_hour",
        "visit_year",
        "visit_month",
        "day_of_week",
        "season",
        "time_of_day",
        "urgency_level",
        "nurse_patient_ratio",
        "specialist_count",
        "facility_beds",
        "time_to_registration_min",
        "time_to_triage_min",
        "time_to_doctor_min",
        "total_wait_time_min",
        "wait_time_category",
        "benchmark_met",
        "patient_outcome",
        "patient_satisfaction",
    ]].copy()

    fk_columns = [
        "hospital_id",
        "region_id",
        "visit_date_id",
    ]

    validate_foreign_keys(fact, fk_columns, "fact_er_visits")
    fact = cast_foreign_keys_to_int(fact, fk_columns)

    load_table(engine, fact, "fact_er_visits")


def load_fact_provincial_wait_times(
    engine,
    df_cihi: pd.DataFrame,
    dim_procedure: pd.DataFrame,
    dim_region: pd.DataFrame,
) -> None:
    

    log.info("Building fact_provincial_wait_times...")

    df = df_cihi.copy()

    # ── Map CIHI indicator to procedure_id ──────────────────────
    procedure_lookup = dim_procedure[["procedure_id", "procedure_name"]].rename(
        columns={"procedure_name": "indicator"}
    )

    df = df.merge(
        procedure_lookup,
        on="indicator",
        how="left"
    )

    # ── Map CIHI province to region_id ──────────────────────────
    # dim_region stores CIHI provinces as region_name.
    region_lookup = dim_region[["region_id", "region_name"]].rename(
        columns={"region_name": "province"}
    )

    df = df.merge(
        region_lookup,
        on="province",
        how="left"
    )

    # ── Select columns in the exact same order as SQL table ─────
    fact = df[[
        "wait_time_id",
        "procedure_id",
        "region_id",
        "reporting_level",
        "data_year",
        "metric",
        "unit_of_measurement",
        "indicator_result",
    ]].copy()

    fk_columns = [
        "procedure_id",
        "region_id",
    ]

# ── Deduplicate on grain columns ───────────────────────────────
# The CIHI dataset contains both Provincial and Regional level rows.
# Some province/procedure/year/metric combinations appear more than once when both reporting levels are present.
# i keep Provincial level rows first, falling back to Regional if no Provincial row exists for that combination.

    before_dedup = len(fact)
    fact = (
    fact
    .sort_values(
        "reporting_level",
        key=lambda x: x.map({"Provincial": 0, "Regional": 1, "National": 2}).fillna(3)
    )
    .drop_duplicates(
        subset=["procedure_id", "region_id", "data_year", "metric"],
        keep="first"
    )
    .reset_index(drop=True)
    )
    # Reassign wait_time_id after deduplication so IDs are sequential
    fact["wait_time_id"] = range(1, len(fact) + 1)

    after_dedup = len(fact)
    log.info(f"Deduplication: kept {after_dedup:,} rows, removed {before_dedup - after_dedup:,} duplicates")



    validate_foreign_keys(fact, fk_columns, "fact_provincial_wait_times")
    fact = cast_foreign_keys_to_int(fact, fk_columns)

    load_table(engine, fact, "fact_provincial_wait_times")

#* ─────────────────────────────────────────────────────────────
#* Main execution
#* ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    engine = get_engine()
    test_connection(engine)
    log.info("Reading cleaned CSV files...")
    df_admissions = pd.read_csv(PROCESSED_DIR / "admissions_clean.csv")
    df_er         = pd.read_csv(PROCESSED_DIR / "er_visits_clean.csv")
    df_cihi       = pd.read_csv(PROCESSED_DIR / "cihi_wait_times_clean.csv")
    log.info("All files loaded")

    clear_tables(engine)

    log.info("Loading dimension tables...")
    dim_date      = load_dim_date(engine, df_admissions, df_er)
    dim_patient   = load_dim_patient(engine, df_admissions)
    dim_hospital  = load_dim_hospital(engine, df_admissions, df_er)
    dim_condition = load_dim_condition(engine, df_admissions)
    dim_region    = load_dim_region(engine, df_er, df_cihi)
    dim_procedure = load_dim_procedure(engine, df_cihi)
    log.info("All dimension tables loaded")

    log.info("Loading fact tables...")
    load_fact_admissions(engine, df_admissions, dim_patient,
                         dim_hospital, dim_condition, dim_date)
    load_fact_er_visits(engine, df_er, dim_hospital, dim_region, dim_date)
    load_fact_provincial_wait_times(engine, df_cihi, dim_procedure, dim_region)
    log.info("All fact tables loaded")

    log.info("Pipeline complete")