WITH source AS (
    SELECT
    *
    FROM
    {{ source('raw_data','tasks_snapshot') }}

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
      CAST(SPLIT(REGEXP_REPLACE(tags, r'^\[|\]$', ''), ',') as ARRAY<STRING>) as tags,
      CAST(columnid AS STRING) as column_id,
      CAST(etag AS STRING) as etag,
      CAST(kind AS STRING) as kind,
      CAST(repeatflag AS STRING) as repeat_flag,
      parse_timestamp("%F %T%z",startdate) as start_date,
      parse_timestamp("%F %T%z",duedate) as due_date,
      CAST(SPLIT(REGEXP_REPLACE(reminders, r"^\[|\]$|\'", ''), ',') as ARRAY<STRING>) as reminders,
      parse_timestamp("%F %T%z",completedtime) as _completed_time,
      CAST(SPLIT(REGEXP_REPLACE(childids, r'^\[|\]$', ''), ',') as ARRAY<STRING>) as childids,
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
        {{ dbt_date.convert_timezone("start_date", target_tz=var('timezone')) }} as start_date,
        {{ dbt_date.convert_timezone("due_date", target_tz=var('timezone')) }} as due_date,
        {{ dbt_date.convert_timezone("_completed_time", target_tz=var('timezone')) }} as _completed_time,
        dbt_scd_id,
        {{ dbt_date.convert_timezone("dbt_updated_at", target_tz=var('timezone')) }} as dbt_updated_at,
        {{ dbt_date.convert_timezone("dbt_valid_from", target_tz=var('timezone')) }} as dbt_valid_from,
        {{ dbt_date.convert_timezone("dbt_valid_to", target_tz=var('timezone')) }} as dbt_valid_to

      from renamed
)

SELECT
    *
FROM
    cast_tz