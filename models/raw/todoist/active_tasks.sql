{{ config(
    location = 's3://' ~ env_var('GCS_RAW_BUCKET') ~ '/todoist/active_tasks.jsonl'
) }}

with source as (
        select * from {{ source('todoist_stateless_raw', 'active_tasks') }}
  ),
  renamed as (
      select *

      from source
  )
  select * from renamed
    