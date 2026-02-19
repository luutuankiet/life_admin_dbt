with source as (
    select
        group_id,
        group_name,
        deleted
    from {{ ref('base__ticktick_v3__groups') }}
),

active_groups as (
    select distinct
        group_id as folder_id,
        group_name as folder_name
    from source
    where coalesce(deleted, false) = false
),

inject_defaults as (
    select
        'default' as folder_id,
        'default' as folder_name
    from (select 1) as seed
    where not exists (
        select 1
        from active_groups
        where folder_id = 'default'
    )

    UNION ALL

    select
        '0' as folder_id,
        'default' as folder_name
    from (select 1) as seed
    where not exists (
        select 1
        from active_groups
        where folder_id = '0'
    )
),

final as (
    select * from active_groups
    UNION ALL
    select * from inject_defaults
)

select * from final