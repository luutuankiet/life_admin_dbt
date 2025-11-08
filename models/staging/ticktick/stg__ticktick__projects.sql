with source as (
    select 
    {{ dbt_utils.star(
        from=ref('base__ticktick__projects'),
        except=['closed']
        ) }},
    -- preserve the col order to join
    cast(NULL as DATETIME) as completed_time,
    false as closed

    from {{ref('base__ticktick__projects')}}
),

snap as (
    select 
    {{ dbt_utils.star(
        from=ref('base__ticktick__projects_snapshot'),
        except=['dbt_valid_to', 'dbt_valid_from', 'dbt_updated_at', 'dbt_scd_id', 'closed']
        ) }},
    -- role play as inferred completed_time
    dbt_valid_to as completed_time,
    true as closed

    from (
        -- dedupe get latest instance in case of
        -- then project gets un-archived
        {{ dbt_utils.deduplicate(
            relation=ref('base__ticktick__projects_snapshot'),
            partition_by='project_id',
            order_by="dbt_updated_at desc",
        )
        }}
    )
    where dbt_valid_to is not null
),

add_completed_time as (
    select * from source
    UNION ALL
    select * from snap
),

coalesce_null_group_ids as (
    select * except(group_id), coalesce(group_id,'default') as group_id
    from add_completed_time
),

add_last_pulse as (
-- pulls (MAX completed at x MAX due date) of each project's task
-- to determine when was the project last touched.
-- use case : gtd weekly review figure 
-- out which projects needs attention.

select 
    coalesce(pulse.due_date, pulse.completed_time) as last_pulse,
    project.*

    from coalesce_null_group_ids project

    LEFT JOIN (
        select 
        project_id,
        MAX(completed_time) as completed_time,
        MAX(due_date) as due_date
        from {{ ref("stg__ticktick__tasks") }}
        group by project_id
    ) as pulse
    on project.project_id = pulse.project_id
)



select 
*

from add_last_pulse