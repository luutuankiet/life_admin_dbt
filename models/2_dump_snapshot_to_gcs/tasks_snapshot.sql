{{ config(
    materialized='external',
    location='s3://ticktick_raw/snp/tasks_snapshot.csv',
    enabled=(target.name == 'dump_snapshot')
) }}

select * from {{ref('snp_tasks')}}
-- needs to explicitly call out repeat tasks cause
-- they get the same id when done (!)
where repeatFlag is null