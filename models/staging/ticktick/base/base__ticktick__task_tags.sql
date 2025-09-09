WITH source AS (
    SELECT
    *
    FROM
    {{ source('ticktick_raw','tasks') }}

),

renamed as (
    select
      CAST(id AS STRING) as task_id,
      tags
      from source
),

unnested as (
    select
        task_id,
        tag
    from
        renamed,
        unnest(tags) as tag
)

SELECT
    *
FROM
    unnested