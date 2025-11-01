with source as (
        select * from {{ source('todoist_raw', 'active_projects') }}
  ),
  renamed as (
      select
        parent_id
        ,is_collapsed
        ,role
        ,public_key
        ,inbox_project
        ,view_style
        ,updated_at
        ,is_shared
        ,default_order
        ,name
        ,is_deleted
        ,public_access
        ,is_archived
        ,description
        ,color
        ,creator_uid
        ,is_frozen
        ,child_order
        ,created_at
        ,can_assign_tasks
        ,is_favorite
        ,id

      from source
  )
  select * from renamed
    