{# models/marts/fct_habit_streaks.sql #}

{#
Habit streak calculation.
Grain: one row per habit (identified by title).

Computes:
- current_done_streak: consecutive completions from most recent action
- current_wontdo_streak: consecutive skips from most recent action
- last_action_date: when habit was last touched

Streak logic:
- Only counts completed (status=2) or skipped (status=-1) actions
- Streak resets when status flips or no more history
- Uses title as habit identifier (occurrences have different task_ids)
#}

with habit_actions as (
    -- All completed or skipped habit instances
    select
        title,
        task_id,
        project_id,
        status,
        coalesce(completed_time, updated_time) as action_time,
        row_number() over (
            partition by title 
            order by coalesce(completed_time, updated_time) desc
        ) as action_seq
    from {{ ref('stg__ticktick_v3__tasks') }}
    where 'habit' in unnest(tags)
      and status in (2, -1)  -- only done or won't do
),

streak_boundaries as (
    -- Detect where streaks break (status changes)
    select
        *,
        case 
            when status != lag(status) over (partition by title order by action_seq)
            then 1 
            else 0 
        end as is_streak_break
    from habit_actions
),

streak_groups as (
    -- Assign streak group (cumsum of breaks)
    select
        *,
        sum(is_streak_break) over (
            partition by title 
            order by action_seq
        ) as streak_group
    from streak_boundaries
),

current_streaks as (
    -- Current streak = group 0 (no breaks from most recent)
    select
        title,
        status as current_status,
        min(action_time) as streak_start,
        max(action_time) as last_action_date,
        count(*) as streak_length
    from streak_groups
    where streak_group = 0
    group by title, status
),

-- Get project info for display
habit_metadata as (
    select distinct
        title,
        project_id,
        first_value(task_id) over (
            partition by title 
            order by updated_time desc
        ) as latest_task_id
    from {{ ref('stg__ticktick_v3__tasks') }}
    where 'habit' in unnest(tags)
),

final as (
    select
        m.title,
        m.project_id,
        p.project_name,
        m.latest_task_id as task_id,
        
        -- Streak metrics
        coalesce(s.current_status, 0) as current_status,
        case s.current_status
            when 2 then 'done'
            when -1 then 'wont_do'
            else 'no_history'
        end as current_streak_type,
        
        case when s.current_status = 2 then s.streak_length else 0 end as current_done_streak,
        case when s.current_status = -1 then s.streak_length else 0 end as current_wontdo_streak,
        
        s.last_action_date,
        s.streak_start
        
    from habit_metadata m
    left join current_streaks s on m.title = s.title
    left join {{ ref('dim_projects_v3') }} p on m.project_id = p.project_id
)

select * from final