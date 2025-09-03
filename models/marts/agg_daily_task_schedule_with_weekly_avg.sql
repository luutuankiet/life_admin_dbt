{#
This model provides a continuous daily view of scheduled tasks while also
calculating the weekly average. This is designed to power a mixed chart in
Lightdash, showing daily task counts as an area chart and the weekly average
as a line chart.

The grain of this table is one row per project per day.
#}



WITH daily_schedule AS (
    SELECT
        schedule_date,
        project_id,
        project_name,
        planned_tasks_count,
        -- Calculate the start of the week for each schedule_date
        DATE_TRUNC(schedule_date, WEEK(MONDAY)) AS week_start_date
    FROM {{ ref('fct_task_schedule') }}
),

weekly_averages AS (
    SELECT
        schedule_date,
        project_id,
        project_name,
        planned_tasks_count,
        week_start_date,
        -- Calculate the simple average of planned_tasks_count for each week
        AVG(planned_tasks_count) OVER (PARTITION BY week_start_date, project_id) AS weekly_average_tasks_per_project,
        AVG(planned_tasks_count) OVER (PARTITION BY week_start_date) AS overall_weekly_average_tasks
    FROM daily_schedule
)

SELECT
    schedule_date,
    project_id,
    project_name,
    planned_tasks_count,
    week_start_date,
    weekly_average_tasks_per_project,
    overall_weekly_average_tasks
FROM weekly_averages
ORDER BY
    schedule_date,
    project_name