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
)



select 
*

from coalesce_null_group_ids
    
