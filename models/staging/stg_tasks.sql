with source as (
    select 
    {{ dbt_utils.star(
        from=ref('base_tasks'),
        except=['completed_time', 'status']
        ) }},
    -- preserve the col order to join
    completed_time,
    0 as status

    from {{ref('base_tasks')}}
),

snap as (
    select 
    {{ dbt_utils.star(
        from=ref('base_tasks_snapshot'),
        except=[
            'dbt_valid_to', 'dbt_valid_from', 'dbt_updated_at', 'dbt_scd_id', 
            'completed_time', 'status'
            ]
        ) }},
    -- role play as inferred completed_time
    dbt_valid_to as completed_time,
    2 as status

    from (
        -- dedupe get latest instance in case of
        -- task removed due to project archived (competed),
        -- then project gets un-archived. in such case 
        -- we retrieve task instance with dbt_valid_to is NULL
        {{ dbt_utils.deduplicate(
            relation=ref('base_tasks_snapshot'),
            partition_by='task_id, etag',
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

flag_repeat as (

    select 
    *,
      CASE
        WHEN repeat_flag IS NOT NULL AND repeat_flag != '' THEN TRUE
        ELSE FALSE
      END AS is_recurring
    from add_completed_time

)



select 
{{ dbt_utils.generate_surrogate_key(['task_id','etag']) }} as surr_id,
*

from flag_repeat
    
