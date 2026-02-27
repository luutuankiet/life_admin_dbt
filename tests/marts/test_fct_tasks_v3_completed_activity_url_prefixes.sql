select
    completed_activity_id,
    task_url_web,
    task_url_native,
    project_url_web,
    project_url_native,
    folder_url_web,
    folder_url_native
from {{ ref('fct_tasks_v3_completed_activity') }}
where not (
    task_url_web like 'https://ticktick.com/webapp/#p/%/tasks/%'
    and task_url_native like 'ticktick://ticktick.com/webapp/#p/%/tasks/%'
    and project_url_web like 'https://ticktick.com/webapp/#p/%/tasks'
    and project_url_native like 'ticktick://ticktick.com/webapp/#p/%/tasks'
    and folder_url_web like 'https://ticktick.com/webapp/#g/%'
    and folder_url_native like 'ticktick://ticktick.com/webapp/#g/%'
)