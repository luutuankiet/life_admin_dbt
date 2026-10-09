---
title: TickTick v3 sync payload semantics
summary: what /api/v3/batch/check/{checkpoint} returns for each user action, and how the poller merges it
verified: 2026-10-09
---

# TickTick v3 sync payload semantics

The TickTick web app keeps itself current by calling
`GET /api/v3/batch/check/{checkpoint}`. The response carries a new checkpoint
and the changes since the one you sent. Checkpoint `0` means "everything you
would load on a fresh login". The endpoint is undocumented. It needs the
browser's session cookie `t` and a browser-like `User-Agent`.

The rules below come from twelve controlled captures made on `2026-02-19`: one
action in the web app, then one poll.

## Lanes

| field | when empty | when non-empty |
|---|---|---|
| `checkPoint` | always present | the next checkpoint to send |
| `syncTaskBean.update[]` | `[]` | tasks created or changed, full objects |
| `syncTaskBean.delete[]` | `[]` | `{taskId, projectId}` of deleted tasks |
| `syncTaskBean.deletedInTrash[]` | absent | mirrors `delete[]` |
| `syncTaskBean.empty` | `true` | `false` |
| `projectProfiles` | `null` | **the full list of projects**, not a delta |
| `projectGroups` | `null` | **the full list of folders (groups)** |
| `syncOrderBeanV3` | `null` | ordering data; not replicated |

Unrelated tasks sometimes show up in `update[]` as a side effect, for example a
`sortOrder` change when a project moves.

## Per action

| action | what arrives |
|---|---|
| create / edit task | task in `update[]` |
| complete task | task in `update[]` with `status: 2`, `completedTime` |
| won't do | task in `update[]` with `status: -1`, `completedTime` |
| delete task | `{taskId, projectId}` in `delete[]` and `deletedInTrash[]`; no tombstone in `update[]` |
| move task | task in `update[]` with the new `projectId` |
| create / rename project | full `projectProfiles` array |
| archive project | project stays in `projectProfiles` with `closed: true` |
| hard-delete project | project **absent** from the next full `projectProfiles`; no delete lane |
| create folder | full `projectGroups` array |
| assign project to folder | both arrays in one delta; project gets `groupId` |
| delete folder (ungroup) | folder **absent** from the next full `projectGroups`; no `deleted: 1` |

## How the poller merges

- Tasks: upsert from `update[]`, delete from `delete[]`.
- Projects and folders: when the field is non-null, **replace the whole table**.
  Absent id means deleted.
- No cascade: children of a deleted project or folder are not touched. Dangling
  `projectId`/`groupId` are resolved with `LEFT JOIN` in dbt.

## Not yet known

- Does hard-deleting a project that still has tasks send those tasks in
  `delete[]`? The capture used an empty project.
- After a folder is deleted, do its projects come back with `groupId: null`, or
  keep pointing at the missing folder? The capture's follow-up delta had
  `projectProfiles: null`.
- Is there any field or request linking a completed recurring occurrence to its
  series? See `docs/traps/HABIT_STREAK_RESETS_OR_MERGES_WHEN_A_RECURRING_TASK_IS_RENAMED.md`.
- How far back does the checkpoint-0 load go for closed tasks, and is the limit
  a count or a date?
