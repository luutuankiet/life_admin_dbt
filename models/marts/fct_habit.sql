{# models/marts/fct_habit.sql #}

{#
Habit fact table. Habits are TickTick tasks tagged with 'habit'.
Grain: one row per habit task (recurring parent, not instances).

Migration note (2026-03): Previously sourced from Todoist. Now sourced from
TickTick v3 API which provides native completion tracking (status=2 + completedTime).
#}

with habits as (
    select
        task_id,
        project_id,
        title,
        due_date,
        completed_time,
        updated_time,
        status,
        repeat_flag,
        tags
    from {{ ref('stg__ticktick_v3__tasks') }}
    where 'habit' in unnest(tags)
),

with_project as (
    select
        h.task_id,
        h.title,
        h.project_id,
        p.project_name,
        h.due_date,
        cast(h.due_date as date) as due_date_day,
        h.completed_time,
        cast(h.completed_time as date) as completed_date,
        h.updated_time,
        h.status,
        case h.status
            when 0 then 'open'
            when 2 then 'done'
            when -1 then 'wont_do'
            else 'other'
        end as status_label,
        cast(h.updated_time as date) as updated_date,
        h.repeat_flag,
        h.tags
    from habits h
    left join {{ ref('dim_projects_v3') }} p
        on h.project_id = p.project_id
)

select * from with_project