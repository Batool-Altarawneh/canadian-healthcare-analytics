# Data Dictionary : Canadian Healthcare Analytics Platform

This data dictionary explains the structure of the Canadian Healthcare Analytics Platform.  
It documents the main dimension and fact tables used in the star schema, including where each field comes from, what it means, and how it is used in the project.

---

## Dimension Tables

Dimension tables store descriptive information.  
They help make the fact tables easier to analyze by adding context such as dates, patients, hospitals, conditions, regions, and procedures.

---

## `dim_date`

The `dim_date` table stores one row for each calendar date used in the project.

I created this table so date-based analysis is easier in SQL and Power BI. Instead of recalculating year, month, quarter, weekday, and weekend flags every time, these fields are pre-built and can be reused across reports.

| Column | Type | Description |
|--------|------|-------------|
| `date_id` | INT | Surrogate key in `YYYYMMDD` format. Example: `20240131` |
| `full_date` | DATE | The actual calendar date |
| `year` | INT | Calendar year |
| `quarter` | INT | Calendar quarter from 1 to 4 |
| `month_num` | INT | Month number from 1 to 12 |
| `month_name` | VARCHAR | Full month name, such as January or February |
| `day_of_month` | INT | Day number within the month |
| `day_of_week` | INT | Day number within the week, where Monday is 0 and Sunday is 6 |
| `day_name` | VARCHAR | Day name, such as Monday or Tuesday |
| `is_weekend` | BIT | 1 if the date is Saturday or Sunday, otherwise 0 |
| `is_weekday` | BIT | 1 if the date is Monday to Friday, otherwise 0 |

---

## `dim_patient`

The `dim_patient` table stores one row per unique patient from the admissions dataset.

This table separates patient details from the admissions fact table. That makes the model cleaner and avoids repeating the same patient information across multiple admission records.

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| `patient_id` | INT | Generated | Surrogate primary key created during the data modeling step |
| `patient_name` | VARCHAR | `healthcare_dataset.csv` | Patient name after formatting it into title case |
| `age` | INT | `healthcare_dataset.csv` | Patient age in years |
| `age_group` | VARCHAR | Derived | Age category used for analysis: `0-17`, `18-34`, `35-54`, `55-74`, `75+` |
| `gender` | VARCHAR | `healthcare_dataset.csv` | Patient gender: Male, Female, or Other |
| `blood_type` | VARCHAR | `healthcare_dataset.csv` | Patient blood type, such as `AB+`, `AB-`, or `O+` |

---

## `dim_hospital`

The `dim_hospital` table stores hospital-level information.

This table combines hospital names from both the admissions dataset and the ER visits dataset. Some hospitals appear only in admissions, some only in ER visits, and some may appear in both.

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| `hospital_id` | INT | Generated | Surrogate primary key for each hospital |
| `hospital_name` | VARCHAR | Both datasets | Hospital name as reported in the source data |
| `region` | VARCHAR | ER dataset | Hospital region, such as Rural or Urban. This may be NULL for hospitals that only appear in the admissions dataset |
| `facility_beds` | INT | ER dataset | Number of beds in the facility. This may be NULL for admissions-only hospitals |
| `source` | VARCHAR | Derived | Shows whether the hospital came from admissions data, ER data, or both |

---

## `dim_condition`

The `dim_condition` table stores one row per medical condition.

I created this table so conditions can be analyzed consistently across admissions, billing, length of stay, and test result reporting.

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| `condition_id` | INT | Generated | Surrogate primary key for each condition |
| `condition_name` | VARCHAR | `healthcare_dataset.csv` | Medical condition name, such as Diabetes, Asthma, or Hypertension |
| `typical_medication` | VARCHAR | `healthcare_dataset.csv` | Most common medication associated with this condition in the dataset |

---

## `dim_region`

The `dim_region` table stores geographic regions used across the project.

This table supports both ER analysis and CIHI provincial wait time analysis. ER records use general regions like Rural or Urban, while CIHI records use Canadian provinces.

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| `region_id` | INT | Generated | Surrogate primary key for each region |
| `region_name` | VARCHAR | Both datasets | Region or province name |
| `province` | VARCHAR | CIHI dataset | Canadian province name. This may be NULL for ER-only regions |
| `country` | VARCHAR | Derived | Always set to Canada |

---

## `dim_procedure`

The `dim_procedure` table stores one row per CIHI medical procedure.

This table is mainly used with the provincial wait times fact table. It allows wait time metrics to be analyzed by procedure, such as hip replacement or knee replacement.

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| `procedure_id` | INT | Generated | Surrogate primary key for each procedure |
| `procedure_name` | VARCHAR | CIHI dataset | Procedure name, such as Hip Replacement or Knee Replacement |
| `benchmark_days` | INT | Manual | Official wait time benchmark in days. This is currently not populated |
| `procedure_category` | VARCHAR | Manual | Procedure grouping or category. This is currently not populated |

---

# Fact Tables

Fact tables store measurable events.  
They are the main tables used for analysis because they contain things like admissions, ER wait times, billing amounts, length of stay, and provincial wait time metrics.

---

## `fact_admissions`

The `fact_admissions` table stores one row per hospital admission.

This is the main table for analyzing hospital admissions, billing amounts, length of stay, admission types, medical conditions, medications, and test results.


| Column | Type | Source | Description |
|--------|------|--------|-------------|
| `admission_id` | INT | Generated | Surrogate primary key for each admission |
| `patient_id` | INT | FK → `dim_patient` | Links the admission to the patient dimension |
| `hospital_id` | INT | FK → `dim_hospital` | Links the admission to the hospital dimension |
| `condition_id` | INT | FK → `dim_condition` | Links the admission to the medical condition dimension |
| `admission_date_id` | INT | FK → `dim_date` | Date key for the admission date |
| `discharge_date_id` | INT | FK → `dim_date` | Date key for the discharge date |
| `doctor` | VARCHAR | `healthcare_dataset.csv` | Name of the attending doctor |
| `insurance_provider` | VARCHAR | `healthcare_dataset.csv` | Insurance provider linked to the admission |
| `admission_type` | VARCHAR | `healthcare_dataset.csv` | Type of admission: Elective, Urgent, or Emergency |
| `room_number` | INT | `healthcare_dataset.csv` | Hospital room number |
| `billing_amount` | DECIMAL | `healthcare_dataset.csv` | Total billing amount in CAD. Negative values were removed during cleaning |
| `length_of_stay_days` | INT | Derived | Number of days between admission date and discharge date |
| `medication` | VARCHAR | `healthcare_dataset.csv` | Main medication prescribed during the admission |
| `test_results` | VARCHAR | `healthcare_dataset.csv` | Test result category: Normal, Abnormal, or Inconclusive |

---

## `fact_er_visits`

The `fact_er_visits` table stores one row per emergency room visit.

This table is used to analyze ER wait times, urgency levels, time-to-doctor performance, patient outcomes, and whether the visit met the CTAS benchmark.


| Column | Type | Source | Description |
|--------|------|--------|-------------|
| `visit_id` | VARCHAR | ER dataset | Source visit identifier |
| `patient_id` | VARCHAR | ER dataset | Source patient identifier from the ER dataset |
| `hospital_id` | INT | FK → `dim_hospital` | Links the visit to the hospital dimension |
| `region_id` | INT | FK → `dim_region` | Links the visit to the region dimension |
| `visit_date_id` | INT | FK → `dim_date` | Date key for the visit date |
| `visit_hour` | INT | Derived | Hour of visit from 0 to 23 |
| `visit_year` | INT | Derived | Year of the ER visit |
| `visit_month` | INT | Derived | Month number of the ER visit |
| `day_of_week` | VARCHAR | ER dataset | Day name, such as Monday or Tuesday |
| `season` | VARCHAR | ER dataset | Season of the visit: Spring, Summer, Fall, or Winter |
| `time_of_day` | VARCHAR | ER dataset | Time bucket such as Morning, Afternoon, Evening, or Night |
| `urgency_level` | VARCHAR | ER dataset | Visit urgency level: Critical, High, Medium, or Low |
| `nurse_patient_ratio` | INT | ER dataset | Nurse-to-patient ratio at the time of the visit |
| `specialist_count` | INT | ER dataset | Number of specialists available |
| `facility_beds` | INT | ER dataset | Total number of beds in the facility |
| `time_to_registration_min` | INT | ER dataset | Minutes from patient arrival to registration |
| `time_to_triage_min` | INT | ER dataset | Minutes from registration to triage |
| `time_to_doctor_min` | INT | ER dataset | Minutes from triage to seeing a doctor. This is used for the CTAS benchmark check |
| `total_wait_time_min` | INT | ER dataset | Total ER wait time in minutes |
| `wait_time_category` | VARCHAR | Derived | Wait time label such as Fast, Moderate, Slow, or Critical |
| `benchmark_met` | BIT | Derived | 1 if the visit met the CTAS time-to-doctor benchmark, otherwise 0 |
| `patient_outcome` | VARCHAR | ER dataset | Outcome of the visit, such as Discharged, Admitted, or Left Without Being Seen |
| `patient_satisfaction` | INT | ER dataset | Patient satisfaction score from 1 to 5 |

---

## `fact_provincial_wait_times`

The `fact_provincial_wait_times` table stores CIHI wait time data by province, procedure, year, and metric.

This table is built from real CIHI data and is used for provincial healthcare wait time analysis, trend analysis, and forecasting.


| Column | Type | Source | Description |
|--------|------|--------|-------------|
| `wait_time_id` | INT | Generated | Surrogate primary key for each wait time record |
| `procedure_id` | INT | FK → `dim_procedure` | Links the record to the procedure dimension |
| `region_id` | INT | FK → `dim_region` | Links the record to the province or region dimension |
| `reporting_level` | VARCHAR | CIHI dataset | Reporting level, such as Provincial, Regional, or National |
| `data_year` | INT | CIHI dataset | Reporting year from 2008 to 2024 |
| `metric` | VARCHAR | CIHI dataset | Metric name, such as 50th Percentile, 90th Percentile, Volume, or % Meeting Benchmark |
| `unit_of_measurement` | VARCHAR | CIHI dataset | Unit used for the metric, such as Days, Number of cases, or Percent |
| `indicator_result` | DECIMAL | CIHI dataset | Numeric value for the metric. This can be NULL when the province did not report a value |

---

# Data Quality Notes

This section documents the main data quality issues found during ingestion and how they were handled.

I included these notes because they show that the pipeline does more than just load files. It also checks the data, fixes known issues, and makes the outputs safer to use in SQL Server and Power BI.

| Issue | Dataset | Action Taken |
|-------|---------|--------------|
| 108 rows had negative billing amounts | Admissions | These rows were removed during ingestion because billing amounts should not be negative |
| Dates were stored as strings | Admissions | Dates were parsed into proper datetime values using `errors='coerce'` |
| Some CIHI years had mixed formats such as `2019FY` or `Q3Q4` | CIHI | Only valid 4-digit calendar years were kept |
| Suppressed CIHI values were stored as `n/a` | CIHI | These values were replaced with NULL so they can be handled correctly in SQL |
| `AB+` and `AB-` blood types were changed to `Ab+` and `Ab-` during title-case formatting | Admissions | The ingestion step restores the correct format using `str.replace('Ab', 'AB')` |
| ER `visit_id` values were stored as strings instead of integers | ER | The SQL column was widened to `VARCHAR(50)` to avoid load errors |
| CIHI had duplicate grain rows from both Provincial and Regional reporting levels | CIHI | Duplicate records were handled by keeping the Provincial-level records |

---

# CTAS Benchmark Reference

The `benchmark_met` field in the ER visits dataset is based on the CTAS time-to-doctor benchmark.

This benchmark is used to check whether a patient was seen by a doctor within the expected time for their urgency level. The logic is applied during the ER ingestion step in:

`02_ingest_er_wait_times.py`

| Urgency Level | CTAS Level | Benchmark: Time to Doctor |
|---------------|------------|---------------------------|
| Critical | CTAS I | 0 minutes, meaning immediate care |
| High | CTAS II | 15 minutes |
| Medium | CTAS III | 30 minutes |
| Low | CTAS IV | 60 minutes |

---

# Why This Data Dictionary Matters

This data dictionary makes the project easier to understand and maintain. It explains the purpose of each table, the meaning of each column, and the main cleaning decisions made during ingestion.

It also helps connect the technical work to the business use case. For example:

- `fact_admissions` supports analysis of billing, length of stay, admission type, and test results.
- `fact_er_visits` supports ER wait time analysis and CTAS benchmark reporting.
- `fact_provincial_wait_times` supports provincial wait time trends and forecasting.
- The dimension tables make the model easier to use in SQL and Power BI.

