with source as (
        select * from {{ source('todoist_raw', 'completed_tasks') }}
  ),
  renamed as (
      select
        user_id
        ,id
        ,project_id
        ,note_count
        ,section_id
        ,content
        ,completed_at
        ,notes
        ,task_id
        ,meta_data
        ,item_object

      from source
  ),
  cast_tz as (
      select 
      * except(
        completed_at
      ),
      DATETIME(completed_at, "{{var('timezone')}}") as completed_at

    from renamed

    )
  select 
  * from cast_tz
    