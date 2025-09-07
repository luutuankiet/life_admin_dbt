{{ config(
    location = 's3://' ~ env_var('GCS_RAW_BUCKET') ~ '/todoist/completed_tasks.jsonl'
) }}

with source as (
        select * from {{ source('todoist_stateless_raw', 'completed_tasks') }}
  ),
  renamed as (
      select *    

      from source
  )
  select * from renamed
    