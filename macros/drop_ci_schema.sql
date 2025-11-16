{%- macro drop_ci_schema() -%}
    {{ adapter.dispatch('drop_ci_schema', 'dbt_utils')() }}
{%- endmacro -%}

{%- macro default__drop_ci_schema() -%}
{# defaults postgres syntax #}
    {% set schema_to_drop = env_var('DBT_CI_SCHEMA', 'ci') if env_var('DBT_CI_SCHEMA') == '' %}
    {% set sql %}
        DROP SCHEMA IF EXISTS "{{ schema_to_drop }}" CASCADE;
    {% endset %}
    
    {% do log("Dropping schema (Postgres syntax): " ~ "'" ~ schema_to_drop ~ "'", info=True) %}
    {% do run_query(sql) %}
    {% do log("CI schema dropped.", info=True) %}
{%- endmacro -%}

{%- macro bigquery__drop_ci_schema() -%}
    {# Retrieve the CI schema name from environment variables, defaulting to 'ci' #}
    {% set schema_to_drop = env_var('DBT_CI_SCHEMA', 'ci') %}

    {% if schema_to_drop %}
        {% set sql %}
            DROP SCHEMA IF EXISTS `{{ schema_to_drop }}` CASCADE;
        {% endset %}

        {% do log("Dropping schema (BigQuery syntax): " ~ "'" ~ schema_to_drop ~ "'", info=True) %}
        {% do run_query(sql) %}
        {% do log("CI schema dropped.", info=True) %}
    {% else %}
        {% do log("DBT_CI_SCHEMA is not set or is empty. Skipping schema drop.", info=True) %}
    {% endif %}
{%- endmacro -%}
