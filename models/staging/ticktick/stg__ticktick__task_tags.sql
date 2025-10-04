WITH source AS (
    SELECT
    *
    FROM
    {{ ref('stg__ticktick__tasks') }}
),

renamed as (
    select
      task_id,
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