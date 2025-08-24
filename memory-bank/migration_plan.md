# Migration Plan: v1 to v2 dbt Models

## 1. Overview

This document outlines the plan for migrating the dbt models from the v1 setup to the new v2 repository. The primary difference between the two versions is the data source: v1 used a custom Python script, while v2 uses the official TickTick Open API via an Airbyte connector. This change has resulted in a simplified data model, which necessitates a re-implementation of many of the v1 models and metrics.

## 2. Analysis of v1 and v2 Setups

### 2.1. v1 Setup

*   **Data Sources:** Custom Python script (`ticktick-py-dbt`).
*   **Entities:** `folders`, `lists`, `todos`, `statuses`.
*   **Metrics:** Detailed progress tracking (`lvl1_progress`, `lvl2_progress`, `lvl3_progress`), habit streak analysis, and various derived metrics.
*   **Structure:** `staging`, `intermediate`, and `marts` layers.

### 2.2. v2 Setup

*   **Data Sources:** Official TickTick Open API via Airbyte connector.
*   **Entities:** `projects` and `tasks`.
*   **Metrics:** Basic transformations and snapshots.
*   **Structure:** Primarily `staging` models.

## 3. Feasibility Analysis

Given the new, simplified data model, not all v1 models and metrics will be directly transferable.

### 3.1. Feasible Models

*   **`dim_projects`:** Can be created from the `projects` data stream. This will be a simplified version of the old `dim_folders` and `dim_lists`.
*   **`dim_tasks`:** Can be created from the `tasks` data stream. This will be a simplified version of the old `fact_todos`.
*   **`dim_dates`:** Can be reused as it's a standard date dimension.
*   **`dim_statuses`:** Can be recreated, but the statuses might need to be inferred from the `tasks` data.

### 3.2. Feasible Metrics

*   **Task Completion Rate:** Can be calculated by comparing the number of completed tasks to the total number of tasks.
*   **Project Progress:** Can be calculated by tracking the percentage of completed tasks within each project.
*   **Task Overdue:** Can be calculated by comparing the `dueDate` with the current date.

### 3.3. Infeasible Models & Metrics (for now)

*   **Habit Streak Analysis:** The new API might not provide the necessary data for this.
*   **`lvl1_progress`, `lvl2_progress`, `lvl3_progress`:** These were based on the old, more granular data model and would need to be re-imagined.
*   **`rolling_counter`:** This was based on the old `fact_todos` and would need to be adapted.

## 4. Migration Plan

The following is a step-by-step plan for migrating the v1 models to the new v2 setup.

### 4.1. Create Core Dimension Models

*   **`dim_projects`:**
    *   **Source:** `projects` data stream.
    *   **Columns:** `project_id`, `project_name`, `project_color`, etc.
    *   **Logic:** This model will serve as a replacement for `dim_folders` and `dim_lists`.
*   **`dim_tasks`:**
    *   **Source:** `tasks` data stream.
    *   **Columns:** `task_id`, `task_title`, `task_content`, `task_status`, `task_due_date`, etc.
    *   **Logic:** This model will serve as a replacement for `fact_todos`.
*   **`dim_statuses`:**
    *   **Source:** `tasks` data stream.
    *   **Logic:** The statuses will need to be inferred from the `tasks` data.

### 4.2. Re-implement Core Metrics

*   **Task Completion Rate:**
    *   **Logic:** `COUNT(completed_tasks) / COUNT(total_tasks)`.
*   **Project Progress:**
    *   **Logic:** `COUNT(completed_tasks) / COUNT(total_tasks)` for each project.
*   **Overdue Tasks:**
    *   **Logic:** `WHERE dueDate < CURRENT_DATE`.

### 4.3. Investigate Advanced Metrics

*   **Habit Streak Analysis:**
    *   **Action:** Investigate the new API to determine if the necessary data is available.
    *   **If Feasible:** Re-implement the habit streak analysis logic.

## 5. Handoff Notes

*   The `v1_models.md` file is not included in this handoff. All necessary information has been consolidated into this document.
*   The primary focus of this migration is to re-establish the core data models and metrics. The more advanced metrics can be revisited in the future.

## 6. Detailed v1 Model Logic

This section provides a detailed overview of the logic used in the v1 models.

### 6.1. Staging Models

#### `stg_folders`

*   **Description:** Cleans and prepares the raw `folders` data.
*   **Logic:**
    *   Coalesces null values to defaults.
    *   Generates a surrogate key (`folder_key`).

```sql
-- models/staging/stg_folders.sql
WITH source AS (
    SELECT
         {{coalesce_defaults(ref(
            'base_folders'
        ) )}}
    FROM
        {{ ref(
            'base_folders'
        ) }}
)
 
SELECT
    {{ dbt_utils.generate_surrogate_key(['folder_id']) }} AS folder_key,*
FROM
    source
```

#### `stg_lists`

*   **Description:** Cleans and prepares the raw `lists` data.
*   **Logic:**
    *   Coalesces null values to defaults.
    *   Infers `list_created_time` from the first `todo_createdTime` in the list.
    *   Calculates `list_isActive` based on the `list_closed` flag.
    *   Generates a surrogate key (`list_key`).

```sql
-- models/staging/stg_lists.sql
WITH lists AS (
    SELECT
        {{ coalesce_defaults(ref('base_lists')) }}
    FROM
        {{ ref(
            'base_lists'
        ) }}
),
todo AS (
    SELECT
        {{ coalesce_defaults(ref('base_todos')) }}
    FROM
        {{ ref(
            "base_todos"
        ) }}
),
list_created AS (
    SELECT
        todo_projectid,
        MIN(todo_createdTime) AS list_created_time
    FROM
        todo
    GROUP BY
        todo_projectid
),
list_isActive AS (
    SELECT
        CASE
            WHEN list_closed = 'True' THEN 0
            ELSE 1
        END AS list_isActive,
        list_id
    FROM
        lists
),
joined AS (
    SELECT
        l.*,
        COALESCE(
            t.list_created_time,
            '1900-01-01T00:00:00'
        ) :: TIMESTAMP AS list_created_time,
        list_isActive :: BOOLEAN AS list_isActive
    FROM
        lists l
        INNER JOIN list_created t
        ON l.list_id = t.todo_projectid
        INNER JOIN list_isActive i
        ON l.list_id = i.list_id 
)
SELECT
    {{ dbt_utils.generate_surrogate_key(['list_id']) }} AS list_key,*
FROM
    joined
```

#### `stg_statuses`

*   **Description:** Creates a status dimension from the `todo_status` field.
*   **Logic:**
    *   Maps status codes to descriptions.
    *   Generates a surrogate key (`status_key`).

```sql
-- models/staging/stg_statuses.sql
WITH source AS (
    SELECT
        {{coalesce_defaults(ref('base_todos'))}}
    FROM
        {{ref('base_todos')}}
),
renamed AS (
    SELECT
        DISTINCT todo_status AS status_id,
        CASE
            WHEN todo_status = '-1' THEN 'wont do'
            WHEN todo_status = '2' THEN 'done'
            WHEN todo_status = '0' THEN 'undone'
        END AS "status_desc",
        CASE
            WHEN todo_status = '-1' THEN 'regardless of archival'
            WHEN todo_status = '2' THEN 'regardless of archival'
            WHEN todo_status = '0' THEN 'regardless of archival'
        END AS status_comments
    FROM
        source
)
SELECT
    {{ dbt_utils.generate_surrogate_key(['status_id']) }} AS status_key,*
FROM
    renamed
```

#### `stg_todos`

*   **Description:** Cleans and prepares the raw `todos` data.
*   **Logic:**
    *   Coalesces null values to defaults.
    *   Derives date fields from timestamps.
    *   Joins with `lists`, `folders`, `statuses`, and `dates` to create foreign keys.
    *   Generates a surrogate key (`todo_key`).

```sql
-- models/staging/stg_todos.sql
{{ config(
    materialized='table',
    unique_key = ['todo_id'],
    incremental_strategy = 'merge',
    on_schema_change='append_new_columns'
) }}

WITH init_todo AS (
    

    SELECT
        DISTINCT {{ coalesce_defaults(ref('base_todos')) }}
    FROM
        {{ ref('base_todos') }}
),
_todo__recurring AS (
    -- handle flagging habits
    SELECT
        *,
        CASE
            WHEN (
                todo_status <> '0'
                AND EXISTS (
                    SELECT
                        todo_id
                    FROM
                        init_todo A
                    WHERE
                        A.todo_id = b.todo_repeattaskid
                        AND A.todo_repeatflag <> 'default'
                )
            )
            OR (
                todo_status = '0'
                AND todo_repeatflag <> 'default'
            ) THEN TRUE
            ELSE FALSE
        END AS todo_derived__is_repeat
    FROM
        init_todo b
),
_todo__habit_streak_init AS (
    -- create buckets
    SELECT
        *,
        CASE
            WHEN todo_status = '2' THEN SUM(
                CASE
                    WHEN todo_status = '2' THEN 1
                    ELSE 0
                END
            ) over (
                PARTITION BY todo_repeattaskid
                ORDER BY
                    todo_completedtime rows BETWEEN unbounded preceding
                    AND CURRENT ROW
            ) - ROW_NUMBER() over (
                PARTITION BY todo_repeattaskid
                ORDER BY
                    todo_completedtime
            ) + 1
            ELSE NULL
        END AS _todo__habit_streak_bucket_id
    FROM
        _todo__recurring
),
_todo__habit_streak AS (
    -- add additional column for rolling streak counter all time
    SELECT
        *,
        CASE
            WHEN todo_status = '2' THEN ROW_NUMBER() over(
                PARTITION BY todo_repeattaskid,
                _todo__habit_streak_bucket_id
                ORDER BY
                    todo_completedtime ASC
            )
            WHEN todo_status = '0' THEN NULL
            WHEN todo_status = '-1' THEN 0
        END AS todo_derived__habit_streak
    FROM
        _todo__habit_streak_init
),
_todo__habit_latest_wrapper AS (
    -- add bunch of wrapper fields for those recurring that grabs the latest ocurrence's fields
    SELECT
        COALESCE(
            b.todo_title,
            A.todo_title
        ) AS todo_title,
        COALESCE(
            b.todo_projectid,
            A.todo_projectid
        ) AS todo_projectid,
        A.todo_derived__is_repeat,
        A._todo__habit_streak_bucket_id,
        A.todo_derived__habit_streak,
        {{ dbt_utils.star(ref('base_todos'), relation_alias = 'A', except = ["todo_title", "todo_projectid" ]) }}
    FROM
        _todo__habit_streak A
        LEFT JOIN _todo__habit_streak b
        ON A.todo_repeattaskid = b.todo_id
),
todo_habit_stg AS (
    SELECT
        h.todo_title,
        h.todo_projectid,
        h.todo_derived__habit_streak,
        h._todo__habit_streak_bucket_id,
        r.todo_derived__is_repeat,
        {{ dbt_utils.star(ref('base_todos'), relation_alias = 'r', except = ["todo_title", "todo_projectid" ]) }}
    FROM
        _todo__recurring r
        LEFT JOIN _todo__habit_latest_wrapper h
        ON r.todo_id = h.todo_id),

init_todo_add_consecutive_undone AS (
    SELECT
        todo_habit_stg.*,
        CASE
            
            WHEN todo_status in ('-1','2') THEN SUM( -- add in 0 to also wrap undone NEW tasks to the count
                CASE
                    WHEN todo_status = '-1' THEN 1
                    ELSE 0
                END
            ) over (
                PARTITION BY todo_repeattaskid
                ORDER BY
                    todo_completedtime rows BETWEEN unbounded preceding
                    AND CURRENT ROW
            ) - ROW_NUMBER() over (
                PARTITION BY todo_repeattaskid
                ORDER BY
                    todo_completedtime
            ) + 1
            ELSE NULL
        END AS _todo__habit_undone_streak_bucket_id,
        lag(todo_status) over (partition by todo_repeattaskid order by todo_duedate) as _status_lag,
        lead(todo_status) over (partition by todo_repeattaskid order by todo_duedate) as _status_lead
    FROM
        todo_habit_stg
),
todo_add_consecutive_undone AS (
    SELECT
        init_todo_add_consecutive_undone.*,
        CASE
            
            WHEN todo_status in ('-1','2')
            AND _todo__habit_undone_streak_bucket_id = MIN(_todo__habit_undone_streak_bucket_id) over (
                PARTITION BY todo_repeattaskid
            )
            THEN SUM(
                CASE
                    WHEN todo_status = '-1' THEN 1
                    WHEN todo_status = '2' and (_status_lag = '-1' and _status_lead in ('2','0')) 
                    THEN -99999

                    ELSE 0
                END
            ) over(
                PARTITION BY todo_repeattaskid,
                _todo__habit_undone_streak_bucket_id
            )
            ELSE 0
        END AS _todo_derived__consecutive_undone
    FROM
        init_todo_add_consecutive_undone
),
stg_todo_undone AS (
    select todo_add_consecutive_undone.*,
        case
            when max(_todo_derived__consecutive_undone) over(partition by todo_title) > 0 
            then max(_todo_derived__consecutive_undone) over (partition by todo_title)
            else null
        end as todo_derived__consecutive_undone
    from todo_add_consecutive_undone
),
todo AS (
    -- this be the final table
    SELECT
        *
    FROM
        init_todo
),
lists AS (
    SELECT
        {{ coalesce_defaults(ref('base_lists')) }}
    FROM
        {{ ref('base_lists') }}
),
folders AS (
    SELECT
        {{ coalesce_defaults(ref('base_folders')) }}
    FROM
        {{ ref('base_folders') }}
),
statuses AS (
    SELECT
        *
    FROM
        {{ ref('stg_statuses') }}
),
dates AS (
    SELECT
        *
    FROM
        {{ ref('stg_dates') }}
),

joined AS (
    SELECT
        {# gotta handle the NULLs from this join; they are hashed. next up is to generate that hashed null in other tables #}
        {{ dbt_utils.generate_surrogate_key(['dds.date_id']) }} AS date_start_key,
        {{ dbt_utils.generate_surrogate_key(['ddd.date_id']) }} AS date_due_key,
        {{ dbt_utils.generate_surrogate_key(['ddcm.date_id']) }} AS date_completed_key,
        {{ dbt_utils.generate_surrogate_key(['ddc.date_id']) }} AS date_created_key,
        {{ dbt_utils.generate_surrogate_key(['ddm.date_id']) }} AS date_modified_key,
        {{ dbt_utils.generate_surrogate_key(['list_id']) }} AS list_key,
        {{ dbt_utils.generate_surrogate_key(['folder_id']) }} AS folder_key,
        {{ dbt_utils.generate_surrogate_key(['status_id']) }} AS status_key,
        t.*,
        COALESCE(l.list_name, 'default') AS todo_list_name,
        COALESCE(f.folder_name, 'default') AS todo_folder_name,
        COALESCE(
            l.list_id,
            'default'
        ) AS list_id,
        COALESCE(
            f.folder_id,
            'default'
        ) AS folder_id,
        COALESCE(
            ss.status_id,
            'default'
        ) AS status_id
    FROM
        todo t
        LEFT JOIN lists l
        ON t.todo_projectid = l.list_id
        LEFT JOIN folders f
        ON l.list_groupid = f.folder_id
        LEFT JOIN statuses ss
        ON ss.status_id = t.todo_status
        LEFT JOIN dates dds
        ON dds.date_id = t.todo_startdate_derived_date
        LEFT JOIN dates ddd
        ON ddd.date_id = t.todo_duedate_derived_date
        LEFT JOIN dates ddc
        ON ddc.date_id = t.todo_createdtime_derived_date
        LEFT JOIN dates ddcm
        ON ddcm.date_id = t.todo_completedtime_derived_date
        LEFT JOIN dates ddm
        ON ddm.date_id = t.todo_modifiedtime_derived_date
)
SELECT
    {{ dbt_utils.generate_surrogate_key(['todo_id']) }} AS todo_key,
    *,
    {{dbt_date.now("Asia/Ho_Chi_Minh")}} as _modified_time
FROM
    joined

{% if is_incremental() %}
  WHERE 
  (-- address this bug tasks completed dont get updated in modified time
    todo_completedtime >= todo_modifiedtime 
    AND todo_completedtime::date >= {{dbt_date.n_days_ago(7)}}
    )
  OR 
  todo_modifiedtime >= (select coalesce(max(todo_modifiedtime),'1900-01-01 00:00:00') from {{ this }} )
{% endif %}
```

### 6.2. Intermediate Models

#### `int_habit_streak_logic`

*   **Description:** Calculates habit streaks and consecutive undone tasks.
*   **Logic:**
    *   Identifies recurring tasks.
    *   Creates "buckets" for consecutive completions and non-completions.
    *   Calculates streak length within each bucket.
    *   Handles edge cases like status changes.

```sql
-- models/intermediate/int_add_bucket.sql
with source as (
    select * FROM {{ ref('int_identify_recurr') }}
),

add_done_bucket_id as (
    -- create buckets
    SELECT
        CASE
            WHEN todo_status = '2' THEN SUM(
                CASE
                    WHEN todo_status = '2' THEN 1
                    ELSE 0
                END
            ) over (
                PARTITION BY todo_repeattaskid
                ORDER BY
                    todo_completedtime rows BETWEEN unbounded preceding
                    AND CURRENT ROW
            ) 
            
            - ROW_NUMBER() over (
                PARTITION BY todo_repeattaskid
                ORDER BY
                    todo_completedtime
            ) + 1
            ELSE NULL
        END AS todo_done_habit_bucket_id,
        *
    FROM
        source
),
add_wontdo_bucket_id as (
        -- create buckets
    SELECT
        CASE
            WHEN todo_status = '-1' THEN SUM(
                CASE
                    WHEN todo_status = '-1' THEN 1
                    ELSE 0
                END
            ) over (
                PARTITION BY todo_repeattaskid
                ORDER BY
                    todo_completedtime rows BETWEEN unbounded preceding
                    AND CURRENT ROW
            ) 
            
            - ROW_NUMBER() over (
                PARTITION BY todo_repeattaskid
                ORDER BY
                    todo_completedtime
            ) + 1
            ELSE NULL
        END AS todo_wontdo_habit_bucket_id,
        *
    FROM
        source
) ,

unioned as (
    select 
    ABS(todo_done_habit_bucket_id) as todo_done_habit_bucket_id,
    NULL as todo_wontdo_habit_bucket_id,
    {{ dbt_utils.star(ref('int_identify_recurr'))}}
    FROM add_done_bucket_id
    WHERE todo_status in ('2', '0') -- so that both new and latest done todo  in same bucket

    UNION ALL 
    select 
    NULL as todo_done_habit_bucket_id,
    ABS(todo_wontdo_habit_bucket_id) as todo_wontdo_habit_bucket_id,
    {{ dbt_utils.star(ref('int_identify_recurr'))}}
    FROM add_wontdo_bucket_id
    WHERE todo_status = '-1'
),

debug as (
    select 
    todo_done_habit_bucket_id,
    todo_wontdo_habit_bucket_id,
    todo_status,
    todo_completedtime,
    todo_title,
    todo_repeattaskid


    FROM unioned
    {# where todo_title ='morning deepwork' #}
    where todo_repeattaskid ='661797cc7ffe5107283a524a'
    {# where todo_repeattaskid ='6583f9868f08a6578069f73b' #}
    order by todo_completedtime::timestamp desc
    
),

final as ( 
    select * FROM unioned
)

select * FROM final
```

### 6.3. Marts Models

#### `fact_todos`

*   **Description:** The main fact table, combining data from `stg_todos` and `int_streak_rollup`.
*   **Logic:**
    *   Joins `stg_todos` with `int_streak_rollup` on `todo_id`.
    *   Includes logic for incremental loads.

```sql
-- models/marts/core/fact_todos.sql
{# had to hardcode the pre hook cause otherwise the old dummy lookahead dates gonn persist & build up #}
{{ config(
    materialized='table',
    unique_key = ['todo_lookahead_skey'],
    incremental_strategy = 'merge',
    on_schema_change='append_new_columns',
    pre_hook = ['{{cleanup_nulls("todo_id")}}'],
    post_hook = ["{% if not is_incremental() %} {{ setup_textsearch() }} {% endif %}"]
) }}
{# extract the base columns from models/intermediate/int_identify_recurr.sql #}
{% set streaks_base_column = dbt_utils.get_filtered_columns_in_relation(
    from = ref('int_identify_recurr'),
    except = ['todo_derived__is_repeat']
) %}
WITH source AS (

    SELECT
        DISTINCT *
    FROM
        {{ ref('stg_todos_join_lookahead') }}
),
streak_analytics AS (
    SELECT
        *
    FROM
        {{ ref('int_streak_rollup') }}
),
joined AS (
    SELECT
        -- grab new fields from the model
        {{ dbt_utils.star(ref('int_streak_rollup'), except = streaks_base_column, relation_alias = 'sa') }},
        -- the base fact todos fields
        {{ dbt_utils.star(ref('stg_todos_join_lookahead'), relation_alias = 's') }}
    FROM
        source s
        LEFT JOIN streak_analytics sa
        ON s.todo_id = sa.todo_id)
    SELECT
        *
    FROM
        joined

{% if is_incremental() %}
  WHERE 
  _modified_time >= (select coalesce(max(_modified_time),'1900-01-01 00:00:00') from {{ this }} )
  OR
  todo_modifiedtime IS NULL
{% endif %}
```

#### `obt`

*   **Description:** An "One Big Table" view that joins `fact_todos` with all dimension tables.
*   **Logic:**
    *   Left joins `fact_todos` with `dim_lists`, `dim_folders`, `dim_statuses`, and `dim_dates`.

```sql
-- models/marts/core/obt.sql
{{
  config(
    materialized = 'view'
    )
}}
WITH f_todos AS (
    SELECT
        *
    FROM
        {{ ref('fact_todos') }}
),
d_lists AS (
    SELECT
        *
    FROM
        {{ ref('dim_lists') }}
),
d_folders AS (
    SELECT
        *
    FROM
        {{ ref('dim_folders') }}
),
d_statuses AS (
    SELECT
        *
    FROM
        {{ ref('dim_statuses') }}
),
d_start_dates AS (
    SELECT
        *
    FROM
        {{ ref('dim_dates') }}
),
d_due_dates AS (
    SELECT
        *
    FROM
        {{ ref('dim_dates') }}
),
d_created_dates AS (
    SELECT
        *
    FROM
        {{ ref('dim_dates') }}
),
d_completed_dates AS (
    SELECT
        *
    FROM
        {{ ref('dim_dates') }}
)
SELECT
    {{ dbt_utils.star(
        from = ref('fact_todos'),
        relation_alias = 'f_todos',
        except = [ 'list_key', 'folder_key','status_key','todo_key','date_start_key','date_due_key','date_completed_key', 'date_created_key','list_id','folder_id','status_id' ]
    ) }},
    {{ dbt_utils.star(
        from = ref('dim_lists'),
        relation_alias = 'd_lists',
        except = [ 'list_key' ]
    ) }},
    {{ dbt_utils.star(
        from = ref('dim_folders'),
        relation_alias = 'd_folders',
        except = [ 'folder_key' ]
    ) }},
    {{ dbt_utils.star(
        from = ref('dim_statuses'),
        relation_alias = 'd_statuses',
        except = [ 'status_key' ]
    ) }},
    -- dates roleplay
    {{ dbt_utils.star(
        from = ref('dim_dates'),
        relation_alias = 'd_start_dates',
        prefix = 'start_',
        except = [ 'date_key' ]
    ) }},
    {{ dbt_utils.star(
        from = ref('dim_dates'),
        relation_alias = 'd_due_dates',
        prefix = 'due_',
        except = [ 'date_key' ]
    ) }},
    {{ dbt_utils.star(
        from = ref('dim_dates'),
        relation_alias = 'd_completed_dates',
        prefix = 'completed_',
        except = [ 'date_key' ]
    ) }},
    {{ dbt_utils.star(
        from = ref('dim_dates'),
        relation_alias = 'd_created_dates',
        prefix = 'created_',
        except = [ 'date_key' ]
    ) }}
FROM
    f_todos
    LEFT JOIN d_lists
    ON f_todos.list_key = d_lists.list_key
    LEFT JOIN d_folders
    ON f_todos.folder_key = d_folders.folder_key
    LEFT JOIN d_statuses
    ON f_todos.status_key = d_statuses.status_key
    LEFT JOIN d_start_dates
    ON f_todos.date_start_key = d_start_dates.date_key
    LEFT JOIN d_due_dates
    ON f_todos.date_due_key = d_due_dates.date_key
    LEFT JOIN d_completed_dates
    ON f_todos.date_completed_key = d_completed_dates.date_key
    LEFT JOIN d_created_dates
    ON f_todos.date_created_key = d_created_dates.date_key