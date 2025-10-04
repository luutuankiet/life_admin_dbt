{# models/marts/dim_tags.sql #}

{#
This model creates a dimension table for tags. The grain of this table
is one row per unique tag. A surrogate key (tag_id) is generated to
provide a stable, unique identifier for each tag.
#}

WITH

task_tags AS (
    {# Source: Bridge model that unnests tags from tasks. #}
    SELECT
        tag
    FROM
        {{ ref('stg__ticktick__task_tags') }}
),

distinct_tags AS (
    {# De-duplicate the tags to get a unique list. #}
    SELECT DISTINCT
        tag
    FROM
        task_tags
)

SELECT
    {#
    Generate a surrogate key for the tag. This is a best practice for
    dimension tables as it provides a stable key that won't change if the
    tag name is ever modified.
    #}
    {{ dbt_utils.generate_surrogate_key(['tag']) }} AS tag_id,
    tag
FROM
    distinct_tags
ORDER BY
    tag