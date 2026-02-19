{# exclude cols we'll transform in this model #}
{% set except_cols = [
    'title',
    '_completed_time',
    'status',
    'modified_time',
    'deleted'
    ]
%}
{%- set shared_columns = dbt_utils.star(from=ref('base__ticktick_v3__tasks'), except=except_cols) -%}

with source as (
    select
        {{ shared_columns }},
        title,
        case
            when status = 2 then _completed_time
            else cast(NULL as DATETIME)
        end as completed_time,
        case
            when status = 2 then modified_time
            else cast(NULL as DATETIME)
        end as updated_time,
        status
    from {{ ref('base__ticktick_v3__tasks') }}
    where deleted = 0
),

add_gtd_work_type as (
{% set deep_tags = fromjson(var('gtd_deep_work_tags')) %}
{% set shallow_tags = fromjson(var('gtd_shallow_work_tags')) %}

select
    *,
    case
        when
    {% if var('enable_gtd_work_type_categorization') or (deep_tags | length == 0 and shallow_tags | length == 0)  %}
        {% if deep_tags | length > 0 %}
            ARRAY_LENGTH(
                ARRAY(
                    (SELECT tag FROM UNNEST({{ deep_tags }}) as tag)
                    INTERSECT DISTINCT
                    (SELECT tag FROM UNNEST(tags) as tag)
                )
            ) > 0

        {% elif deep_tags | length == 0 %}
            COALESCE(ARRAY_LENGTH(tags),0) = 0
        {% endif %}
            then '🥩'

        when
        {% if shallow_tags | length > 0 %}
            ARRAY_LENGTH(
                ARRAY(
                    (SELECT tag FROM UNNEST({{ shallow_tags }}) as tag)
                    INTERSECT DISTINCT
                    (SELECT tag FROM UNNEST(tags) as tag)
                )
            ) > 0

        {% elif shallow_tags | length == 0 %}
            COALESCE(ARRAY_LENGTH(tags),0) = 0
        {% endif %}
            then '🧃'

    {% else %}
        NULL THEN NULL
    {% endif %}
        else null
    end as gtd_work_type
from source
)

select
    *
from add_gtd_work_type