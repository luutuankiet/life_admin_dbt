with tasks as (
    select
        task_id,
        project_id,
        title,
        due_date,
        completed_time,
        updated_time,
        status,
        gtd_work_type
    from {{ ref('stg__ticktick_v3__tasks') }}
),

projects as (
    select
        project_id,
        project_name,
        coalesce(nullif(group_id, ''), 'default') as raw_folder_id
    from {{ ref('dim_projects_v3') }}
),

folders as (
    select
        folder_id,
        folder_name
    from {{ ref('dim_folders_v3') }}
),

joined as (
    select
        tasks.task_id,
        tasks.project_id,
        coalesce(projects.project_name, tasks.project_id, 'unknown_project') as project_name,
        projects.raw_folder_id,
        coalesce(folders.folder_name, 'default') as raw_folder_name,
        tasks.title,
        tasks.due_date,
        cast(tasks.due_date as date) as due_date_day,
        date_trunc(cast(tasks.due_date as date), week) as due_date_week,
        format_date('%A', cast(tasks.due_date as date)) as due_date_day_of_week_name,
        extract(month from cast(tasks.due_date as date)) as due_date_month_num,
        extract(day from cast(tasks.due_date as date)) as due_date_day_of_month_num,
        tasks.completed_time,
        cast(tasks.completed_time as date) as completed_time_day,
        format_date('%A', cast(tasks.completed_time as date)) as completed_time_day_of_week_name,
        tasks.updated_time,
        tasks.status,
        tasks.gtd_work_type
    from tasks
    left join projects
        on tasks.project_id = projects.project_id
    left join folders
        on projects.raw_folder_id = folders.folder_id
),

normalized as (
    select
        task_id,
        project_id,
        project_name,
        case
            when raw_folder_id in ('0', 'default') or lower(raw_folder_name) = 'default' then 'default'
            when raw_folder_id is null then 'default'
            else raw_folder_id
        end as folder_id,
        case
            when raw_folder_id in ('0', 'default') or lower(raw_folder_name) = 'default' then 'default'
            when raw_folder_name is null then 'default'
            else raw_folder_name
        end as folder_name,
        title,
        due_date,
        due_date_day,
        due_date_week,
        due_date_day_of_week_name,
        due_date_month_num,
        due_date_day_of_month_num,
        completed_time,
        completed_time_day,
        completed_time_day_of_week_name,
        updated_time,
        status,
        gtd_work_type
    from joined
),

scoped as (
    select
        *,
        case
            when regexp_contains(
                lower(concat(folder_name, ' ', project_name)),
                r'(^|[^a-z0-9])joons([^a-z0-9]|$)'
            ) then 'joons'
            else 'rest'
        end as scope_bucket
    from normalized
)

select
    task_id,
    project_id,
    project_name,
    folder_id,
    folder_name,
    title,
    due_date,
    due_date_day,
    due_date_week,
    due_date_day_of_week_name,
    due_date_month_num,
    due_date_day_of_month_num,
    completed_time,
    completed_time_day,
    completed_time_day_of_week_name,
    updated_time,
    status,
    gtd_work_type,
    scope_bucket,
    format(
        'ticktick.com/webapp/#p/%s/tasks/%s',
        coalesce(project_id, 'unknown_project'),
        coalesce(task_id, 'unknown_task')
    ) as task_url_path,
    format(
        'ticktick.com/webapp/#p/%s/tasks',
        coalesce(project_id, 'unknown_project')
    ) as project_url_path,
    format(
        'ticktick.com/webapp/#g/%s',
        coalesce(folder_id, 'default')
    ) as folder_url_path,
    format(
        'https://ticktick.com/webapp/#p/%s/tasks/%s',
        coalesce(project_id, 'unknown_project'),
        coalesce(task_id, 'unknown_task')
    ) as task_url_web,
    format(
        'ticktick://ticktick.com/webapp/#p/%s/tasks/%s',
        coalesce(project_id, 'unknown_project'),
        coalesce(task_id, 'unknown_task')
    ) as task_url_native,
    format(
        'https://ticktick.com/webapp/#p/%s/tasks',
        coalesce(project_id, 'unknown_project')
    ) as project_url_web,
    format(
        'ticktick://ticktick.com/webapp/#p/%s/tasks',
        coalesce(project_id, 'unknown_project')
    ) as project_url_native,
    format(
        'https://ticktick.com/webapp/#g/%s',
        coalesce(folder_id, 'default')
    ) as folder_url_web,
    format(
        'ticktick://ticktick.com/webapp/#g/%s',
        coalesce(folder_id, 'default')
    ) as folder_url_native
from scoped