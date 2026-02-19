# GSD-Lite Inbox

## Active Loops

### [LOOP-001] - Hierarchy cascade behavior on parent deletion - Status: Open
**Created:** 2026-02-19 | **Source:** LOG-014 | **Origin:** User

**Context:** During capture matrix analysis (LOG-014), the question arose: when a project is hard-deleted, does the API explicitly emit the child tasks in `syncTaskBean.delete[]`? When a group is ungrouped, do the child projects get their `groupId` nulled in the same `projectProfiles[]` delta? These behaviors were not captured.

**Details:**
- Q1: Project hard-delete → are orphaned tasks emitted in `syncTaskBean.delete[]` in the same or next delta?
- Q2: Group ungroup → do child projects get `groupId: null` in `projectProfiles[]`, or does `groupId` silently point to a now-absent group?
- In capture 11 (ungroup), `projectProfiles` was null in poll 2 — could not determine Q2 from existing evidence.
- In capture 12 (project hard-delete), no tasks were in the project at time of deletion — Q1 remains untested.

**Phase-1 decision:** Poller captures 1-1. Orphaned FKs (`projectId`, `groupId`) resolved at query time in dbt via `LEFT JOIN`. This loop does not block Phase-1 build.

**To resolve:** Create a project, add 2-3 tasks, hard-delete the project, inspect whether `syncTaskBean.delete[]` carries the child tasks. Separately: create a group with 2 projects, ungroup, inspect `projectProfiles[]` for `groupId` field on the former children.

**Resolution:** _(pending)_

## Resolved Loops