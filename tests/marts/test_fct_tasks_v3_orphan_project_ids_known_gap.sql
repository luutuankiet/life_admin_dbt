{{ config(severity='warn') }}

with orphaned as (
    select
        base.project_id,
        count(*) as row_count,
        min(base.due_date_day) as earliest_due_date_day,
        max(base.due_date_day) as latest_due_date_day
    from {{ ref('fct_tasks_v3_semantic_base') }} as base
    left join {{ ref('dim_projects_v3') }} as projects
        on base.project_id = projects.project_id
    where base.project_id is not null
      and projects.project_id is null
    group by 1
)

select *
from orphaned