with source as (
        select * from {{ source('todoist_raw', 'archived_projects') }}
  ),
  renamed as (
      select
          *

      from source
  )
  select * from renamed
    