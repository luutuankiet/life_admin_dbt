with source as (
    select *
    from {{ ref('stg__ticktick_v3__project_folder') }}
)

select *
from source