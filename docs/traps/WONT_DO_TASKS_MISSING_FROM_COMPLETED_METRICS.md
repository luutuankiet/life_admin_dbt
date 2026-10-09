---
symptom: "won't do tasks have null completed_time" / "skipped habit shows on the wrong day" / "open task has a completed_time"
area: stg__ticktick_v3__tasks, fct_habit_streaks, completed-activity marts
verified: 2026-10-09
---

# Won't-do loses its timestamp, and reopened tasks keep a stale one

**Symptom.** Any metric keyed on `completed_time` ignores tasks you marked
"won't do". Streak logic falls back to `updated_time`, so a skipped habit can
land on whatever day you last edited it. Separately, a few open tasks carry a
`completed_time`.

**Mechanism.** TickTick status codes are `0` open, `2` done, `-1` won't do. The
source sets `completedTime` for **both** closed states. Measured in
`ticktick_raw.tasks_v3`:

| status | rows | with completed_time | earliest |
|---|---|---|---|
| -1 | 354 | 354 | 2025-05-28 |
| 0 | 791 | 8 | |
| 2 | 2061 | 2061 | 2025-05-28 |

`models/staging/ticktick/stg__ticktick_v3__tasks.sql` keeps the timestamp only
for status `2`:

```sql
when status = 2 then _completed_time
```

So all 354 won't-do timestamps are thrown away. `fct_habit_streaks.sql` then
does `coalesce(completed_time, updated_time)`, and `updated_time` moves on every
edit.

The 8 open rows with a timestamp are tasks completed and then reopened.
TickTick does not clear `completedTime` on reopen. The staging `case` hides them
because it also checks status, but any query on `base__ticktick_v3__tasks` or
the raw table that filters only on `completed_time is not null` counts them.

**Fix.** Treat both closed states as closed:

```sql
when status in (2, -1) then _completed_time
```

Then add a `closed_reason` column (`done` or `wont_do`) so metrics that mean
"done" can still filter. Never use `completed_time` without a status filter.

**Verify.** The table above comes from:

```sql
select status, count(*), countif(completed_time is not null), min(completed_time)
from `ticktick_raw.tasks_v3` group by status;
```

After the fix, `stg__ticktick_v3__tasks` should have no status `-1` row with a
null `completed_time`.

**General rule.** A "closed" timestamp in a task system usually covers every
closed state, and it is rarely cleared on reopen. Derive it from status, not
next to it.
