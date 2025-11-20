-- Find feedback rows with null or invalid ratings
-- These are the rows causing the Leaderboard.svelte error I started seeing at some point

SELECT 
    id,
    user_id,
    type,
    data->>'rating' as rating,
    data->>'model_id' as model_id,
    created_at,
    updated_at
FROM feedback
WHERE 
    -- Rating is null or missing
    (data->>'rating' IS NULL OR data->>'rating' = 'null')
    -- OR model_id is null or missing
    OR (data->>'model_id' IS NULL OR data->>'model_id' = 'null')
    -- OR data itself is null
    OR data IS NULL
ORDER BY updated_at DESC;

-- Count how many corrupt rows exist
SELECT 
    COUNT(*) as corrupt_count
FROM feedback
WHERE 
    (data->>'rating' IS NULL OR data->>'rating' = 'null')
    OR (data->>'model_id' IS NULL OR data->>'model_id' = 'null')
    OR data IS NULL;

-- Optionally, delete corrupt feedback rows (UNCOMMENT TO USE):
-- DELETE FROM feedback
-- WHERE 
--     (data->>'rating' IS NULL OR data->>'rating' = 'null')
--     OR (data->>'model_id' IS NULL OR data->>'model_id' = 'null')
--     OR data IS NULL;

