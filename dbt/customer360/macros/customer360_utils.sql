{% macro customer360_surrogate_key(columns) -%}
    sha2(
        concat_ws(
            '||',
            {%- for column in columns -%}
                coalesce(cast({{ column }} as varchar), '__dbt_null__')
                {%- if not loop.last %}, {% endif -%}
            {%- endfor -%}
        ),
        256
    )
{%- endmacro %}

{% macro customer360_standardize_company(column_name) -%}
    nullif(
        regexp_replace(
            regexp_replace(upper(trim({{ column_name }})), '\\b(CORP|CORPORATION|INC|LLC|LTD|CO|COMPANY)\\b', ''),
            '\\s+',
            ' '
        ),
        ''
    )
{%- endmacro %}

{% macro customer360_clean_text(column_name) -%}
    nullif(regexp_replace(upper(trim({{ column_name }})), '\\s+', ' '), '')
{%- endmacro %}

{% macro customer360_clean_email(column_name) -%}
    nullif(lower(trim({{ column_name }})), '')
{%- endmacro %}

{% macro customer360_clean_phone(column_name) -%}
    nullif(regexp_replace({{ column_name }}, '[^0-9]', ''), '')
{%- endmacro %}

{% macro customer360_clean_website(column_name) -%}
    nullif(regexp_replace(lower(regexp_replace(trim({{ column_name }}), '^https?://(www\\.)?', '')), '/.*$', ''), '')
{%- endmacro %}

{% macro customer360_incremental_watermark(source_column_name, target_column_name='last_modified_timestamp') -%}
    {% if is_incremental() %}
        and {{ source_column_name }} > (
            select coalesce(max({{ target_column_name }}), to_timestamp_ntz('1900-01-01 00:00:00'))
            from {{ this }}
        )
    {% endif %}
{%- endmacro %}
