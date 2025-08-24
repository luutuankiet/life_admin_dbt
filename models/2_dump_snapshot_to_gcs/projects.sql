{{ config(
    materialized='external',
    location='s3://ticktick_raw/snp/projects.csv',
    enabled=(target.name == 'dump_snapshot')
) }}

select * from {{source('stateless_raw','projects')}}