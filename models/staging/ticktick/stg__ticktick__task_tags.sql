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
),

task_without_tags as (
    -- unnest above dont really work if 
    -- the tags array len = 0 i.e.
    -- the task do not have any tags.
    select 
        task_id,
        'default' as tag
    from renamed
    where ARRAY_LENGTH(tags) = 0
),

unioned as (
    select * from unnested
    UNION ALL
    select * from task_without_tags

)

SELECT
    *
FROM
    unioned