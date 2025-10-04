WITH source AS (
    SELECT
    *
    FROM
    {{ source('ticktick_raw','tasks') }}

),

renamed_and_typed as (
    select
      NULLIF(CAST(id AS STRING),'') as task_id,
      NULLIF(CAST(projectid AS STRING),'') as project_id,
      CAST(sortorder AS INT) as sort_order,
      NULLIF(CAST(title AS STRING),'') as title,
      NULLIF(CAST(timezone AS STRING),'') as timezone,
      CAST(isallday AS BOOLEAN) as is_allday,
      CAST(priority AS INT) as priority,
      CAST(status AS INT) as status,
      NULLIF(CAST(columnid AS STRING),'') as column_id,
      NULLIF(CAST(etag AS STRING),'') as etag,
      NULLIF(CAST(kind AS STRING),'') as kind,
      NULLIF(CAST(repeatflag AS STRING),'') as repeat_flag,
      startdate as start_date,
      duedate as due_date,
      completedtime as _completed_time,
      NULLIF(CAST(parentid AS STRING),'') as parent_id,

      -- NULLIF for typed array
      ARRAY(
        SELECT item
        FROM UNNEST(tags) as item
        WHERE trim(item) != ''
        ) as tags,
      ARRAY(
        SELECT item
        FROM UNNEST(childids) as item
        WHERE trim(item) != ''
        ) as childids,
      ARRAY(
        SELECT item
        FROM UNNEST(reminders) as item
        WHERE trim(item) != ''
        ) as reminders
      from source
),

cast_tz as(
    select
        * except (start_date, due_date, _completed_time),
        DATETIME(start_date, "{{var('timezone')}}") as start_date,
        DATETIME(due_date, "{{var('timezone')}}") as due_date,
        DATETIME(_completed_time, "{{var('timezone')}}") as _completed_time
      from renamed_and_typed

)

SELECT
    *
FROM
    cast_tz