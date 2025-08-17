WITH source AS (
    SELECT
        *
    FROM
        {{ source(
            'raw_data',
            'projects'
        ) }}
)
SELECT
    *
FROM
    source