-- PostgreSQL Database Size Report
-- Shows table sizes, index sizes, and row counts for all tables
-- With detailed breakdown for chat_message table
-- EXAMPLE: PGPASSWORD=mySecurePassword psql -h localhost -p 5432 -U username -d velachat -f check_db_sizes.sql

\echo '========================================'
\echo 'DATABASE TABLE SIZES'
\echo '========================================'
\echo ''

SELECT 
    tablename AS "Table Name",
    pg_size_pretty(pg_total_relation_size('public.' || tablename)) AS "Total Size",
    pg_size_pretty(pg_relation_size('public.' || tablename)) AS "Table Size",
    pg_size_pretty(pg_total_relation_size('public.' || tablename) - pg_relation_size('public.' || tablename)) AS "Indexes Size",
    (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = tablename) AS "Column Count"
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size('public.' || tablename) DESC;

\echo ''
\echo '========================================'
\echo 'ROW COUNTS FOR ALL TABLES'
\echo '========================================'
\echo ''

SELECT 
    tablename AS "Table Name",
    (xpath('/row/c/text()', query_to_xml(format('select count(*) as c from %I.%I', schemaname, tablename), false, true, '')))[1]::text::int AS "Row Count"
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY "Row Count" DESC;

\echo ''
\echo '========================================'
\echo 'DETAILED INFORMATION: chat_message TABLE'
\echo '========================================'
\echo ''

-- Total size information
SELECT 
    'Total Size (including indexes)' AS "Metric",
    pg_size_pretty(pg_total_relation_size('public.chat_message')) AS "Size",
    pg_total_relation_size('public.chat_message') AS "Bytes"
UNION ALL
SELECT 
    'Table Size (data only)' AS "Metric",
    pg_size_pretty(pg_relation_size('public.chat_message')) AS "Size",
    pg_relation_size('public.chat_message') AS "Bytes"
UNION ALL
SELECT 
    'Indexes Size' AS "Metric",
    pg_size_pretty(pg_total_relation_size('public.chat_message') - pg_relation_size('public.chat_message')) AS "Size",
    (pg_total_relation_size('public.chat_message') - pg_relation_size('public.chat_message')) AS "Bytes"
UNION ALL
SELECT 
    'Row Count' AS "Metric",
    COUNT(*)::text AS "Size",
    COUNT(*) AS "Bytes"
FROM chat_message;

\echo ''
\echo 'Average row size:'
SELECT 
    pg_size_pretty(pg_relation_size('public.chat_message') / NULLIF((SELECT COUNT(*) FROM chat_message), 0)) AS "Average Row Size"
WHERE EXISTS (SELECT 1 FROM chat_message);

\echo ''
\echo '========================================'
\echo 'chat_message TABLE COLUMNS'
\echo '========================================'
\echo ''

SELECT 
    column_name AS "Column Name",
    data_type AS "Data Type",
    CASE 
        WHEN character_maximum_length IS NOT NULL THEN data_type || '(' || character_maximum_length || ')'
        ELSE data_type
    END AS "Full Type",
    is_nullable AS "Nullable"
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'chat_message'
ORDER BY ordinal_position;

\echo ''
\echo '========================================'
\echo 'chat_message TABLE INDEXES'
\echo '========================================'
\echo ''

SELECT 
    indexname AS "Index Name",
    pg_size_pretty(pg_relation_size(indexname::regclass)) AS "Index Size",
    pg_relation_size(indexname::regclass) AS "Bytes",
    indexdef AS "Definition"
FROM pg_indexes
WHERE schemaname = 'public' AND tablename = 'chat_message'
ORDER BY pg_relation_size(indexname::regclass) DESC;

\echo ''
\echo '========================================'
\echo 'DATABASE SUMMARY'
\echo '========================================'
\echo ''

SELECT 
    pg_size_pretty(pg_database_size(current_database())) AS "Total Database Size",
    (SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public') AS "Number of Tables",
    pg_size_pretty(pg_total_relation_size('public.chat_message')) AS "chat_message Size",
    ROUND(100.0 * pg_total_relation_size('public.chat_message') / NULLIF(pg_database_size(current_database()), 0), 2) AS "chat_message % of Total";
















