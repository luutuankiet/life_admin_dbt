{{ config(
    materialized='external',
    location='s3://' ~ env_var('GCS_RAW_BUCKET') ~ '/ticktick/projects.jsonl',
    enabled=(target.name == 'dump_snapshot')
) }}

select * from {{source('stateless_raw','projects')}}