{# exclude cols we'll transform in this model #}
{% set except_cols = [
    'title',
    '_completed_time',
    'status'
    ]
%}
{# then create a set of shared column to keep the orders intact & UNION ALL happy #}
{%- set shared_columns = dbt_utils.star(from=ref('base__ticktick__tasks'),except=except_cols) -%}



with source as (
    select
    {{ shared_columns }},
    -- preserve the col order to join
    -- also set to NULL for cases task re-add / project unarchived
    -- in which we enforce source to always have "new" status.
    title,
    cast(NULL as DATETIME) as completed_time,
    cast(NULL as DATETIME) as updated_time,
    0 as status

    from {{ref('base__ticktick__tasks')}}
    where task_id != '0' -- we'd inject this in the cte below
),

snap as (
    select
    {{ shared_columns }},
    title,
    -- role play as inferred completed_time
    dbt_valid_to as completed_time,
    dbt_updated_at as updated_time,
    2 as status

    from (
        -- dedupe get latest instance in case of
        -- task removed due to project archived (competed),
        -- then project gets un-archived. in such case
        -- we retrieve task instance with dbt_valid_to is NULL
        {{ dbt_utils.deduplicate(
            relation=ref('base__ticktick__tasks_snapshot'),
            partition_by='task_id',
            order_by="dbt_updated_at desc",
        )
        }}
    )

    where dbt_valid_to is not null
),

inject_load_time as (
    select 
    {{ shared_columns }},
    -- calculate the next load time
    -- its an eyesore but i'd hate putting this
    -- in lightdash yaml 🤷
    {% if var('load_interval') %}
    CASE
        when DATETIME_DIFF(
            -- get expected next load time
            DATETIME_ADD(
                _completed_time,
                INTERVAL {{ var('load_interval') | as_number }} MINUTE
            ),
            -- substract it by current time
            CURRENT_DATETIME("{{var('timezone','UTC')}}"),
            MINUTE
        ) > 0
        then CONCAT(
            "🏗️ in ",
            DATETIME_DIFF(
                -- get expected next load time
                DATETIME_ADD(
                    _completed_time,
                    INTERVAL {{ var('load_interval') | as_number }} MINUTE
                ),
                -- substract it by current time
                CURRENT_DATETIME("{{var('timezone','UTC')}}"),
                MINUTE
            ),
            " minutes"
        )

        else "🟢 now"
    end as title,

    {% else %}
    title,
    {% endif %}
    cast(NULL as DATETIME) as completed_time,
    -- we injected a row id=1 in tasks_raw that has column _completed_time as the pipeline loaded time
    cast(_completed_time as DATETIME) as updated_time,
    0 as status,

    from {{ref('base__ticktick__tasks')}}
    where task_id = '0'
),

infer_completed_time as (
    -- this cte will union the two above to
    -- infer the completion time from snapshot model.
    select * from source
    UNION ALL
    select * from snap
    UNION ALL
    select * from inject_load_time
),

add_gtd_work_type as (
{% set deep_tags = fromjson(var('gtd_deep_work_tags'))%}
{%  set shallow_tags = fromjson(var('gtd_shallow_work_tags')) %}


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
            -- empty arrays have 0 length, 
            -- but NULL arrays will return NULL
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
from infer_completed_time
)
select
 *
from add_gtd_work_type
