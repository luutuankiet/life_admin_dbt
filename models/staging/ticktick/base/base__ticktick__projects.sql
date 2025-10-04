WITH source AS (
    SELECT
        *
    FROM 
    {{source('ticktick_raw', 'projects')}}
), 
renamed as (
    select 
NULLIF(cast(id as string), '') as project_id,
NULLIF(cast(name as string), '') as project_name,
cast(sortorder as INT64) as sort_order,
NULLIF(cast(groupid as string), '') as group_id,
NULLIF(cast(kind as string), '') as kind,
NULLIF(cast(color as string), '') as color,
NULLIF(cast(viewmode as string), '') as view_mode,
NULLIF(cast(permission as string), '') as permission,
cast(closed as boolean) as closed

    from source
)
SELECT
    *
FROM
    renamed