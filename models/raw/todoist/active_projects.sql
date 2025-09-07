{{ config(
    location='s3://ticktick_raw/todoist/active_projects.jsonl',
) }}

with source as (
        select * from {{ source('todoist_stateless_raw', 'active_projects') }}
  ),
  renamed as (
    select *
          

      from source
  )
  select * from renamed
    