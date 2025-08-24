{{ config(
    materialized='external',
    location='s3://ticktick_raw/snp/projects_snapshot.csv',
    enabled=(target.name == 'dump_snapshot')
) }}

select * from {{ref('snp_projects')}}