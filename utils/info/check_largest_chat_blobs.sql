-- Query to find the largest chat JSON blobs in the database
-- Useful for analyzing which chats had the most message data before migration

-- Main query with detailed breakdown
SELECT 
    c.id,
    c.user_id,
    c.title,
    c.created_at,
    c.updated_at,
    -- Size of the chat JSON column (includes TOAST if applicable)
    pg_size_pretty(pg_column_size(c.chat)::bigint) AS chat_json_size,
    pg_column_size(c.chat) AS chat_json_size_bytes,
    -- Check if history.messages exists
    CASE 
        WHEN c.chat IS NULL THEN NULL
        WHEN (c.chat::jsonb->'history'->'messages') IS NULL THEN 'No'
        ELSE 'Yes'
    END AS has_history_messages,
    -- Count messages array if it exists
    CASE 
        WHEN c.chat IS NULL THEN NULL
        WHEN (c.chat::jsonb->'messages') IS NULL THEN NULL
        ELSE jsonb_array_length(c.chat::jsonb->'messages')
    END AS messages_array_length,
    -- Show if params exist
    CASE 
        WHEN (c.chat::jsonb->'params') IS NOT NULL THEN 'Yes'
        ELSE 'No'
    END AS has_params,
    -- Show if files exist
    CASE 
        WHEN (c.chat::jsonb->'files') IS NOT NULL THEN 'Yes'
        ELSE 'No'
    END AS has_files
FROM 
    chat c
WHERE 
    c.chat IS NOT NULL
ORDER BY 
    pg_column_size(c.chat) DESC
LIMIT 50;

-- ============================================================================
-- SIMPLER VERSION (faster, less detail)
-- ============================================================================
-- SELECT 
--     id,
--     user_id,
--     title,
--     pg_size_pretty(pg_column_size(chat)::bigint) AS chat_size,
--     pg_column_size(chat) AS chat_size_bytes
-- FROM chat
-- WHERE chat IS NOT NULL
-- ORDER BY pg_column_size(chat) DESC
-- LIMIT 50;

-- ============================================================================
-- VERSION WITH MESSAGE COUNT (slower but more informative)
-- ============================================================================
-- This version actually counts the messages but is slower due to the subquery
-- SELECT 
--     c.id,
--     c.user_id,
--     c.title,
--     pg_size_pretty(pg_column_size(c.chat)::bigint) AS chat_size,
--     pg_column_size(c.chat) AS chat_size_bytes,
--     (
--         SELECT COUNT(*) 
--         FROM jsonb_object_keys(c.chat::jsonb->'history'->'messages')
--     ) AS history_messages_count,
--     jsonb_array_length(c.chat::jsonb->'messages') AS messages_array_length
-- FROM chat c
-- WHERE c.chat IS NOT NULL
--   AND (c.chat::jsonb->'history'->'messages') IS NOT NULL
-- ORDER BY pg_column_size(c.chat) DESC
-- LIMIT 50;

