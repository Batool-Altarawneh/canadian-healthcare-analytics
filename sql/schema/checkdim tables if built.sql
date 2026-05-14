SELECT 'dim_date'      AS tbl, COUNT(*) AS rows FROM dim_date
UNION ALL SELECT 'dim_patient',    COUNT(*) FROM dim_patient
UNION ALL SELECT 'dim_hospital',   COUNT(*) FROM dim_hospital
UNION ALL SELECT 'dim_condition',  COUNT(*) FROM dim_condition
UNION ALL SELECT 'dim_region',     COUNT(*) FROM dim_region
UNION ALL SELECT 'dim_procedure',  COUNT(*) FROM dim_procedure;