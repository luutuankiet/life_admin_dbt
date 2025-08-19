{{ config(
    materialized='external',
    location='s3://ticktick_raw/snp/tasks.csv',
    enabled=(target.name == 'snapshot')
) }}

select * from {{ref('snp_tasks_raw')}}