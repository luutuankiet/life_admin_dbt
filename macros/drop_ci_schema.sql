{%- macro drop_ci_schema() -%}
    {{ adapter.dispatch('drop_ci_schema', 'dbt_utils')() }}
{%- endmacro -%}

{%- macro default__drop_ci_schema() -%}
{# defaults postgres syntax #}
    {% set schema_to_drop = env_var('CI_SCHEMA', 'ci') %}
    {% set sql %}
        DROP SCHEMA IF EXISTS "{{ schema_to_drop }}" CASCADE;
    {% endset %}
    
    {% do log("Dropping schema (Postgres syntax): " ~ "'" ~ schema_to_drop ~ "'", info=True) %}
    {% do run_query(sql) %}
    {% do log("CI schema dropped.", info=True) %}
{%- endmacro -%}

{%- macro bigquery__drop_ci_schema() -%}
    {% set schema_to_drop = env_var('CI_SCHEMA', 'ci') %}
    {% set sql %}
        DROP SCHEMA IF EXISTS `{{ schema_to_drop }}` CASCADE;
    {% endset %}
    
    {% do log("Dropping schema (BigQuery syntax): " ~ "'" ~ schema_to_drop ~ "'", info=True) %}
    {% do run_query(sql) %}
    {% do log("CI schema dropped.", info=True) %}
{%- endmacro -%}