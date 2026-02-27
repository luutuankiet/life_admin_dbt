with expected as (
    select
        due_date_day,
        project_id,
        count(distinct task_id) as expected_open_task_count
    from {{ ref('fct_tasks_v3_semantic_base') }}
    where status != 2
      and due_date_day is not null
    group by 1, 2
),

actual as (
    select
        due_date_day,
        project_id,
        open_task_count
    from {{ ref('fct_tasks_v3_due_workload_daily') }}
)

select
    actual.due_date_day,
    actual.project_id,
    coalesce(expected.expected_open_task_count, 0) as expected_open_task_count,
    actual.open_task_count
from actual
left join expected
    on actual.due_date_day = expected.due_date_day
    and actual.project_id = expected.project_id
where actual.open_task_count != coalesce(expected.expected_open_task_count, 0)