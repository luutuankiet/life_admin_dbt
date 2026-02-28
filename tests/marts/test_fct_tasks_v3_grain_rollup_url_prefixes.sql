select
    grain_rollup_id,
    grain_level,
    grain_url_web,
    grain_url_native,
    parent_grain_url_web,
    parent_grain_url_native
from {{ ref('fct_tasks_v3_grain_rollup') }}
where
    case
        when grain_level = 'task' then not (
            grain_url_web like 'https://ticktick.com/webapp/#p/%/tasks/%'
            and grain_url_native like 'ticktick://ticktick.com/webapp/#p/%/tasks/%'
            and parent_grain_url_web like 'https://ticktick.com/webapp/#p/%/tasks'
            and parent_grain_url_native like 'ticktick://ticktick.com/webapp/#p/%/tasks'
        )
        when grain_level = 'project' then not (
            grain_url_web like 'https://ticktick.com/webapp/#p/%/tasks'
            and grain_url_native like 'ticktick://ticktick.com/webapp/#p/%/tasks'
            and parent_grain_url_web like 'https://ticktick.com/webapp/#g/%'
            and parent_grain_url_native like 'ticktick://ticktick.com/webapp/#g/%'
        )
        when grain_level = 'folder' then not (
            grain_url_web like 'https://ticktick.com/webapp/#g/%'
            and grain_url_native like 'ticktick://ticktick.com/webapp/#g/%'
            and parent_grain_url_web like 'https://ticktick.com/webapp/#g/%'
            and parent_grain_url_native like 'ticktick://ticktick.com/webapp/#g/%'
        )
        else true
    end