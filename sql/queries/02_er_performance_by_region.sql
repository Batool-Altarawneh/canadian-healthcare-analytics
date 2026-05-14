
-- ================================================================
--   Which regions and urgency levels have the worst ER wait times?
--   How does benchmark performance vary across the system?
-- ================================================================
-- 
--   Resource allocation decisions like: staffing, equipment, capacity depend on knowing which regions are underperforming and for which urgency levels.
-- ================================================================

SELECT
    r.region_name AS region,
    f.urgency_level AS urgency_level,

    COUNT(*) AS total_visits,

    -- Wait time averages
    CAST(
        AVG(CAST(f.total_wait_time_min AS FLOAT))
        AS DECIMAL(10,1)
    ) AS avg_total_wait_min,

    CAST(
        AVG(CAST(f.time_to_doctor_min AS FLOAT))
        AS DECIMAL(10,1)
    ) AS avg_time_to_doctor_min,

    -- Benchmark performance
    SUM(CASE WHEN f.benchmark_met = 1 THEN 1 ELSE 0 END)
        AS visits_meeting_benchmark,

    CAST(
        100.0 * SUM(CASE WHEN f.benchmark_met = 1 THEN 1 ELSE 0 END)
        / NULLIF(COUNT(*), 0)
        AS DECIMAL(5,1)
    ) AS pct_benchmark_met,

    -- Wait time distribution
    MIN(f.total_wait_time_min) AS min_wait_min,
    MAX(f.total_wait_time_min) AS max_wait_min,

    -- Performance rating based on average total wait time
    CASE
        WHEN AVG(CAST(f.total_wait_time_min AS FLOAT)) <= 60
            THEN 'Good'
        WHEN AVG(CAST(f.total_wait_time_min AS FLOAT)) <= 120
            THEN 'Acceptable'
        ELSE 'Needs Improvement'
    END AS performance_rating

FROM dbo.fact_er_visits AS f

JOIN dbo.dim_region AS r
    ON f.region_id = r.region_id

GROUP BY
    r.region_name,
    f.urgency_level

ORDER BY
    r.region_name,
    f.urgency_level;
GO
