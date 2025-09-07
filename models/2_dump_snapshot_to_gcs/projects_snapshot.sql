{{ config(
    materialized='external',
    location='s3://ticktick_raw/snp/projects_snapshot.csv',
    enabled=(target.name == 'dump_snapshot')
) }}

with snp as (

    select * from {{ref('snp_projects')}}

),

base as (
    -- pulls in the stateless raw to inject 
    -- the latest attributes before dumping 
    -- to snapshot remote.
    select * from {{source('stateless_raw','projects')}}
),

joined as (
    select 
    -- get base first if avail, else coalesce to snp
    {%- set columns = adapter.get_columns_in_relation(ref('snp_projects')) -%}

    {% for column in columns %}
        {% if 'dbt_' not in column.name %}
        COALESCE(b.{{column.name}}::text, s.{{column.name}}::text) as {{column.name}},
        {% endif %}
    {% endfor %}
    dbt_scd_id,
    dbt_updated_at,
    dbt_valid_from,
    dbt_valid_to

    from snp s LEFT JOIN base b 
    ON s.id = b.id


)

select * from joined