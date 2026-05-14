
-- ================================================================
-- How have provincial wait times for hip and knee replacement changed from 2008 to 2024?
-- ================================================================
--   This query uses real CIHI wait time data to show whether provincial surgical wait times are improving, worsening, or staying stable.
-- ================================================================
WITH wait_trends AS (
    SELECT
        r.region_name AS province,
        p.procedure_name AS procedure_name,
        f.data_year,

        CAST(f.indicator_result AS DECIMAL(10,2)) AS p50_wait_days,

        LAG(f.indicator_result) OVER (
            PARTITION BY r.region_name, p.procedure_name
            ORDER BY f.data_year
        ) AS prior_year_p50_wait_days,

        f.indicator_result
            - LAG(f.indicator_result) OVER (
                PARTITION BY r.region_name, p.procedure_name
                ORDER BY f.data_year
            ) AS yoy_change_days,

        CAST(
            100.0 * (
                f.indicator_result
                - LAG(f.indicator_result) OVER (
                    PARTITION BY r.region_name, p.procedure_name
                    ORDER BY f.data_year
                )
            )
            / NULLIF(
                LAG(f.indicator_result) OVER (
                    PARTITION BY r.region_name, p.procedure_name
                    ORDER BY f.data_year
                ),
                0
            )
            AS DECIMAL(6,1)
        ) AS yoy_pct_change

    FROM dbo.fact_provincial_wait_times AS f

    JOIN dbo.dim_region AS r
        ON f.region_id = r.region_id

    JOIN dbo.dim_procedure AS p
        ON f.procedure_id = p.procedure_id

    WHERE
        p.procedure_name IN ('Hip Replacement', 'Knee Replacement')
        AND f.metric = '50th Percentile'
        AND r.region_name <> 'Canada'
)

SELECT
    province,
    procedure_name,
    data_year,
    p50_wait_days,
    CAST(prior_year_p50_wait_days AS DECIMAL(10,2)) AS prior_year_p50_wait_days,
    CAST(yoy_change_days AS DECIMAL(10,2)) AS yoy_change_days,
    yoy_pct_change,

    CASE
        WHEN yoy_change_days IS NULL THEN 'Baseline Year'
        WHEN yoy_change_days > 30 THEN 'Significant Increase'
        WHEN yoy_change_days < -30 THEN 'Significant Decrease'
        ELSE 'Stable'
    END AS trend_flag

FROM wait_trends

ORDER BY
    province,
    procedure_name,
    data_year;
GO
