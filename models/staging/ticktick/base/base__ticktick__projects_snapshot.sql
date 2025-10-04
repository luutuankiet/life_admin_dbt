WITH source AS (
    SELECT
        *
    FROM 
    {{source('ticktick_raw', 'projects_snapshot')}}
), 
renamed as (
    select 
NULLIF(cast(id as string),'') as project_id,
NULLIF(cast(name as string),'') as project_name,
cast(sortorder as INT64) as sort_order,
NULLIF(cast(groupid as string),'') as group_id,
NULLIF(cast(kind as string),'') as kind,
NULLIF(cast(color as string),'') as color,
NULLIF(cast(viewmode as string),'') as view_mode,
NULLIF(cast(permission as string),'') as permission,
cast(closed as boolean) as closed,
NULLIF(cast(dbt_scd_id as string),'') as dbt_scd_id,
DATETIME(cast(dbt_updated_at as timestamp), "{{var('timezone')}}") as dbt_updated_at,
DATETIME(cast(dbt_valid_from as timestamp), "{{var('timezone')}}") as dbt_valid_from,
DATETIME(cast(dbt_valid_to as timestamp), "{{var('timezone')}}") as dbt_valid_to

    from source
)
SELECT
    *
FROM
    renamed