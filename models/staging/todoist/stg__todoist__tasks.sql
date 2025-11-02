{# 
{{ dbt_utils.union_relations(
    relations=[ref('base__todoist__active_tasks'), ref('base__todoist__completed_tasks')]
) }}

 #}
with active as (

        
            select
                cast('base__todoist__active_tasks' as string) as _dbt_source_relation,
                    cast(`user_id` as INT64) as `user_id` ,
                    cast(`id` as STRING) as `id` ,
                    cast(`project_id` as STRING) as `project_id` ,
                    cast(`note_count` as INT64) as `note_count` ,
                    cast(`section_id` as STRING) as `section_id` ,
                    cast(`content` as STRING) as `content` ,
                    cast(`completed_at` as DATETIME) as `completed_at` ,
                    cast(`assigned_by_uid` as STRING) as `assigned_by_uid` ,
                    cast(`description` as STRING) as `description` ,
                    cast(`priority` as INT64) as `priority` ,
                    cast(`responsible_uid` as STRING) as `responsible_uid` ,
                    cast(`updated_at` as DATETIME) as `updated_at` ,
                    cast(`checked` as BOOLEAN) as `checked` ,
                    cast(`added_at` as DATETIME) as `added_at` ,
                    cast(`is_collapsed` as BOOLEAN) as `is_collapsed` ,
                    cast(`deadline` as STRING) as `deadline` ,
                    cast(`parent_id` as STRING) as `parent_id` ,
                    cast(`day_order` as INT64) as `day_order` ,
                    cast(`added_by_uid` as INT64) as `added_by_uid` ,
                    cast(`is_deleted` as BOOLEAN) as `is_deleted` ,
                    cast(`duration` as STRING) as `duration` ,
                    cast(`child_order` as INT64) as `child_order` ,
                    cast(`labels` as ARRAY<STRING>) as `labels` ,
                    cast(`due_is_recurring` as BOOLEAN) as `due_is_recurring` ,
                    cast(`due_lang` as STRING) as `due_lang` ,
                    cast(`due_timezone` as STRING) as `due_timezone` ,
                    cast(`due_string` as STRING) as `due_string` ,
                    cast(`due_date` as DATETIME) as `due_date` ,
                    cast(null as ARRAY<STRING>) as `notes` ,
                    -- role play id as task_id as this is the main field
                    -- for identifying a task.
                    cast(id as STRING) as `task_id` ,
                    cast(null as STRING) as `meta_data` ,
                    cast(null as STRING) as `item_object` 

            from {{ ref('base__todoist__active_tasks') }}
),

completed as (
  select
                cast('base__todoist__completed_tasks' as string) as _dbt_source_relation,
                    cast(`user_id` as INT64) as `user_id` ,
                    cast(completed.`id` as STRING) as `id` ,
                    cast(`project_id` as STRING) as `project_id` ,
                    cast(`note_count` as INT64) as `note_count` ,
                    cast(`section_id` as STRING) as `section_id` ,
                    cast(`content` as STRING) as `content` ,
                    cast(`completed_at` as DATETIME) as `completed_at` ,
                    cast(null as STRING) as `assigned_by_uid` ,
                    cast(active.description as STRING) as `description` ,
                    cast(null as INT64) as `priority` ,
                    cast(null as STRING) as `responsible_uid` ,
                    cast(null as DATETIME) as `updated_at` ,
                    cast(null as BOOLEAN) as `checked` ,
                    cast(null as DATETIME) as `added_at` ,
                    cast(null as BOOLEAN) as `is_collapsed` ,
                    cast(null as STRING) as `deadline` ,
                    cast(null as STRING) as `parent_id` ,
                    cast(null as INT64) as `day_order` ,
                    cast(null as INT64) as `added_by_uid` ,
                    cast(null as BOOLEAN) as `is_deleted` ,
                    cast(null as STRING) as `duration` ,
                    cast(null as INT64) as `child_order` ,
                    cast(null as ARRAY<STRING>) as `labels` ,
                    cast(null as BOOLEAN) as `due_is_recurring` ,
                    cast(null as STRING) as `due_lang` ,
                    cast(null as STRING) as `due_timezone` ,
                    cast(null as STRING) as `due_string` ,
                    cast(null as DATETIME) as `due_date` ,
                    cast(`notes` as ARRAY<STRING>) as `notes` ,
                    cast(`task_id` as STRING) as `task_id` ,
                    cast(`meta_data` as STRING) as `meta_data` ,
                    cast(`item_object` as STRING) as `item_object` 

            from {{ ref('base__todoist__completed_tasks') }} completed
            -- grabs the description from active tasks
            LEFT JOIN (
                select id, description from 
                {{ ref('base__todoist__active_tasks') }} 
                ) as active
            ON completed.task_id = active.id 

            
),
unioned as (
    select * from active
    UNION ALL
    select * from completed
),
add_clean_content_col as (
    select 
    trim(
        regexp_replace(
            regexp_replace(
                content,
                r'@[^ ]+',
                ''
            ),
            r'\s+',
            ' '
        )
    ) as cleaned_content,
    * from unioned
),
add_streak as (
    select 
        case when description like '%Current streak%'
        then replace(description,'**Current streak:** ','')
        else NULL end as streak
        ,*

    from add_clean_content_col
),

coalesce_due_and_completed_date as (
    -- put duedate and completed date under the same field 
    -- to enable applying date filter on a single field for 
    -- completed and active tasks
    select 
    coalesce(completed_at,due_date) as scheduled_date
    ,*

    
    from add_streak
),

add_status as (
    -- simple router new task if no completed_at  else completed
    select 
    case when completed_at is null then 'new'
    else 'completed'
    end as is_completed
    ,*
    from coalesce_due_and_completed_date
)


select 
{{dbt_utils.generate_surrogate_key(['task_id', 'id']) }} as surr_id
,*

from add_status