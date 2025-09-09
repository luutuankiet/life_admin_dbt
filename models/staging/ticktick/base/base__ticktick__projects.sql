WITH source AS (
    SELECT
        *
    FROM 
    {{source('ticktick_raw', 'projects')}}
), 
renamed as (
    select 
cast(id as string) as project_id,
cast(name as string) as project_name,
cast(sortorder as INT64) as sort_order,
cast(groupid as string) as group_id,
cast(kind as string) as kind,
cast(color as string) as color,
cast(viewmode as string) as view_mode,
cast(permission as string) as permission,
cast(closed as boolean) as closed

    from source
)
SELECT
    *
FROM
    renamed