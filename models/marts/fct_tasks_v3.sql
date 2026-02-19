with source as (
    select *
    from {{ ref('stg__ticktick_v3__tasks') }}
)

select *
from source