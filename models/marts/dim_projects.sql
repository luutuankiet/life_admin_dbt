{# models/marts/dim_projects.sql #}

{#
This model creates a dimension table for projects.
The grain of this table is one row per project.
#}

WITH

stg_projects AS (
    {# Source: Staging model for all projects. #}
    SELECT *
    FROM {{ ref('stg_projects') }}
)

SELECT
    {{ dbt_utils.generate_surrogate_key(['project_id']) }} AS project_key,
    project_id,
    name AS project_name,
    color AS project_color,
    kind AS project_kind,
    view_mode,
    sort_order,
    closed AS is_closed,
    completed_time
FROM stg_projects
