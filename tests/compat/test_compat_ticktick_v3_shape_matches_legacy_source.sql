-- Each compat view must expose exactly the columns, order and types the legacy
-- ticktick_raw.<x>_v3 source declares, so the base models read it unchanged.
-- Returns one row per mismatch.
{%- set pairs = [
    ('compat__ticktick_v3__tasks', 'tasks_v3'),
    ('compat__ticktick_v3__projects', 'projects_v3'),
    ('compat__ticktick_v3__groups', 'groups_v3'),
] %}

with expected as (
    {%- if execute %}
    {%- for model_name, source_table in pairs %}
    {%- set src = graph.sources['source.life_admin_dbt.ticktick_raw.' ~ source_table] %}
    {%- for col in src.columns.values() %}
    select '{{ model_name }}' as table_name, '{{ col.name }}' as column_name,
        {{ loop.index }} as ordinal_position, '{{ col.data_type }}' as data_type
    {% if not loop.last %}union all{% endif %}
    {%- endfor %}
    {% if not loop.last %}union all{% endif %}
    {%- endfor %}
    {%- else %}
    select '' as table_name, '' as column_name, 0 as ordinal_position, '' as data_type
    {%- endif %}
),

actual as (
    select
        table_name,
        column_name,
        ordinal_position,
        -- legacy declarations say BOOLEAN; BigQuery reports BOOL
        if(data_type = 'BOOL', 'BOOLEAN', data_type) as data_type
    from {{ ref('compat__ticktick_v3__tasks').database }}.{{ ref('compat__ticktick_v3__tasks').schema }}.INFORMATION_SCHEMA.COLUMNS
    where table_name in (
        {%- for model_name, _ in pairs %}'{{ model_name }}'{% if not loop.last %}, {% endif %}{% endfor -%}
    )
)

select
    coalesce(e.table_name, a.table_name) as table_name,
    coalesce(e.column_name, a.column_name) as column_name,
    e.ordinal_position as expected_position,
    a.ordinal_position as actual_position,
    e.data_type as expected_type,
    a.data_type as actual_type
from expected as e
full outer join actual as a
    on e.table_name = a.table_name
    and e.column_name = a.column_name
where e.column_name is null
    or a.column_name is null
    or e.ordinal_position != a.ordinal_position
    or e.data_type != a.data_type
