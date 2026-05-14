-- ================================================================
-- DIMENSION TABLES
-- ================================================================


-- ====================
-- dim_date
-- ====================


CREATE TABLE dim_date (
   
    date_id         INT             NOT NULL,
    full_date       DATE            NOT NULL,
    year            INT             NOT NULL,
    quarter         INT             NOT NULL,
    month_num       INT             NOT NULL,
    month_name      VARCHAR(10)     NOT NULL,
    day_of_month    INT             NOT NULL,
    day_of_week     INT             NOT NULL,
    day_name        VARCHAR(10)     NOT NULL,
    -- 1 means Saturday/Sunday, 0 means regular weekday.
    is_weekend      BIT             NOT NULL,

    -- 1 means Monday-Friday, 0 means weekend.
    is_weekday      BIT             NOT NULL,
    CONSTRAINT PK_dim_date PRIMARY KEY (date_id),
    -- Unique constraint prevents the same full_date from being inserted twice.
    CONSTRAINT UQ_dim_date_full_date UNIQUE (full_date)
);
GO

-- ====================
-- dim_patient
-- ====================

CREATE TABLE dim_patient (
    patient_id      INT             NOT NULL,
    patient_name    VARCHAR(100)    NOT NULL,
    age             INT             NOT NULL,
    age_group       VARCHAR(20)     NOT NULL,
    gender          VARCHAR(10)     NOT NULL,
    blood_type      VARCHAR(5)      NOT NULL,
    CONSTRAINT PK_dim_patient 
        PRIMARY KEY (patient_id),
    -- Keeps patient age within a realistic human range.
    CONSTRAINT CHK_dim_patient_age 
        CHECK (age >= 0 AND age <= 120),
    CONSTRAINT CHK_dim_patient_gender 
        CHECK (gender IN ('Male', 'Female', 'Other')),

    CONSTRAINT CHK_dim_patient_blood_type
        CHECK (blood_type IN ('A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'))
);
GO


-- ====================
-- dim_hospital
-- ====================

CREATE TABLE dim_hospital (
    hospital_id     INT             NOT NULL,
    hospital_name   VARCHAR(200)    NOT NULL,
    region          VARCHAR(100)    NULL,
    facility_beds   INT             NULL,
    -- Tracks where this hospital record came from.
    -- This helps when hospitals are created from more than one dataset.
    source          VARCHAR(20)     NOT NULL,

    CONSTRAINT PK_dim_hospital
        PRIMARY KEY (hospital_id),

    CONSTRAINT CHK_dim_hospital_source
        CHECK (source IN ('admissions', 'er', 'both')),

    CONSTRAINT CHK_dim_hospital_facility_beds
        CHECK (facility_beds IS NULL OR facility_beds >= 0)
);
GO

-- ====================
-- dim_condition
-- ====================
--   Stores one row per unique medical condition.

CREATE TABLE dim_condition (
    condition_id        INT             NOT NULL,
    condition_name      VARCHAR(100)    NOT NULL,
    typical_medication  VARCHAR(100)    NULL,

    CONSTRAINT PK_dim_condition
        PRIMARY KEY (condition_id),

    -- Prevents duplicate condition names in the dimension.
    CONSTRAINT UQ_dim_condition_name
        UNIQUE (condition_name)
);
GO

-- ====================
-- dim_region
-- ====================
--   Region is used to compare healthcare performance across locations.
--   This is useful for ER wait time reporting and CIHI provincial wait time analysis.

CREATE TABLE dim_region (
    region_id       INT             NOT NULL,
    region_name     VARCHAR(100)    NOT NULL,
    province        VARCHAR(100)    NULL,
    country         VARCHAR(50)     NOT NULL,

    CONSTRAINT PK_dim_region
        PRIMARY KEY (region_id),

    -- Prevents the same region/province/country combination from repeating.
    CONSTRAINT UQ_dim_region_location
        UNIQUE (region_name, province, country)
);
GO

-- ====================
-- dim_procedure
-- ====================
--   CIHI wait time reporting is procedure-based. This table lets us  analyze wait times by procedure, category, and benchmark target.


CREATE TABLE dim_procedure (
    procedure_id        INT             NOT NULL,
    procedure_name      VARCHAR(200)    NOT NULL,
    benchmark_days      INT             NULL,
    procedure_category  VARCHAR(100)    NULL,

    CONSTRAINT PK_dim_procedure
        PRIMARY KEY (procedure_id),
    CONSTRAINT UQ_dim_procedure_name
        UNIQUE (procedure_name),

    -- Benchmark days must be positive when provided.
    CONSTRAINT CHK_dim_procedure_benchmark
        CHECK (benchmark_days IS NULL OR benchmark_days > 0)
);
GO



-- ================================================================
-- Fact TABLES
-- ================================================================

-- ====================
-- fact_admissions
-- ====================
--   Stores one row per hospital admission.
--
--   This is the main fact table for admissions analysis. 
-- It stores the measurable values we want to analyze, such as billing amount and length of stay, while descriptive details are stored in dimensions.

CREATE TABLE fact_admissions (
    admission_id            INT             NOT NULL,
    patient_id              INT             NOT NULL,
    hospital_id             INT             NOT NULL,
    condition_id            INT             NOT NULL,
    admission_date_id       INT             NOT NULL,
    discharge_date_id       INT             NOT NULL,

    -- Optional descriptive fields from the admissions dataset.
    doctor                  VARCHAR(200)    NULL,
    insurance_provider      VARCHAR(100)    NULL,

    admission_type          VARCHAR(20)     NOT NULL,

    room_number             INT             NULL,

    billing_amount          DECIMAL(10,2)   NOT NULL,

    length_of_stay_days     INT             NOT NULL,

    medication              VARCHAR(100)    NULL,

    -- Test result category used for quality/risk analysis.
    test_results            VARCHAR(20)     NOT NULL,

    CONSTRAINT PK_fact_admissions
        PRIMARY KEY (admission_id),

    CONSTRAINT FK_fact_admissions_patient
        FOREIGN KEY (patient_id)
        REFERENCES dim_patient(patient_id),

    CONSTRAINT FK_fact_admissions_hospital
        FOREIGN KEY (hospital_id)
        REFERENCES dim_hospital(hospital_id),

    CONSTRAINT FK_fact_admissions_condition
        FOREIGN KEY (condition_id)
        REFERENCES dim_condition(condition_id),

    CONSTRAINT FK_fact_admissions_admission_date
        FOREIGN KEY (admission_date_id)
        REFERENCES dim_date(date_id),

    CONSTRAINT FK_fact_admissions_discharge_date
        FOREIGN KEY (discharge_date_id)
        REFERENCES dim_date(date_id),

    -- Billing cannot be negative.
    CONSTRAINT CHK_fact_admissions_billing
        CHECK (billing_amount >= 0),

    -- Same-day discharge is valid (LOS = 0).
    -- Only negative values indicate a data error.
    CONSTRAINT CHK_fact_admissions_los
    CHECK (length_of_stay_days >= 0),

    -- Keeps admission type values consistent for reporting.
    CONSTRAINT CHK_fact_admissions_type
        CHECK (admission_type IN ('Elective', 'Urgent', 'Emergency')),

    -- Keeps test result categories clean.
    CONSTRAINT CHK_fact_admissions_test
        CHECK (test_results IN ('Normal', 'Abnormal', 'Inconclusive'))
);
GO


-- ====================
-- fact_er_visits
-- ====================
--   Stores one row per emergency room visit.
--   This fact table supports ER performance analysis, including wait  times, benchmark performance, urgency-level patterns, staffing indicators, patient outcomes, and satisfaction scores.


CREATE TABLE fact_er_visits (
    visit_id                    VARCHAR(50)     NOT NULL,
    patient_id                  VARCHAR(20)     NOT NULL,
    hospital_id                 INT             NOT NULL,
    region_id                   INT             NOT NULL,
    visit_date_id               INT             NOT NULL,

    -- Time attributes kept in the fact table because they describe the exact ER visit event.
    visit_hour                  INT             NOT NULL,
    visit_year                  INT             NOT NULL,
    visit_month                 INT             NOT NULL,
    day_of_week                 VARCHAR(10)     NOT NULL,
    season                      VARCHAR(10)     NOT NULL,
    time_of_day                 VARCHAR(20)     NOT NULL,

    -- Urgency category assigned to the ER visit.
    urgency_level               VARCHAR(10)     NOT NULL,

    -- Operational capacity/staffing indicators.
    nurse_patient_ratio         INT             NULL,
    specialist_count            INT             NULL,
    facility_beds               INT             NULL,

    -- Wait time components in minutes.
    time_to_registration_min    INT             NULL,
    time_to_triage_min          INT             NULL,
    time_to_doctor_min          INT             NULL,
    total_wait_time_min         INT             NULL,

    -- Derived category from total wait time.
    wait_time_category          VARCHAR(30)     NOT NULL,

    -- 1 means the visit met the benchmark, 0 means it did not.
    benchmark_met               BIT             NOT NULL,

    -- ER visit result, such as discharged or admitted.
    patient_outcome             VARCHAR(50)     NULL,

    -- Patient satisfaction score from 1 to 5.
    patient_satisfaction        INT             NULL,

    CONSTRAINT PK_fact_er_visits
        PRIMARY KEY (visit_id),

    CONSTRAINT FK_fact_er_visits_hospital
        FOREIGN KEY (hospital_id)
        REFERENCES dim_hospital(hospital_id),

    CONSTRAINT FK_fact_er_visits_region
        FOREIGN KEY (region_id)
        REFERENCES dim_region(region_id),

    CONSTRAINT FK_fact_er_visits_date
        FOREIGN KEY (visit_date_id)
        REFERENCES dim_date(date_id),

    -- Visit hour should follow a 24-hour clock.
    CONSTRAINT CHK_fact_er_visits_hour
        CHECK (visit_hour BETWEEN 0 AND 23),

    -- Month should be between January and December.
    CONSTRAINT CHK_fact_er_visits_month
        CHECK (visit_month BETWEEN 1 AND 12),

    -- Keeps urgency values aligned with the cleaning script.
    CONSTRAINT CHK_fact_er_visits_urgency
        CHECK (urgency_level IN ('Critical', 'High', 'Medium', 'Low')),

    -- Wait times cannot be negative when provided.
    CONSTRAINT CHK_fact_er_visits_wait_time
        CHECK (total_wait_time_min IS NULL OR total_wait_time_min >= 0),

    -- Patient satisfaction is expected to be a 1 to 5 score.
    CONSTRAINT CHK_fact_er_visits_satisfaction
        CHECK (
            patient_satisfaction IS NULL
            OR patient_satisfaction BETWEEN 1 AND 5
        ),

    -- Operational counts cannot be negative when provided.
    CONSTRAINT CHK_fact_er_visits_staffing
        CHECK (
            (nurse_patient_ratio IS NULL OR nurse_patient_ratio >= 0)
            AND (specialist_count IS NULL OR specialist_count >= 0)
            AND (facility_beds IS NULL OR facility_beds >= 0)
        )
);
GO

-- ==========================
-- fact_provincial_wait_times
-- ==========================
--   Stores provincial wait time measures from the CIHI dataset.
--   One row represents one metric value for one procedure, in one region/province, for one reporting year.
--
-- Example:
--   Ontario + Hip Replacement + 2024 + 50th percentile wait time

CREATE TABLE fact_provincial_wait_times (
    wait_time_id        INT             NOT NULL,
    procedure_id        INT             NOT NULL,
    region_id           INT             NOT NULL,

    -- Reporting level from the CIHI file.
    -- Examples may include Province, Region, or National.
    reporting_level     VARCHAR(20)     NOT NULL,
    data_year           INT             NOT NULL,
    metric              VARCHAR(50)     NOT NULL,
    unit_of_measurement VARCHAR(50)     NULL,
    indicator_result    DECIMAL(10,2)   NULL,

    CONSTRAINT PK_fact_provincial_wait_times
        PRIMARY KEY (wait_time_id),

    CONSTRAINT FK_fact_provincial_procedure
        FOREIGN KEY (procedure_id)
        REFERENCES dim_procedure(procedure_id),

    CONSTRAINT FK_fact_provincial_region
        FOREIGN KEY (region_id)
        REFERENCES dim_region(region_id),

    -- CIHI historical data starts in 2008.
    -- The upper bound allows future updates or forecasted values later.
    CONSTRAINT CHK_fact_provincial_year
        CHECK (data_year BETWEEN 2008 AND 2030),

    -- Wait times, volumes, and percentages should not be negative.
    CONSTRAINT CHK_fact_provincial_result
        CHECK (indicator_result IS NULL OR indicator_result >= 0),

    -- Prevents duplicate metric rows for the same procedure, region, and year.
    CONSTRAINT UQ_fact_provincial_wait_times_grain
        UNIQUE (procedure_id, region_id, data_year, metric)
);
GO