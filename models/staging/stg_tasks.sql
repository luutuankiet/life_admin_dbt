with source as (
    select 
    {{ dbt_utils.star(
        from=ref('base_tasks'),
        except=['completed_time', 'status']
        ) }},
    -- preserve the col order to join
    -- also set to NULL for cases task re-add / project unarchived
    -- in which we enforce source to always have "new" status.
    cast(NULL as timestamp) as completed_time,
    cast(NULL as timestamp) as updated_time,
    0 as status

    from {{ref('base_tasks')}}
),

snap as (
    select 
    {{ dbt_utils.star(
        from=ref('base_tasks_snapshot'),
        except=[
            'dbt_valid_to', 'dbt_valid_from', 'dbt_updated_at', 'dbt_scd_id', 
            'completed_time', 'status'
            ]
        ) }},
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
            relation=ref('base_tasks_snapshot'),
            partition_by='task_id',
            order_by="dbt_updated_at desc",
        )
        }}
    )

    where dbt_valid_to is not null
),

infer_completed_time as (
    -- this cte will union the two above to
    -- infer the completion time from snapshot model.
    select * from source
    UNION ALL
    select * from snap
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
            ARRAY_LENGTH(tags) is null 
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
            ARRAY_LENGTH(tags) is null -- length of an empty array is NULL
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
