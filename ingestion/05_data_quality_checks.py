"""
05_data_quality_checks.py
--------------------------
This script runs basic data quality checks on the cleaned healthcare datasets.

It should be run after the ingestion scripts and before loading the data into SQL Server. 
The goal is to catch common data issues early, such as missing values, invalid categories, negative numbers, duplicate IDs, or unrealistic ranges.

Run order:
    1. ingestion/01_ingest_patient_admissions.py
    2. ingestion/02_ingest_er_wait_times.py
    3. ingestion/03_ingest_cihi_wait_times.py
    4. ingestion/05_data_quality_checks.py
    5. ingestion/04_load_to_sql_server.py

Input files:
    data/processed/admissions_clean.csv
    data/processed/er_visits_clean.csv
    data/processed/cihi_wait_times_clean.csv
"""

from pathlib import Path
import logging

import pandas as pd


PROCESSED_DIR = Path("data/processed")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)

log = logging.getLogger(__name__)


# ── Validation engine ──────────────────────────────────────────
class DataQualityChecker:
    """
    A small reusable data quality checker for pandas DataFrames.

    I created this class so I can apply the same type of checks to multiple datasets without repeating the same code each time.

    The checker collects all failures first, then reports them together.
    This is more useful than stopping at the first error because it shows the full picture of what needs to be fixed.
    """

    def __init__(self, df: pd.DataFrame, dataset_name: str):
        self.df = df
        self.dataset_name = dataset_name

        # Store failed checks here so they can be reported at the end.
        self.failures = []

        # Count how many checks passed successfully.
        self.passed = 0

    def expect_no_nulls(self, column: str) -> None:
        """
        Check that a column has no missing values.

        This is useful for important fields like IDs, dates, categories, and numeric columns used in analysis or SQL relationships.
        """
        null_count = self.df[column].isna().sum()

        if null_count > 0:
            self.failures.append(
                f"{column}: {null_count:,} null values found, expected 0"
            )
        else:
            self.passed += 1

    def expect_values_in_set(self, column: str, valid_values: set) -> None:
        """
        Check that all values in a column belong to an expected list.

        For example, gender should only contain Male, Female, or Other.
        This helps catch spelling issues, unexpected labels, or dirty data.
        """
        invalid_mask = ~self.df[column].isin(valid_values)
        invalid_count = invalid_mask.sum()

        if invalid_count > 0:
            unexpected_values = (
                self.df.loc[invalid_mask, column]
                .dropna()
                .unique()
                .tolist()
            )

            self.failures.append(
                f"{column}: {invalid_count:,} rows have unexpected values: "
                f"{unexpected_values}"
            )
        else:
            self.passed += 1

    def expect_column_min(self, column: str, min_val: float) -> None:
        """
        Check that numeric values are not below the allowed minimum.

        Examples:
        - age should not be below 0
        - billing_amount should not be negative
        - wait times should not be negative
        """
        below_min_count = (self.df[column] < min_val).sum()

        if below_min_count > 0:
            min_found = self.df[column].min()

            self.failures.append(
                f"{column}: {below_min_count:,} rows below minimum {min_val}. "
                f"Minimum found: {min_found}"
            )
        else:
            self.passed += 1

    def expect_column_max(self, column: str, max_val: float) -> None:
        """
        Check that numeric values are not above the allowed maximum.

        This helps catch unrealistic values, such as age above 120 or
        data years outside the project range.
        """
        above_max_count = (self.df[column] > max_val).sum()

        if above_max_count > 0:
            max_found = self.df[column].max()

            self.failures.append(
                f"{column}: {above_max_count:,} rows above maximum {max_val}. "
                f"Maximum found: {max_found}"
            )
        else:
            self.passed += 1

    def expect_column_between(
        self,
        column: str,
        min_val: float,
        max_val: float
    ) -> None:
        """
        Check that a numeric column stays within a realistic range.

        I split this into a min check and a max check so the error message clearly tells me whether the issue is too low, too high, or both.
        """
        self.expect_column_min(column, min_val)
        self.expect_column_max(column, max_val)

    def expect_unique(self, column: str) -> None:
        """
        Check that a column has unique values.

        This is important for ID columns like visit_id because duplicate IDs can cause problems when loading data into SQL tables.
        """
        duplicate_count = self.df[column].duplicated().sum()

        if duplicate_count > 0:
            self.failures.append(
                f"{column}: {duplicate_count:,} duplicate values found, expected unique"
            )
        else:
            self.passed += 1

    def report(self) -> bool:
        """
        Print a summary for this dataset.

        Returns:
            True  : all checks passed
            False : one or more checks failed
        """
        total_checks = self.passed + len(self.failures)

        log.info(
            f"[{self.dataset_name}] {self.passed}/{total_checks} checks passed"
        )

        if self.failures:
            for failure in self.failures:
                log.error(f"  FAIL: {failure}")

            return False

        return True


log.info("Data quality checker loaded")

# ── Validation  1: Patient Admissions ─────────────────────
def check_admissions(df: pd.DataFrame) -> bool:
    """
    Run data quality checks for the cleaned patient admissions dataset.

    """
    log.info("Running admissions checks...")

    c = DataQualityChecker(df, "admissions")

   
    for col in [
        "admission_id",
        "name",
        "age",
        "gender",
        "medical_condition",
        "date_of_admission",
        "discharge_date",
        "billing_amount",
        "admission_type",
        "test_results",
    ]:
        c.expect_no_nulls(col)

    c.expect_values_in_set("gender", {"Male", "Female", "Other"})
    c.expect_values_in_set("admission_type", {"Elective", "Urgent", "Emergency"})
    c.expect_values_in_set("test_results", {"Normal", "Abnormal", "Inconclusive"})

    c.expect_values_in_set(
        "medical_condition",
        {"Arthritis", "Asthma", "Cancer", "Diabetes", "Hypertension", "Obesity"},
    )

    c.expect_values_in_set(
        "blood_type",
        {"A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"},
    )


    c.expect_column_between("age", 0, 120)
    c.expect_column_min("billing_amount", 0)
    c.expect_column_between("length_of_stay_days", 0, 365)

    c.expect_unique("admission_id")

    return c.report()


# ── Validation  2: ER Wait Times ──────────────────────────
def check_er_visits(df: pd.DataFrame) -> bool:
    """
    Run data quality checks for the cleaned ER wait times dataset.

    These checks focus on required visit fields, wait time values,
    time-based fields, and unique visit IDs.
    """
    log.info("Running ER visit checks...")

    c = DataQualityChecker(df, "er_visits")

    for col in [
        "visit_id",
        "urgency_level",
        "total_wait_time_min",
        "visit_date",
        "region",
    ]:
        c.expect_no_nulls(col)

    # Make sure urgency level and season use consistent labels.
    c.expect_values_in_set("urgency_level", {"Critical", "High", "Medium", "Low"})
    c.expect_values_in_set("season", {"Spring", "Summer", "Fall", "Winter"})

    # Validate numeric ranges.
    # 1440 minutes is one full day, so values above that would need review.
    c.expect_column_between("total_wait_time_min", 0, 1440)
    c.expect_column_between("visit_hour", 0, 23)
    c.expect_column_between("visit_month", 1, 12)
    c.expect_column_between("patient_satisfaction", 1, 5)

    # Wait time components should never be negative.
    for col in [
        "time_to_registration_min",
        "time_to_triage_min",
        "time_to_doctor_min",
    ]:
        c.expect_column_min(col, 0)

    # Each ER visit should appear once.
    c.expect_unique("visit_id")

    return c.report()


# ── Validation  3: CIHI Wait Times ────────────────────────
def check_cihi(df: pd.DataFrame) -> bool:
    """
    Run data quality checks for the cleaned CIHI wait times dataset.

    These checks make sure the provincial wait time data has valid years, required descriptive fields, valid metric names, and no negative results.
    """
    log.info("Running CIHI checks...")

    c = DataQualityChecker(df, "cihi")


    for col in [
        "wait_time_id",
        "province",
        "indicator",
        "metric",
        "data_year",
    ]:
        c.expect_no_nulls(col)

    c.expect_column_between("data_year", 2008, 2024)

    c.expect_values_in_set(
        "metric",
        {
            "50th Percentile",
            "90th Percentile",
            "Volume",
            "% Meeting Benchmark",
        },
    )

   
    non_null_results = df["indicator_result"].dropna()
    negative_count = (non_null_results < 0).sum()

    if negative_count > 0:
        c.failures.append(
            f"indicator_result: {negative_count:,} negative values"
        )
    else:
        c.passed += 1

    # wait_time_id is the surrogate key for this dataset.
    c.expect_unique("wait_time_id")

    return c.report()


if __name__ == "__main__":
  

    log.info("Loading cleaned datasets...")

    df_adm = pd.read_csv(PROCESSED_DIR / "admissions_clean.csv")
    df_er = pd.read_csv(PROCESSED_DIR / "er_visits_clean.csv")
    df_cihi = pd.read_csv(PROCESSED_DIR / "cihi_wait_times_clean.csv")

    log.info("All files loaded")

    # Run each dataset through its own validation suite.
    results = {
        "admissions": check_admissions(df_adm),
        "er_visits": check_er_visits(df_er),
        "cihi": check_cihi(df_cihi),
    }

    log.info("=== QUALITY SUMMARY ===")

    all_passed = True

    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        log.info(f"  {name:<20} {status}")

        if not passed:
            all_passed = False

    if all_passed:
        log.info("All quality checks passed. Safe to load.")
    else:
        raise SystemExit(
            "Quality checks failed. Fix issues before loading to SQL Server."
        )