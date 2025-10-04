{# models/marts/fct_task_tags_bridge.sql #}

{#
This bridge table connects tasks to their associated tags. The grain of
this table is one row per task-tag relationship.
#}

WITH

task_tags_source AS (
    {# Source: Staging model that unnests tags for each task. #}
    SELECT
        task_id,
        tag
    FROM
        {{ ref('stg__ticktick__task_tags') }}
),

dim_tags AS (
    {# Source: Dimension model for tags. #}
    SELECT
        tag_id,
        tag
    FROM
        {{ ref('dim_tags') }}
)

SELECT
    task_tags_source.task_id,
    dim_tags.tag_id
FROM
    task_tags_source
INNER JOIN
    dim_tags
    ON task_tags_source.tag = dim_tags.tag
