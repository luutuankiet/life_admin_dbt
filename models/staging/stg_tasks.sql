with source as (
    select * from {{ref('base_tasks')}}
)

select * from source