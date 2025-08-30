{#
This model provides a forward-looking view of all planned, incomplete tasks.
It uses a date spine to generate a continuous timeline starting from today,
ensuring that days with no scheduled tasks are included with a count of 0.

The grain of this table is one row per project per scheduled day.
#}

{%- set timezone = 'Asia/Ho_Chi_Minh' -%}

WITH

date_spine AS (
    {# 1. Generate a series of dates from today to 3 months in the future. #}
    {{ dbt_utils.date_spine(
        datepart="day",
        start_date="CAST(" ~ dbt_date.today(timezone) ~ " AS DATE)",
        end_date="CAST(" ~ dbt.dateadd('month', 3, dbt_date.today(timezone)) ~ " AS DATE)"
    ) }}
),

future_tasks AS (
    {# 2. Select all incomplete tasks that have a due date from today onwards. #}
    SELECT
        task_id,
        project_id,
        CAST(due_date AS DATE) AS due_date_day
    FROM {{ ref('fct_tasks') }}
    WHERE
        due_date IS NOT NULL
        AND status != 2 -- Filter for incomplete tasks
        AND CAST(due_date AS DATE) >= {{ dbt_date.today(timezone) }}
),

project_tasks_per_day AS (
    {# 3. Join the date spine with tasks and count tasks per project per day. #}
    SELECT
        d.date_day,
        t.project_id,
        COUNT(t.task_id) AS planned_tasks_count
    FROM date_spine d
    LEFT JOIN future_tasks t
        ON d.date_day = t.due_date_day
    GROUP BY
        d.date_day,
        t.project_id
)

{# 4. Final step: Join with the projects dimension to get project names. #}
SELECT
    ptd.date_day AS schedule_date,
    dp.project_id,
    dp.project_name,
    -- If a project has no tasks on a given day, the count will be 0.
    -- If a day has no tasks for ANY project, this ensures those rows still exist with a 0 count.
    COALESCE(ptd.planned_tasks_count, 0) AS planned_tasks_count
FROM project_tasks_per_day ptd
LEFT JOIN {{ ref('dim_projects') }} dp
    ON ptd.project_id = dp.project_id
-- We add a dummy project for days where no tasks are scheduled at all
-- to ensure the date appears in Lightdash.
UNION ALL
SELECT
    date_day,
    'no-project' AS project_id,
    'No Project Assigned' AS project_name,
    0 AS planned_tasks_count
FROM date_spine
WHERE date_day NOT IN (SELECT DISTINCT date_day FROM project_tasks_per_day WHERE planned_tasks_count > 0)
ORDER BY
    schedule_date,
    project_name
