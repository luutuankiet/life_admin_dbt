with source as (
    select * from {{ ref('stg__ticktick__projects') }}
),

extract_labels as (
    select 
    project_name,
    group_id,
    regexp_extract(project_name, r"folder_map - '(.*)'") as folder_name

    from source
    where project_name like 'folder_map - %'
),

final as (
    select 
    distinct
    group_id as folder_id,
    folder_name
    from extract_labels
    UNION ALL
    -- inject default folder name for projects with no folder names
    select 
    'default',
    'default'
    UNION ALL
    -- inject dummy folder name for inbox
    select 
    '0',
    'default'
)

select * from final