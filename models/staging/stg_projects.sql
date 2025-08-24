with source as (
    select * from {{ref('base_projects')}}
)

select * from source