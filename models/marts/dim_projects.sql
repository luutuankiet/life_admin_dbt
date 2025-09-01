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
*
FROM stg_projects
