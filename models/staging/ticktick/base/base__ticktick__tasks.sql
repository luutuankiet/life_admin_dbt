WITH source AS (
    SELECT
    *
    FROM
    {{ source('ticktick_raw','tasks') }}

),

renamed as (
    select
      CAST(id AS STRING) as task_id,
      CAST(projectid AS STRING) as project_id,
      CAST(sortorder AS INT) as sort_order,
      CAST(title AS STRING) as title,
      CAST(timezone AS STRING) as timezone,
      CAST(isallday AS BOOLEAN) as is_allday,
      CAST(priority AS INT) as priority,
      CAST(status AS INT) as status,
      tags as tags,
      CAST(columnid AS STRING) as column_id,
      CAST(etag AS STRING) as etag,
      CAST(kind AS STRING) as kind,
      CAST(repeatflag AS STRING) as repeat_flag,
      startdate as start_date,
      duedate as due_date,
      reminders as reminders,
      completedtime as _completed_time,
      childids as childids,
      CAST(parentid AS STRING) as parent_id
      from source
),

cast_tz as(
    select
        task_id,
        project_id,
        sort_order,
        title,
        timezone,
        is_allday,
        priority,
        status,
        tags,
        column_id,
        etag,
        kind,
        repeat_flag,
        reminders,
        childids,
        parent_id,
        DATETIME(start_date, "{{var('timezone')}}") as start_date,
        DATETIME(due_date, "{{var('timezone')}}") as due_date,
        DATETIME(_completed_time, "{{var('timezone')}}") as _completed_time
      from renamed

)

SELECT
    *
FROM
    cast_tz