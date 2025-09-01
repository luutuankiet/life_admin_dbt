WITH source AS (
    SELECT
    *
    FROM
    {{ source('raw_data','tasks') }}

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
      parse_timestamp("%FT%H:%M:%E3S%z",startdate) as start_date,
      parse_timestamp("%FT%H:%M:%E3S%z",duedate) as due_date,
      CAST(SPLIT(REGEXP_REPLACE(reminders, r"^\[|\]$|\'", ''), ',') as ARRAY<STRING>) as reminders,
      parse_timestamp("%FT%H:%M:%E3S%z",completedtime) as _completed_time,
      CAST(SPLIT(REGEXP_REPLACE(childids, r'^\[|\]$', ''), ',') as ARRAY<STRING>) as childids,
      CAST(parentid AS STRING) as parent_id
      from source
)

SELECT
    *
FROM
    renamed
