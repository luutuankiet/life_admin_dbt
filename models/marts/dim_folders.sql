with source as (
    select * from {{ref('stg__ticktick__project_folder')}}
),

final as (
    select *  from source
)

select * from source

