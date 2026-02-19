WITH source AS (
    SELECT
        *
    FROM {{ source('ticktick_raw', 'groups_v3') }}
),

renamed_and_typed AS (
    SELECT
        NULLIF(CAST(group_id AS STRING), '') AS group_id,
        NULLIF(CAST(account_id AS STRING), '') AS account_id,
        NULLIF(CAST(name AS STRING), '') AS group_name,
        CASE
            WHEN SAFE_CAST(deleted AS INT64) IS NOT NULL THEN SAFE_CAST(deleted AS INT64) = 1
            ELSE SAFE_CAST(JSON_VALUE(raw_json, '$.deleted') AS BOOL)
        END AS deleted,
        COALESCE(SAFE_CAST(sort_order AS INT64), SAFE_CAST(JSON_VALUE(raw_json, '$.sortOrder') AS INT64)) AS sort_order,
        NULLIF(CAST(sort_type AS STRING), '') AS sort_type,
        NULLIF(CAST(JSON_VALUE(raw_json, '$.viewMode') AS STRING), '') AS view_mode,
        NULLIF(CAST(etag AS STRING), '') AS etag,
        SAFE_CAST(updated_at AS TIMESTAMP) AS updated_at,
        raw_json
    FROM source
),

cast_tz AS (
    SELECT
        * EXCEPT (updated_at),
        DATETIME(updated_at, "{{ var('timezone') }}") AS updated_at
    FROM renamed_and_typed
)

SELECT
    *
FROM cast_tz