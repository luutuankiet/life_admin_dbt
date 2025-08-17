WITH source AS (
    SELECT
        {{ select_source_columns(source('raw_data', 'tasks')) }}
    FROM
        {{ source(
            'raw_data',
            'tasks'
        ) }}
)
SELECT
    *
FROM
    source