{{
  config(
    enabled= target.name == 'load_snapshot',
    materialized='table'
    )
}}
select * from {{ source('stateful_raw','projects') }}