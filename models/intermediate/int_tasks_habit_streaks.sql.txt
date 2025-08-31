{# models/intermediate/int_tasks_habit_streaks.sql #}

{# 
This model identifies tasks tagged as 'habit' and calculates completion streaks.
It infers missed occurrences by parsing the task's repeat schedule ('RRULE')
to create a complete timeline of expected vs. actual completions, respecting the
local timezone.
#}

{# 
Note: The following Jinja block is used to dynamically determine the date range
for the dbt_utils.date_spine macro. This is necessary because the macro
requires string literals for its start and end dates.
#}
{{config(
    enabled=false
    )}}
{%- set timezone = 'Asia/Ho_Chi_Minh' -%}
{%- set date_range_query %}
SELECT
    {# Get the earliest date (start or due) from all habits to start the timeline, converted to the local timezone #}
    MIN(LEAST(DATE(due_date, '{{ timezone }}'), DATE(start_date, '{{ timezone }}'))) as start_date,
    {# Get the current date in the specified timezone to end the timeline #}
    {{ dbt_date.today(timezone) }} as end_date
FROM {{ ref('stg_tasks') }}
{# Correctly filter for habits, ignoring leading/trailing whitespace in tags #}
WHERE EXISTS (SELECT 1 FROM UNNEST(tags) AS tag WHERE TRIM(tag) = 'habit')
AND repeat_flag IS NOT NULL AND repeat_flag != ''
{%- endset -%}

{%- set date_range = dbt_utils.get_query_results_as_dict(date_range_query) -%}

{%- if execute -%}
    {%- set start_date = date_range['start_date'][0] | string -%}
    {# Add one day to the end date to ensure the date_spine includes the current day #}
    {%- set end_date = dbt.dateadd('day', 1, "'" ~ date_range['end_date'][0] ~ "'") | string -%}
{%- else -%}
    {#- Provide dummy dates for dbt's parsing phase -#}
    {%- set start_date = "2020-01-01" -%}
    {%- set end_date = "2020-01-02" -%}
{%- endif -%}

WITH

stg_tasks AS (
    {# Source: Staging model for tasks. #}
    SELECT *
    FROM {{ ref('stg_tasks') }}
),

habit_tasks AS (
    {# 1. Filter for habit tasks and find the earliest date (start or due) in the local timezone #}
    {#    to establish the starting point for its schedule. #}
    SELECT
        *,
        MIN(LEAST(DATE(due_date, '{{ timezone }}'), DATE(start_date, '{{ timezone }}'))) OVER (PARTITION BY task_id) as habit_start_date
    FROM stg_tasks
    {# Correctly filter for habits, ignoring leading/trailing whitespace in tags #}
    WHERE EXISTS (SELECT 1 FROM UNNEST(tags) AS tag WHERE TRIM(tag) = 'habit')
    AND repeat_flag IS NOT NULL AND repeat_flag != ''
),

date_spine AS (
    {# 2. Generate a series of dates using dbt_utils.date_spine. #}
    {#    The macro generates a full select statement. #}
    {{ dbt_utils.date_spine(
        datepart="day",
        start_date="CAST('" ~ start_date ~ "' AS DATE)",
        end_date="CAST(" ~ end_date ~ " AS DATE)"
    ) }}
),

latest_habit_schedule AS (
    {# New CTE to ensure we only use the most recent repeat_flag for each task #}
    SELECT
        task_id,
        habit_start_date,
        repeat_flag
    FROM (
        SELECT
            task_id,
            habit_start_date,
            repeat_flag,
            ROW_NUMBER() OVER (PARTITION BY task_id ORDER BY COALESCE(due_date, start_date) DESC) as rn
        FROM habit_tasks
    )
    WHERE rn = 1
),

habit_schedule_params AS (
    {# 3. Parse the RRULE string from the 'repeat_flag' to extract scheduling parameters. #}
    {#    This now references our new CTE to avoid duplicate schedules. #}
    SELECT
        task_id,
        habit_start_date,
        REGEXP_EXTRACT(repeat_flag, r'FREQ=([A-Z]+)') AS frequency,
        {# Extract and default the interval to 1 if not specified #}
        COALESCE(SAFE_CAST(REGEXP_EXTRACT(repeat_flag, r'INTERVAL=(\d+)') AS INT64), 1) AS `interval`,
        {# Extract days of the week for weekly habits #}
        SPLIT(REGEXP_EXTRACT(repeat_flag, r'BYDAY=([A-Z,]+)'), ',') AS by_day
    FROM latest_habit_schedule
),

expected_occurrences AS (
    {# 4. Generate the full "scaffold" of dates each habit was expected to occur. #}
    SELECT
        p.task_id,
        CAST(d.date_day AS DATE) AS expected_date
    FROM habit_schedule_params p
    CROSS JOIN date_spine d
    WHERE
        CAST(d.date_day AS DATE) >= p.habit_start_date
        AND
        (
            {# Logic for DAILY habits based on interval #}
            (p.frequency = 'DAILY' AND MOD(DATE_DIFF(CAST(d.date_day AS DATE), p.habit_start_date, DAY), p.interval) = 0)
            OR
            {# Logic for WEEKLY habits based on interval and days of the week #}
            (
                p.frequency = 'WEEKLY'
                AND MOD(DATE_DIFF(CAST(d.date_day AS DATE), p.habit_start_date, WEEK), p.interval) = 0
                AND FORMAT_DATE('%a', CAST(d.date_day AS DATE)) IN (SELECT UPPER(SUBSTR(day_abbr, 1, 2)) FROM UNNEST(p.by_day) as day_abbr)
            )
        )
),

deduplicate_completions AS (
    {# New step to handle multiple completions on the same day. #}
    {# We only keep the first completion for any given task on a single day, based on local time. #}
    SELECT
        *
    FROM (
        SELECT
            *,
            ROW_NUMBER() OVER(PARTITION BY task_id, DATE(completed_time, '{{ timezone }}') ORDER BY completed_time) as rn
        FROM habit_tasks
        WHERE status = 2
    )
    WHERE rn = 1
),

habit_log AS (
    {# 5. Join the expected occurrences with the now-deduplicated completed tasks. #}
    SELECT
        e.task_id,
        e.expected_date,
        COALESCE(t.status, -1) AS status,
        t.task_id,
        t.completed_time,
        t.title
    FROM expected_occurrences e
    LEFT JOIN deduplicate_completions t
        ON e.task_id = t.task_id AND DATE(t.completed_time, '{{ timezone }}') = e.expected_date
),

add_streak_bucket AS (
    {# 6. The "gaps and islands" logic. It now runs on the complete log. #}
    {#    A 'missed' day (status -1) will break the sequence and start a new bucket. #}
    SELECT
        *,
        SUM(CASE WHEN status = 2 THEN 1 ELSE 0 END) OVER (
            PARTITION BY task_id
            ORDER BY expected_date
        )
        -
        ROW_NUMBER() OVER (
            PARTITION BY task_id
            ORDER BY expected_date
        ) AS habit_streak_bucket_id
    FROM habit_log
    WHERE status = 2 {# Only calculate buckets for completed tasks #}
),

calculate_streak AS (
    {# 7. Calculate the rolling streak count within each bucket. #}
    SELECT
        task_id,
        title,
        expected_date,
        ROW_NUMBER() OVER (
            PARTITION BY task_id, habit_streak_bucket_id
            ORDER BY expected_date
        ) AS habit_streak
    FROM add_streak_bucket
)

{# Final step: Join the calculated streaks back to the full habit log. #}
SELECT
    hl.task_id,
    COALESCE(hl.title, cs.title) as title,
    hl.expected_date,
    hl.status,
    hl.completed_time,
    cs.habit_streak
FROM habit_log hl
LEFT JOIN calculate_streak cs
    ON hl.task_id = cs.task_id AND hl.expected_date = cs.expected_date
ORDER BY
    hl.task_id,
    hl.expected_date
