with expected as (
    select
        due_date_day,
        scope_bucket,
        count(distinct task_id) as expected_open_task_count
    from {{ ref('fct_tasks_v3_semantic_base') }}
    where status != 2
      and due_date_day is not null
    group by 1, 2
),

actual as (
    select
        due_date_day,
        scope_bucket,
        grain_level,
        sum(task_count) as actual_open_task_count
    from {{ ref('fct_tasks_v3_grain_rollup') }}
    group by 1, 2, 3
)

select
    actual.due_date_day,
    actual.scope_bucket,
    actual.grain_level,
    coalesce(expected.expected_open_task_count, 0) as expected_open_task_count,
    actual.actual_open_task_count
from actual
left join expected
    on actual.due_date_day = expected.due_date_day
    and actual.scope_bucket = expected.scope_bucket
where actual.actual_open_task_count != coalesce(expected.expected_open_task_count, 0)