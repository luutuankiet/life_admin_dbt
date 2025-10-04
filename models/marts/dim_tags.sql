{#
This model creates a dimension table for tags. The grain of this table
is one row per unique tag. A surrogate key (tag_id) is generated to
provide a stable, unique identifier for each tag.
#}

WITH

task_tags AS (
    {# Source: Bridge model that unnests tags from tasks. #}
    SELECT
        distinct tag
    FROM
        {{ ref('stg__ticktick__task_tags') }}
)

SELECT
    {{ dbt_utils.generate_surrogate_key(['tag']) }} AS tag_id,
    tag
FROM
    task_tags
ORDER BY
    tag