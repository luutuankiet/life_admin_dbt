with completed_tasks as (
    select
        task_id,
        title,
        project_id,
        project_name,
        folder_id,
        folder_name,
        scope_bucket,
        gtd_work_type,
        completed_time,
        completed_time_day,
        completed_time_day_of_week_name,
        updated_time,
        due_date,
        due_date_day,
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
    where status = 2
      and completed_time_day is not null
)

select
    {{ dbt_utils.generate_surrogate_key(['task_id', 'cast(completed_time as string)', 'cast(updated_time as string)']) }} as completed_activity_id,
    task_id,
    title,
    project_id,
    project_name,
    concat(
        code_points_to_string([
            127812 + mod(abs(farm_fingerprint(project_name)), 50)
        ]),
        ' ',
        project_name
    ) as project_name_formatted,
    folder_id,
    folder_name,
    scope_bucket,
    gtd_work_type,
    completed_time,
    completed_time_day,
    completed_time_day_of_week_name,
    updated_time,
    due_date,
    due_date_day,
    task_url_path,
    task_url_web,
    task_url_native,
    project_url_path,
    project_url_web,
    project_url_native,
    folder_url_path,
    folder_url_web,
    folder_url_native
from completed_tasks