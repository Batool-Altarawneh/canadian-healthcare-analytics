-- ================================================================
--  What are the overall KPIs for patient admissions by year?
-- ================================================================
--   1. Total admissions
--   2. Average billing amount
--   3. Average length of stay
--   4. Test result breakdown percentages
--   5. Total billing amount
--   This query gives healthcare leaders a quick yearly overview of admission volume, cost, patient stay duration, and test result mix.
-- 
-- ================================================================

SELECT
    d.year AS admission_year,

    COUNT(*) AS total_admissions,

    CAST(AVG(f.billing_amount) AS DECIMAL(12,2)) AS avg_billing_cad,

    CAST(
        AVG(CAST(f.length_of_stay_days AS FLOAT))
        AS DECIMAL(6,1)
    ) AS avg_los_days,

    CAST(
        100.0 * SUM(CASE WHEN f.test_results = 'Normal' THEN 1 ELSE 0 END)
        / NULLIF(COUNT(*), 0)
        AS DECIMAL(5,1)
    ) AS pct_normal,

    CAST(
        100.0 * SUM(CASE WHEN f.test_results = 'Abnormal' THEN 1 ELSE 0 END)
        / NULLIF(COUNT(*), 0)
        AS DECIMAL(5,1)
    ) AS pct_abnormal,

    CAST(
        100.0 * SUM(CASE WHEN f.test_results = 'Inconclusive' THEN 1 ELSE 0 END)
        / NULLIF(COUNT(*), 0)
        AS DECIMAL(5,1)
    ) AS pct_inconclusive,

    CAST(SUM(f.billing_amount) AS DECIMAL(15,2)) AS total_billing_cad

FROM dbo.fact_admissions AS f

JOIN dbo.dim_date AS d
    ON f.admission_date_id = d.date_id

GROUP BY
    d.year

ORDER BY
    d.year;
GO
