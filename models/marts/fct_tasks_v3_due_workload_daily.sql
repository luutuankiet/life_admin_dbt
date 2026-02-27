with date_spine as (
    select
        cast(date_day as date) as due_date_day,
        date_trunc(cast(date_day as date), week) as due_date_week,
        format_date('%A', cast(date_day as date)) as due_date_day_of_week_name,
        extract(month from cast(date_day as date)) as due_date_month_num,
        extract(day from cast(date_day as date)) as due_date_day_of_month_num
    from {{ ref('dim_date_spine') }}
),

project_catalog as (
    select distinct
        projects.project_id,
        coalesce(projects.project_name, projects.project_id, 'unknown_project') as project_name,
        case
            when coalesce(nullif(projects.group_id, ''), 'default') in ('0', 'default')
                or lower(coalesce(folders.folder_name, 'default')) = 'default'
                then 'default'
            else coalesce(nullif(projects.group_id, ''), 'default')
        end as folder_id,
        case
            when coalesce(nullif(projects.group_id, ''), 'default') in ('0', 'default')
                or lower(coalesce(folders.folder_name, 'default')) = 'default'
                then 'default'
            else coalesce(folders.folder_name, 'default')
        end as folder_name
    from {{ ref('dim_projects_v3') }} as projects
    left join {{ ref('dim_folders_v3') }} as folders
        on coalesce(nullif(projects.group_id, ''), 'default') = folders.folder_id
),

project_catalog_scoped as (
    select
        project_id,
        project_name,
        folder_id,
        folder_name,
        case
            when regexp_contains(
                lower(concat(folder_name, ' ', project_name)),
                r'(^|[^a-z0-9])joons([^a-z0-9]|$)'
            ) then 'joons'
            else 'rest'
        end as scope_bucket
    from project_catalog
),

project_calendar as (
    select
        date_spine.due_date_day,
        date_spine.due_date_week,
        date_spine.due_date_day_of_week_name,
        date_spine.due_date_month_num,
        date_spine.due_date_day_of_month_num,
        project_catalog_scoped.project_id,
        project_catalog_scoped.project_name,
        project_catalog_scoped.folder_id,
        project_catalog_scoped.folder_name,
        project_catalog_scoped.scope_bucket
    from date_spine
    cross join project_catalog_scoped
),

open_task_counts as (
    select
        due_date_day,
        project_id,
        count(distinct task_id) as open_task_count
    from {{ ref('fct_tasks_v3_semantic_base') }}
    where status != 2
      and due_date_day is not null
    group by 1, 2
)

select
    {{ dbt_utils.generate_surrogate_key(['cast(project_calendar.due_date_day as string)', 'project_calendar.project_id']) }} as due_workload_daily_id,
    project_calendar.due_date_day,
    project_calendar.due_date_week,
    project_calendar.due_date_day_of_week_name,
    project_calendar.due_date_month_num,
    project_calendar.due_date_day_of_month_num,
    project_calendar.scope_bucket,
    project_calendar.folder_id,
    project_calendar.folder_name,
    project_calendar.project_id,
    project_calendar.project_name,
    coalesce(open_task_counts.open_task_count, 0) as open_task_count,
    format(
        'ticktick.com/webapp/#p/%s/tasks',
        coalesce(project_calendar.project_id, 'unknown_project')
    ) as project_url_path,
    format(
        'ticktick.com/webapp/#g/%s',
        coalesce(project_calendar.folder_id, 'default')
    ) as folder_url_path,
    format(
        'https://ticktick.com/webapp/#p/%s/tasks',
        coalesce(project_calendar.project_id, 'unknown_project')
    ) as project_url_web,
    format(
        'ticktick://ticktick.com/webapp/#p/%s/tasks',
        coalesce(project_calendar.project_id, 'unknown_project')
    ) as project_url_native,
    format(
        'https://ticktick.com/webapp/#g/%s',
        coalesce(project_calendar.folder_id, 'default')
    ) as folder_url_web,
    format(
        'ticktick://ticktick.com/webapp/#g/%s',
        coalesce(project_calendar.folder_id, 'default')
    ) as folder_url_native
from project_calendar
left join open_task_counts
    on project_calendar.due_date_day = open_task_counts.due_date_day
    and project_calendar.project_id = open_task_counts.project_id