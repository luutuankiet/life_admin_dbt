{# models/marts/dim_date_spine.sql #}

{#
This model generates a continuous series of dates, providing a foundational
timeline for forward-looking analysis. It can be joined to fact tables
to ensure that all days are represented in a report, even if no events
occurred on a given day.
#}

{%- set timezone = 'Asia/Ho_Chi_Minh' -%}
{{ config(
    materialized = 'table'
)
}}

{{ dbt_utils.date_spine(
    datepart="day",
    start_date="CAST(" ~ dbt_date.today(timezone) ~ " AS DATE)",
    end_date="CAST(" ~ dbt.dateadd('month', 3, dbt_date.today(timezone)) ~ " AS DATE)"
) }}