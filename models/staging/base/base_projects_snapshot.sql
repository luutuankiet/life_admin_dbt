WITH source AS (
    SELECT
        *
    FROM 
    {{source('raw_data', 'projects_snapshot')}}
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
cast(closed as boolean) as closed,
cast(dbt_scd_id as string) as dbt_scd_id,
cast(dbt_updated_at as timestamp) as dbt_updated_at,
cast(dbt_valid_from as timestamp) as dbt_valid_from,
cast(dbt_valid_to as timestamp) as dbt_valid_to,

    from source
)
SELECT
    *
FROM
    renamed