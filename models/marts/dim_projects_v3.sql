with source as (
    select *
    from {{ ref('stg__ticktick_v3__projects') }}
)

select *
from source