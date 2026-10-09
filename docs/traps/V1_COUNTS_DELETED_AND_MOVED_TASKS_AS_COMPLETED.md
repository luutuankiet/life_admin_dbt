---
symptom: "deleted task shows as completed" / "tasks in an archived list counted as done" / "completed_time equals the snapshot run time"
area: legacy v1 models (stg__ticktick__tasks, dbt snapshots)
verified: 2026-10-09
---

# The v1 chain counts every disappearance as a completion

**Symptom.** In the v1 models (`stg__ticktick__tasks`, `fct_tasks`), deleted
tasks, tasks in an archived list, and tasks whose list was deleted all appear as
completed. Their `completed_time` lands on a snapshot run boundary, not on when
you actually finished them.

**Mechanism.** The Open API only lists open tasks. The legacy pipeline ran
`dbt snapshot` with `strategy: check`, `check_cols: [id]`,
`invalidate_hard_deletes: true`. The only change it can detect is "this id is no
longer in the open list". `stg__ticktick__tasks.sql` then maps that to done:

```sql
dbt_valid_to as completed_time,
2 as status
```

Every reason a task leaves the open list looks the same: done, won't do,
deleted, list archived, list deleted. The timestamp is the run that noticed, so
its precision is the polling interval (15 minutes at the end). When a list is
un-archived, its tasks come back and the model has to un-complete them. The
dedupe comment in the same file covers that case: "task removed due to project
archived (completed), then project gets un-archived".

The pipeline also needed every run to succeed. A failed run widens the gap, and
the runs had been failing since `2026-02-18`.

**Fix.** Do not build on v1. The v3 source carries real status codes, a delete
list and `completedTime`. Its own gaps are in the other trap pages. Retire the
v1 chain (see `docs/architecture/legacy-v1-snapshot.md` for the list).

**Verify.** In v1 output, compare against v3 for one task id you know was
deleted. v1 shows `status = 2`, and v3 has no row (`deleted = 1` rows are
dropped in staging).

**General rule.** Absence is not an event. If a source only tells you what
exists now, you cannot tell why something stopped existing. Find a source that
emits the reason.
