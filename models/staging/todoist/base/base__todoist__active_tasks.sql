with source as (
        select * from {{ source('todoist_raw', 'active_tasks') }}
  ),
  renamed as (
      select
        user_id
        ,id
        ,project_id
        ,note_count
        ,section_id
        ,content
        ,cast(completed_at as timestamp) as completed_at
        ,assigned_by_uid
        ,description
        ,priority
        ,responsible_uid
        ,updated_at
        ,checked
        ,added_at
        ,is_collapsed
        ,deadline
        ,parent_id
        ,day_order
        ,added_by_uid
        ,is_deleted
        ,duration
        ,child_order
        ,labels
        ,due.is_recurring as due_is_recurring
        ,due.lang as due_lang
        ,due.timezone as due_timezone
        ,due.string as due_string
        ,cast(due.date as timestamp) as due_date

      from source
  ),

  cast_tz as (
    select 
    * except(
      completed_at,
      updated_at,
      added_at,
      due_date
    ),
      DATETIME(completed_at, "{{var('timezone')}}") as completed_at,
      DATETIME(updated_at, "{{var('timezone')}}") as updated_at,
      DATETIME(added_at, "{{var('timezone')}}") as added_at,
      DATETIME(due_date, "{{var('timezone')}}") as due_date

  from renamed

  )
  select * from cast_tz
    