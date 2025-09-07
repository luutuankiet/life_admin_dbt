{{ config(
    location='s3://ticktick_raw/todoist/active_tasks.jsonl',
) }}

with source as (
        select * from {{ source('todoist_stateless_raw', 'active_tasks') }}
  ),
  renamed as (
      select *

      from source
  )
  select * from renamed
    