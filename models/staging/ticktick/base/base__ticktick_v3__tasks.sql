WITH source AS (
    SELECT
        *
    FROM {{ source('ticktick_raw', 'tasks_v3') }}
),

renamed_and_typed AS (
    SELECT
        NULLIF(CAST(task_id AS STRING), '') AS task_id,
        NULLIF(CAST(account_id AS STRING), '') AS account_id,
        NULLIF(CAST(project_id AS STRING), '') AS project_id,
        COALESCE(SAFE_CAST(sort_order AS INT64), SAFE_CAST(JSON_VALUE(raw_json, '$.sortOrder') AS INT64)) AS sort_order,
        NULLIF(CAST(title AS STRING), '') AS title,
        NULLIF(CAST(content AS STRING), '') AS content,
        COALESCE(NULLIF(CAST(timezone AS STRING), ''), NULLIF(CAST(JSON_VALUE(raw_json, '$.timeZone') AS STRING), '')) AS timezone,
        COALESCE(SAFE_CAST(is_all_day AS BOOL), SAFE_CAST(JSON_VALUE(raw_json, '$.isAllDay') AS BOOL)) AS is_allday,
        COALESCE(SAFE_CAST(is_floating AS BOOL), SAFE_CAST(JSON_VALUE(raw_json, '$.isFloating') AS BOOL)) AS is_floating,
        COALESCE(NULLIF(CAST(reminder AS STRING), ''), NULLIF(CAST(JSON_VALUE(raw_json, '$.reminder') AS STRING), '')) AS reminder,
        COALESCE(SAFE_CAST(priority AS INT64), SAFE_CAST(JSON_VALUE(raw_json, '$.priority') AS INT64)) AS priority,
        COALESCE(SAFE_CAST(progress AS INT64), SAFE_CAST(JSON_VALUE(raw_json, '$.progress') AS INT64)) AS progress,
        SAFE_CAST(status AS INT64) AS status,
        SAFE_CAST(deleted AS INT64) AS deleted,
        NULLIF(CAST(column_id AS STRING), '') AS column_id,
        NULLIF(CAST(etag AS STRING), '') AS etag,
        NULLIF(CAST(kind AS STRING), '') AS kind,
        COALESCE(NULLIF(CAST(repeat_flag AS STRING), ''), NULLIF(CAST(JSON_VALUE(raw_json, '$.repeatFlag') AS STRING), '')) AS repeat_flag,
        COALESCE(SAFE_CAST(start_date AS TIMESTAMP), SAFE_CAST(JSON_VALUE(raw_json, '$.startDate') AS TIMESTAMP)) AS start_date,
        COALESCE(SAFE_CAST(due_date AS TIMESTAMP), SAFE_CAST(JSON_VALUE(raw_json, '$.dueDate') AS TIMESTAMP)) AS due_date,
        COALESCE(SAFE_CAST(repeat_first_date AS TIMESTAMP), SAFE_CAST(JSON_VALUE(raw_json, '$.repeatFirstDate') AS TIMESTAMP)) AS repeat_first_date,
        COALESCE(SAFE_CAST(completed_time AS TIMESTAMP), SAFE_CAST(JSON_VALUE(raw_json, '$.completedTime') AS TIMESTAMP)) AS _completed_time,
        NULLIF(CAST(completed_user_id AS STRING), '') AS completed_user_id,
        SAFE_CAST(creator AS INT64) AS creator,
        SAFE_CAST(created_time AS TIMESTAMP) AS created_time,
        SAFE_CAST(modified_time AS TIMESTAMP) AS modified_time,
        SAFE_CAST(updated_at AS TIMESTAMP) AS updated_at,
        COALESCE(NULLIF(CAST(parent_id AS STRING), ''), NULLIF(CAST(JSON_VALUE(raw_json, '$.parentId') AS STRING), '')) AS parent_id,
        ARRAY(
            SELECT item
            FROM UNNEST(IFNULL(JSON_VALUE_ARRAY(raw_json, '$.tags'), [])) AS item
            WHERE TRIM(item) != ''
        ) AS tags,
        ARRAY(
            SELECT item
            FROM UNNEST(IFNULL(JSON_VALUE_ARRAY(raw_json, '$.childIds'), [])) AS item
            WHERE TRIM(item) != ''
        ) AS childids,
        ARRAY(
            SELECT item
            FROM UNNEST(IFNULL(JSON_VALUE_ARRAY(raw_json, '$.reminders'), [])) AS item
            WHERE TRIM(item) != ''
        ) AS reminders,
        raw_json
    FROM source
),

cast_tz AS (
    SELECT
        * EXCEPT (start_date, due_date, repeat_first_date, _completed_time, created_time, modified_time, updated_at),
        DATETIME(start_date, "{{ var('timezone') }}") AS start_date,
        DATETIME(due_date, "{{ var('timezone') }}") AS due_date,
        DATETIME(repeat_first_date, "{{ var('timezone') }}") AS repeat_first_date,
        DATETIME(_completed_time, "{{ var('timezone') }}") AS _completed_time,
        DATETIME(created_time, "{{ var('timezone') }}") AS created_time,
        DATETIME(modified_time, "{{ var('timezone') }}") AS modified_time,
        DATETIME(updated_at, "{{ var('timezone') }}") AS updated_at
    FROM renamed_and_typed
)

SELECT
    *
FROM cast_tz