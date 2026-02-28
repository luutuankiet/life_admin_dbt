select
    due_workload_daily_id,
    project_url_web,
    project_url_native,
    folder_url_web,
    folder_url_native
from {{ ref('fct_tasks_v3_due_workload_daily') }}
where not (
    project_url_web like 'https://ticktick.com/webapp/#p/%/tasks'
    and project_url_native like 'ticktick://ticktick.com/webapp/#p/%/tasks'
    and folder_url_web like 'https://ticktick.com/webapp/#g/%'
    and folder_url_native like 'ticktick://ticktick.com/webapp/#g/%'
)