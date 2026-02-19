with source as (
    select
        {{ dbt_utils.star(from=ref('base__ticktick_v3__projects'), except=['closed', 'modified_time']) }},
        case
            when coalesce(closed, false) then modified_time
            else cast(NULL as DATETIME)
        end as completed_time,
        coalesce(closed, false) as closed
    from {{ ref('base__ticktick_v3__projects') }}
),

legacy_inbox_projects as (
    select distinct
        cast(legacy.id as string) as project_id,
        regexp_extract(cast(legacy.id as string), r'^inbox(.*)$') as account_id,
        nullif(cast(legacy.name as string), '') as project_name,
        safe_cast(legacy.sortOrder as int64) as sort_order,
        nullif(cast(legacy.groupId as string), '') as group_id,
        nullif(cast(legacy.kind as string), '') as kind,
        nullif(cast(legacy.color as string), '') as color,
        nullif(cast(legacy.viewMode as string), '') as view_mode,
        nullif(cast(legacy.permission as string), '') as permission,
        cast(NULL as string) as etag,
        cast(NULL as string) as raw_json,
        cast(NULL as DATETIME) as updated_at,
        cast(NULL as DATETIME) as completed_time,
        false as closed
    from {{ source('ticktick_raw', 'projects') }} as legacy
    where cast(legacy.id as string) like 'inbox%'
      and not exists (
          select 1
          from source
          where source.project_id = cast(legacy.id as string)
      )
),

projects_with_inbox as (
    select * from source
    union all
    select * from legacy_inbox_projects
),

coalesce_null_group_ids as (
    select
        * except(group_id),
        coalesce(group_id, 'default') as group_id
    from projects_with_inbox
),

add_last_pulse as (
    select
        coalesce(pulse.due_date, pulse.completed_time) as last_pulse,
        project.*
    from coalesce_null_group_ids project
    left join (
        select
            project_id,
            max(completed_time) as completed_time,
            max(due_date) as due_date
        from {{ ref('stg__ticktick_v3__tasks') }}
        group by project_id
    ) as pulse
    on project.project_id = pulse.project_id
)

select
    *
from add_last_pulse