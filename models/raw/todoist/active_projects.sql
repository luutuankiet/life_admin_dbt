{{ config(
    location = 's3://' ~ env_var('GCS_RAW_BUCKET') ~ '/todoist/active_projects.jsonl'
) }}

with source as (
        select * from {{ source('todoist_stateless_raw', 'active_projects') }}
  ),
  renamed as (
    select *
          

      from source
  )
  select * from renamed
    