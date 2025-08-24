with source as (
    select 
    {{ dbt_utils.star(
        from=ref('base_projects'),
        except=['closed']
        ) }},
    -- preserve the col order to join
    cast(NULL as timestamp) as completed_time,
    false as closed

    from {{ref('base_projects')}}
),

snap as (
    select 
    {{ dbt_utils.star(
        from=ref('base_projects_snapshot'),
        except=['dbt_valid_to', 'dbt_valid_from', 'dbt_updated_at', 'dbt_scd_id', 'closed']
        ) }},
    -- role play as inferred completed_time
    dbt_valid_to as completed_time,
    true as closed

    from (
        -- dedupe get latest instance in case of
        -- then project gets un-archived
        {{ dbt_utils.deduplicate(
            relation=ref('base_projects_snapshot'),
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
)



select 
*

from add_completed_time
    
