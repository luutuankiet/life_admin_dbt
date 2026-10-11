-- Shapes the dlt current-state task tables exactly like the legacy tasks_v3 external
-- table (ticktick_raw.tasks_v3), so base__ticktick_v3__tasks reads it unchanged.
-- Every field comes from raw_json: dlt renames typed columns (camelCase -> snake_case),
-- raw_json keeps TickTick's own names.
{%- set ts_fields = {
    'start_date': 'startDate',
    'due_date': 'dueDate',
    'repeat_first_date': 'repeatFirstDate',
    'completed_time': 'completedTime',
    'created_time': 'createdTime',
    'modified_time': 'modifiedTime',
} %}

WITH unioned AS (
    SELECT raw_json, _extracted_at, 0 AS source_rank
    FROM {{ source('ticktick_ingest', 'tasks') }}
    WHERE raw_json IS NOT NULL

    UNION ALL

    -- an old completed-history row must never override a newer sync-feed state (e.g. a reopen)
    SELECT raw_json, _extracted_at, 1 AS source_rank
    FROM {{ source('ticktick_ingest', 'closed_tasks') }}
    WHERE raw_json IS NOT NULL
),

typed AS (
    SELECT
        JSON_VALUE(raw_json, '$.id') AS task_id,
        'default' AS account_id,
        JSON_VALUE(raw_json, '$.projectId') AS project_id,
        SAFE_CAST(JSON_VALUE(raw_json, '$.sortOrder') AS INT64) AS sort_order,
        JSON_VALUE(raw_json, '$.title') AS title,
        JSON_VALUE(raw_json, '$.content') AS content,
        JSON_VALUE(raw_json, '$.timeZone') AS timezone,
        SAFE_CAST(JSON_VALUE(raw_json, '$.isFloating') AS BOOL) AS is_floating,
        SAFE_CAST(JSON_VALUE(raw_json, '$.isAllDay') AS BOOL) AS is_all_day,
        JSON_VALUE(raw_json, '$.reminder') AS reminder,
        SAFE_CAST(JSON_VALUE(raw_json, '$.priority') AS INT64) AS priority,
        SAFE_CAST(JSON_VALUE(raw_json, '$.status') AS INT64) AS status,
        -- hard deletes are already gone from the source tables; the column stays for shape
        0 AS deleted,
        SAFE_CAST(JSON_VALUE(raw_json, '$.progress') AS INT64) AS progress,
        {%- for col, key in ts_fields.items() %}
        -- TickTick writes yyyy-MM-ddTHH:mm:ss.SSS+0000
        SAFE.PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%E*S%z', JSON_VALUE(raw_json, '$.{{ key }}')) AS {{ col }},
        {%- endfor %}
        JSON_VALUE(raw_json, '$.repeatFlag') AS repeat_flag,
        JSON_VALUE(raw_json, '$.completedUserId') AS completed_user_id,
        SAFE_CAST(JSON_VALUE(raw_json, '$.creator') AS INT64) AS creator,
        JSON_VALUE(raw_json, '$.parentId') AS parent_id,
        JSON_VALUE(raw_json, '$.kind') AS kind,
        JSON_VALUE(raw_json, '$.columnId') AS column_id,
        JSON_VALUE(raw_json, '$.etag') AS etag,
        raw_json,
        _extracted_at AS updated_at,
        source_rank
    FROM unioned
),

deduped AS (
    SELECT *
    FROM typed
    WHERE task_id IS NOT NULL
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY task_id
        ORDER BY modified_time DESC NULLS LAST, source_rank ASC, updated_at DESC
    ) = 1
)

SELECT
    task_id,
    account_id,
    project_id,
    sort_order,
    title,
    content,
    timezone,
    is_floating,
    is_all_day,
    reminder,
    priority,
    status,
    deleted,
    progress,
    start_date,
    due_date,
    repeat_flag,
    repeat_first_date,
    completed_time,
    completed_user_id,
    creator,
    parent_id,
    created_time,
    modified_time,
    kind,
    column_id,
    etag,
    raw_json,
    updated_at
FROM deduped
-- after the dedup, so a task's newest state decides. Deleting a list leaves its tasks
-- behind: the change feed carries no task deletes for them. Inbox is not a list row;
-- stg adds it from the legacy projects source.
WHERE project_id IS NULL
    OR project_id LIKE 'inbox%'
    OR project_id IN (SELECT JSON_VALUE(raw_json, '$.id') FROM {{ source('ticktick_ingest', 'lists') }})
