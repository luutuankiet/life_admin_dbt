with open_tasks as (
    select
        task_id,
        title,
        project_id,
        project_name,
        folder_id,
        folder_name,
        due_date_day,
        due_date_week,
        due_date_day_of_week_name,
        due_date_month_num,
        due_date_day_of_month_num,
        scope_bucket,
        task_url_path,
        task_url_web,
        task_url_native,
        project_url_path,
        project_url_web,
        project_url_native,
        folder_url_path,
        folder_url_web,
        folder_url_native
    from {{ ref('fct_tasks_v3_semantic_base') }}
    where status != 2
      and due_date_day is not null
),

task_level as (
    select
        due_date_day,
        due_date_week,
        due_date_day_of_week_name,
        due_date_month_num,
        due_date_day_of_month_num,
        scope_bucket,
        folder_id,
        folder_name,
        project_id,
        project_name,
        'task' as grain_level,
        task_id as grain_id,
        coalesce(title, task_id, 'untitled_task') as grain_label,
        project_id as parent_grain_id,
        project_name as parent_grain_label,
        task_url_path as grain_url_path,
        task_url_web as grain_url_web,
        task_url_native as grain_url_native,
        project_url_path as parent_grain_url_path,
        project_url_web as parent_grain_url_web,
        project_url_native as parent_grain_url_native,
        count(distinct task_id) as task_count
    from open_tasks
    group by
        due_date_day,
        due_date_week,
        due_date_day_of_week_name,
        due_date_month_num,
        due_date_day_of_month_num,
        scope_bucket,
        folder_id,
        folder_name,
        project_id,
        project_name,
        task_id,
        title,
        task_url_path,
        task_url_web,
        task_url_native,
        project_url_path,
        project_url_web,
        project_url_native
),

project_level as (
    select
        due_date_day,
        due_date_week,
        due_date_day_of_week_name,
        due_date_month_num,
        due_date_day_of_month_num,
        scope_bucket,
        folder_id,
        folder_name,
        project_id,
        project_name,
        'project' as grain_level,
        project_id as grain_id,
        project_name as grain_label,
        folder_id as parent_grain_id,
        folder_name as parent_grain_label,
        project_url_path as grain_url_path,
        project_url_web as grain_url_web,
        project_url_native as grain_url_native,
        folder_url_path as parent_grain_url_path,
        folder_url_web as parent_grain_url_web,
        folder_url_native as parent_grain_url_native,
        count(distinct task_id) as task_count
    from open_tasks
    group by
        due_date_day,
        due_date_week,
        due_date_day_of_week_name,
        due_date_month_num,
        due_date_day_of_month_num,
        scope_bucket,
        folder_id,
        folder_name,
        project_id,
        project_name,
        project_url_path,
        project_url_web,
        project_url_native,
        folder_url_path,
        folder_url_web,
        folder_url_native
),

folder_level as (
    select
        due_date_day,
        due_date_week,
        due_date_day_of_week_name,
        due_date_month_num,
        due_date_day_of_month_num,
        scope_bucket,
        folder_id,
        folder_name,
        cast(null as string) as project_id,
        cast(null as string) as project_name,
        'folder' as grain_level,
        folder_id as grain_id,
        folder_name as grain_label,
        folder_id as parent_grain_id,
        folder_name as parent_grain_label,
        folder_url_path as grain_url_path,
        folder_url_web as grain_url_web,
        folder_url_native as grain_url_native,
        folder_url_path as parent_grain_url_path,
        folder_url_web as parent_grain_url_web,
        folder_url_native as parent_grain_url_native,
        count(distinct task_id) as task_count
    from open_tasks
    group by
        due_date_day,
        due_date_week,
        due_date_day_of_week_name,
        due_date_month_num,
        due_date_day_of_month_num,
        scope_bucket,
        folder_id,
        folder_name,
        folder_url_path,
        folder_url_web,
        folder_url_native
),

unioned as (
    select * from task_level
    union all
    select * from project_level
    union all
    select * from folder_level
)

select
    {{ dbt_utils.generate_surrogate_key(['cast(due_date_day as string)', 'grain_level', 'grain_id', 'scope_bucket']) }} as grain_rollup_id,
    due_date_day,
    due_date_week,
    due_date_day_of_week_name,
    due_date_month_num,
    due_date_day_of_month_num,
    scope_bucket,
    folder_id,
    folder_name,
    project_id,
    project_name,
    grain_level,
    grain_id,
    grain_label,
    parent_grain_id,
    parent_grain_label,
    grain_url_path,
    grain_url_web,
    grain_url_native,
    parent_grain_url_path,
    parent_grain_url_web,
    parent_grain_url_native,
    task_count
from unioned