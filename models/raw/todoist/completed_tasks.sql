{{ config(
    location='s3://ticktick_raw/todoist/completed_tasks.jsonl',
) }}

with source as (
        select * from {{ source('todoist_stateless_raw', 'completed_tasks') }}
  ),
  renamed as (
      select *    

      from source
  )
  select * from renamed
    