WITH source AS (
    SELECT
    *
    FROM
    {{ source('ticktick_raw','tasks_snapshot') }}

),

renamed_and_typed as (
    -- one caveat with having duckdb dumping 
    -- snapshots to gcs is that BQ tries to 
    -- guess the data types, which is unreliable.
    -- we gonna explicitly type them in this step.
    select
      NULLIF(CAST(id AS STRING), '') as task_id,
      NULLIF(CAST(projectid AS STRING), '') as project_id,
      CAST(sortorder AS INT) as sort_order,
      NULLIF(CAST(title AS STRING), '') as title,
      NULLIF(CAST(timezone AS STRING), '') as timezone,
      CAST(isallday AS BOOLEAN) as is_allday,
      CAST(priority AS INT) as priority,
      CAST(status AS INT) as status,
      NULLIF(CAST(columnid AS STRING), '') as column_id,
      NULLIF(CAST(etag AS STRING), '') as etag,
      NULLIF(CAST(kind AS STRING), '') as kind,
      NULLIF(CAST(repeatflag AS STRING), '') as repeat_flag,
      startdate as start_date,
      duedate as due_date,
      -- reminders value are wrapped in single quotes
      -- i.e. malformed json array : ['val1','val2']
      -- so needs to replace them too
      ARRAY(
          SELECT item 
          FROM UNNEST(SPLIT(REGEXP_REPLACE(reminders, r"^\[|\]$|\'", ''))) as item
          WHERE trim(item) != ''
      ) as reminders,
      completedtime as _completed_time,
      -- these are malformed JSON array : [val1,val2].
      -- we have 2 options; either parse array<JSON-string> or just parse as ARRAY<string>.
      -- go with options 2 because our data is flat no nested here.
      ARRAY(
          SELECT item 
          FROM UNNEST(SPLIT(REGEXP_REPLACE(childids, r'^\[|\]$', ''))) as item
          WHERE trim(item) != ''
      ) as childids,
            
      -- column `tags`
      ARRAY(
          SELECT item 
          FROM UNNEST(SPLIT(REGEXP_REPLACE(tags, r'^\[|\]$', ''))) as item
          WHERE trim(item) != ''
      ) as tags,
      NULLIF(CAST(parentid AS STRING), '') as parent_id,
      NULLIF(CAST(dbt_scd_id AS STRING), '') as dbt_scd_id,
      CAST(dbt_updated_at AS TIMESTAMP) as dbt_updated_at,
      CAST(dbt_valid_from AS TIMESTAMP) as dbt_valid_from,
      CAST(dbt_valid_to AS TIMESTAMP) as dbt_valid_to
      from source
),

cast_tz as (
    select
    * except(
        start_date, due_date, _completed_time,
        dbt_updated_at, dbt_valid_from, dbt_valid_to
    ),

        DATETIME(start_date, "{{var('timezone')}}") as start_date,
        DATETIME(due_date, "{{var('timezone')}}") as due_date,
        DATETIME(_completed_time, "{{var('timezone')}}") as _completed_time,
        DATETIME(dbt_updated_at, "{{var('timezone')}}") as dbt_updated_at,
        DATETIME(dbt_valid_from, "{{var('timezone')}}") as dbt_valid_from,
        DATETIME(dbt_valid_to, "{{var('timezone')}}") as dbt_valid_to

      from renamed_and_typed
)

SELECT
    *
FROM
    cast_tz