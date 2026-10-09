---
title: v1 (Open API) vs v3 (sync endpoint) task schema
summary: column-level differences between the two TickTick sources and their dbt chains
verified: 2026-10-09
---

# v1 vs v3 task schema

The two sources are different APIs, landed in different formats, and modelled
by two parallel dbt chains. They are not interchangeable column for column.

| aspect | v1: Open API | v3: web-app sync |
|---|---|---|
| landed as | JSONL in GCS, camelCase flattened to lowercase (`projectid`, `repeatflag`) | Parquet in GCS, snake_case columns plus the full object in `raw_json` |
| BigQuery tables | `tasks`, `tasks_snapshot`, `projects`, `projects_snapshot` | `tasks_v3`, `projects_v3`, `groups_v3` |
| which tasks | open only | open, done, won't do (recent window), deleted marker |
| `status` | always 0 at source; model sets 2 from snapshots | real: 0, 2, -1 |
| `completed_time` | snapshot `dbt_valid_to` (time the run noticed) | `completedTime` from TickTick |
| created / modified time | none; inferred from snapshot `dbt_valid_from` | `createdTime`, `modifiedTime` |
| deleted | not visible | `delete[]` lane; the poller removes the row, so `deleted = 1` never reaches BigQuery |
| folders | not in the API; derived from projects named with a folder convention | `groups_v3`, joined on `groupId` |
| archived project | disappears | `closed: true` |
| recurring series | `repeatFlag` on the open task | same; completed occurrences have no series link |
| extra fields | | `exDate`, `repeatFirstDate`, `completedUserId`, `etag`, `columnId`, ... |

## Model chains

| layer | v1 | v3 |
|---|---|---|
| base | `base__ticktick__tasks`, `base__ticktick__tasks_snapshot`, `base__ticktick__projects*` | `base__ticktick_v3__{tasks,projects,groups}` |
| staging | `stg__ticktick__{tasks,projects,project_folder,task_tags}` | `stg__ticktick_v3__{tasks,projects,project_folder}` |
| marts | `fct_tasks`, `dim_projects`, `dim_folders`, `fct_task_tags_bridge`, `dim_tags` | `fct_tasks_v3*`, `dim_projects_v3`, `dim_folders_v3`, `fct_habit*` |

The GTD work-type logic is duplicated across both staging task models. Change it
in both or retire v1 first.

`base__ticktick_v3__tasks.sql` reads each field as
`COALESCE(<typed column>, JSON_VALUE(raw_json, '$.<camelCase>'))`. A field the
emitter does not yet type is still reachable through `raw_json`.
