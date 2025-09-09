{# models/marts/fct_tasks.sql #}

{#
This is the final fact model for tasks. The grain of this table is one row
per task instance, as it appears in the staging layer.

Habit-specific analytics, like streak calculations, are handled in a separate,
downstream model to keep this core fact table clean and focused.
#}

WITH

source AS (
    {# Source: Staging model for all tasks. #}
    SELECT *
    FROM {{ ref('stg__ticktick__tasks') }}
)

SELECT *

FROM source
