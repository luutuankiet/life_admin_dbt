---
symptom: "habit streak reset to zero after I renamed the recurring task" / "two different habits share one streak" / "how do I find all occurrences of a recurring task"
area: TickTick v3 source, fct_habit_streaks
verified: 2026-10-09
---

# Recurring-task occurrences carry no link to their series

**Symptom.** You rename a recurring habit in TickTick and its streak in Grafana
drops to zero, while the old name keeps a frozen streak. Or two habits with the
same title in different lists merge into one streak.

**Mechanism.** When you complete an occurrence of a recurring task, TickTick
stores the completed occurrence as its own task with a **new `id`**, and moves
the open task forward to the next date. The completed copy keeps no pointer
back to its series:

```
tasks_v3, status = 2 (completed):   2061 rows
  ... with a non-empty repeatFlag:     0
open tasks with a non-empty repeatFlag: 15
raw_json keys include repeatFirstDate, exDate, completedUserId
raw_json keys do NOT include any repeatTaskId / seriesId / originalId
```

The repeat rule (`repeatFlag`) lives only on the one open task. The completed
occurrences are ordinary tasks that happen to share its title. Heavy habits show
the scale: one daily habit has 129 completed occurrences and another has 121,
each with a different `task_id`.

`models/marts/fct_habit_streaks.sql` states the workaround in its header:

```
- Uses title as habit identifier (occurrences have different task_ids)
```

**Fix.** None in the current source. Options, in order of preference:

1. Find a series key in the private API. The web app shows recurring history, so
   some request links them. Capture it in the browser and check whether an
   occurrence carries `repeatTaskId` or similar.
2. Key on `(title, project_id)` instead of `title` alone. That stops cross-list
   merges but still breaks on rename.
3. Keep a small mapping table of old titles to a stable habit key.

**Verify.** Count completed rows with a non-empty repeat rule:

```sql
select countif(nullif(json_value(parse_json(raw_json),'$.repeatFlag'),'') is not null)
from `ticktick_raw.tasks_v3` where status = 2;
```

Anything above zero means TickTick started stamping occurrences, and this page
needs revisiting.

**General rule.** For a recurring item, ask the source what links an instance
to its series before you design any per-series metric. A shared display name is
not an identity.
