{{ config(
    materialized='external',
    location='s3://ticktick_raw/snp/projects.csv',
    enabled=(target.name == 'snapshot')
) }}

select * from {{ref('snp_projects_raw')}}