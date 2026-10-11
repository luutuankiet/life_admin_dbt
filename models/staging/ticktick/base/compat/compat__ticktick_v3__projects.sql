-- Shapes the dlt lists table exactly like the legacy projects_v3 external table.
-- Fields come from raw_json, which keeps TickTick's own key names.
SELECT
    JSON_VALUE(raw_json, '$.id') AS project_id,
    'default' AS account_id,
    JSON_VALUE(raw_json, '$.name') AS name,
    JSON_VALUE(raw_json, '$.groupId') AS group_id,
    -- archived lists carry closed: true; unarchive stores null
    IF(SAFE_CAST(JSON_VALUE(raw_json, '$.closed') AS BOOL), 1, 0) AS closed,
    SAFE_CAST(JSON_VALUE(raw_json, '$.sortOrder') AS INT64) AS sort_order,
    JSON_VALUE(raw_json, '$.kind') AS kind,
    JSON_VALUE(raw_json, '$.viewMode') AS view_mode,
    SAFE.PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%E*S%z', JSON_VALUE(raw_json, '$.modifiedTime')) AS modified_time,
    JSON_VALUE(raw_json, '$.etag') AS etag,
    raw_json,
    _extracted_at AS updated_at
FROM {{ source('ticktick_ingest', 'lists') }}
WHERE raw_json IS NOT NULL
