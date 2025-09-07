{{ config(
    location='s3://ticktick_raw/todoist/archived_projects.jsonl',
) }}

with source as (
        select * from {{ source('todoist_stateless_raw', 'archived_projects') }}
  ),
  renamed as (
      select * 

      from source
  )
  select * from renamed
    