
-- ================================================================
-- Which patient profiles are most associated with abnormal test results?
-- Which age group and admission type combinations carry the highest risk?
-- ================================================================
-- This query identifies which patient segments should receive closer monitoring.
-- ================================================================


WITH risk_profile AS (
    SELECT
        p.age_group AS age_group,
        f.admission_type AS admission_type,

        COUNT(*) AS total_patients,

        -- Number of abnormal test results in this patient segment.
        SUM(CASE WHEN f.test_results = 'Abnormal' THEN 1 ELSE 0 END)
            AS abnormal_count,

        -- Abnormal test result rate for this segment.
        CAST(
            100.0 * SUM(CASE WHEN f.test_results = 'Abnormal' THEN 1 ELSE 0 END)
            / NULLIF(COUNT(*), 0)
            AS DECIMAL(5,1)
        ) AS pct_abnormal,

        -- Context metrics.
        CAST(AVG(f.billing_amount) AS DECIMAL(12,2)) AS avg_billing_cad,

        CAST(
            AVG(CAST(f.length_of_stay_days AS FLOAT))
            AS DECIMAL(6,1)
        ) AS avg_los_days

    FROM dbo.fact_admissions AS f

    JOIN dbo.dim_patient AS p
        ON f.patient_id = p.patient_id

    GROUP BY
        p.age_group,
        f.admission_type

    -- Only keep groups with enough records to make the rate meaningful.
    HAVING COUNT(*) >= 100
),

overall_average AS (
    SELECT
        CAST(
            100.0 * SUM(CASE WHEN test_results = 'Abnormal' THEN 1 ELSE 0 END)
            / NULLIF(COUNT(*), 0)
            AS DECIMAL(5,1)
        ) AS overall_pct_abnormal
    FROM dbo.fact_admissions
)

SELECT
    rp.age_group,
    rp.admission_type,
    rp.total_patients,
    rp.abnormal_count,
    rp.pct_abnormal,
    oa.overall_pct_abnormal,

    -- Difference from the overall abnormal rate.
    CAST(
        rp.pct_abnormal - oa.overall_pct_abnormal
        AS DECIMAL(5,1)
    ) AS pct_points_vs_average,

    rp.avg_billing_cad,
    rp.avg_los_days,

    -- Simple risk tier based on abnormal rate compared with overall average.
    CASE
        WHEN rp.pct_abnormal >= oa.overall_pct_abnormal + 5
            THEN 'High Risk'
        WHEN rp.pct_abnormal >= oa.overall_pct_abnormal
            THEN 'Above Average'
        ELSE 'Normal Range'
    END AS risk_tier

FROM risk_profile AS rp

CROSS JOIN overall_average AS oa

ORDER BY
    rp.pct_abnormal DESC,
    rp.total_patients DESC;
GO