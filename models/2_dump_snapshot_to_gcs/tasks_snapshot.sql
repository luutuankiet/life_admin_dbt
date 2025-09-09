{{ config(
    materialized='external',
    location='s3://' ~ env_var('GCS_RAW_BUCKET') ~ '/ticktick/tasks_snapshot.jsonl',
    enabled=(target.name == 'dump_snapshot')
) }}

with snp as (
    select * from {{ref('snp_tasks')}}
),

base as (
    -- pulls in the stateless raw to inject 
    -- the latest attributes before dumping 
    -- to snapshot remote.
    select * from {{source('stateless_raw','tasks')}}
),

joined as (
    select 
    -- get base first if avail, else coalesce to snp
    {%- set columns = adapter.get_columns_in_relation(ref('snp_tasks')) -%}

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


-- needs to explicitly call out repeat tasks cause
-- they get the same id when done (!)
where repeatFlag is null
-- just found out that repeatflag can be blank instead of null.... 
-- starting to hate csv.
or repeatFlag = ''