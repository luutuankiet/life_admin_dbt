-- Shapes the dlt folders table exactly like the legacy groups_v3 external table.
-- Fields come from raw_json, which keeps TickTick's own key names.
SELECT
    JSON_VALUE(raw_json, '$.id') AS group_id,
    'default' AS account_id,
    JSON_VALUE(raw_json, '$.name') AS name,
    SAFE_CAST(JSON_VALUE(raw_json, '$.deleted') AS INT64) AS deleted,
    SAFE_CAST(JSON_VALUE(raw_json, '$.sortOrder') AS INT64) AS sort_order,
    JSON_VALUE(raw_json, '$.sortType') AS sort_type,
    JSON_VALUE(raw_json, '$.etag') AS etag,
    raw_json,
    _extracted_at AS updated_at
FROM {{ source('ticktick_ingest', 'folders') }}
WHERE raw_json IS NOT NULL
