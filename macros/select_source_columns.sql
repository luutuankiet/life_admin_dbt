{% macro select_source_columns(source_relation) %}
    {{ dbt_utils.star(from=source_relation, except=var('airbyte_meta_fields')) }}
{% endmacro %}