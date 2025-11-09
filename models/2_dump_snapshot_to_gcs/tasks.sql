{{ config(
    materialized='external',
    location='s3://' ~ env_var('GCS_RAW_BUCKET') ~ '/ticktick/tasks.jsonl',
    enabled=(target.name == 'dump_snapshot')
) }}

with src as (
    select *, null as parentId from {{source('stateless_raw','tasks')}}
)

{# add_load_time as (
    -- add a dummy row to "load" the snapshot runtime to the table
    select 
        -- dummy id
        0 as id,
        NULL as projectId,
        NULL as sortOrder,
        NULL as title,
        NULL as timeZone,
        NULL as isAllDay,
        NULL as priority,
        NULL as status,
        NULL as tags,
        NULL as columnId,
        NULL as etag,
        NULL as kind,
        NULL as repeatFlag,
        NULL as startDate,
        NULL as dueDate,
        NULL as reminders,
        -- inject load time. needs to format it like so
        -- 2025-09-03T13:20:30.066000+00
        SUBSTRING(strftime(now() AT TIME ZONE 'UTC', '%Y-%m-%dT%H:%M:%S.%f'), 1, 23 ) || '+0000' as completedTime,
        NULL as childIds,
        NULL as parentId
),

unioned as (
    select * from src 
    UNION ALL
    select * from add_load_time
) #}


select * from src