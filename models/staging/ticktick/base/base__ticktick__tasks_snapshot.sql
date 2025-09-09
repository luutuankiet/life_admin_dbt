WITH source AS (
    SELECT
    *
    FROM
    {{ source('ticktick_raw','tasks_snapshot') }}

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
      CAST(parentid AS STRING) as parent_id,
      CAST(dbt_scd_id AS STRING) as dbt_scd_id,
      CAST(dbt_updated_at AS TIMESTAMP) as dbt_updated_at,
      CAST(dbt_valid_from AS TIMESTAMP) as dbt_valid_from,
      CAST(dbt_valid_to AS TIMESTAMP) as dbt_valid_to
      from source
),

cast_tz as (
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
        DATETIME(_completed_time, "{{var('timezone')}}") as _completed_time,
        dbt_scd_id,
        DATETIME(dbt_updated_at, "{{var('timezone')}}") as dbt_updated_at,
        DATETIME(dbt_valid_from, "{{var('timezone')}}") as dbt_valid_from,
        DATETIME(dbt_valid_to, "{{var('timezone')}}") as dbt_valid_to

      from renamed
)

SELECT
    *
FROM
    cast_tz