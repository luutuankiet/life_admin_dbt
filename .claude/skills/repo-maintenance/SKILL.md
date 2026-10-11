---
name: repo-maintenance
description: This repo keeps a catalogue of its own traps — failure modes that produce no error, so you find them by symptom, not by stack trace — plus its reference pages and its decision records. Use before debugging behaviour that is wrong but not crashing, before editing shared state, and whenever you finish debugging something that cost more than an hour.
---

# Traps in this repo

Most of what has cost time here fails **silently**. There is no stack trace to
search, so the catalogue below is keyed on **the symptom you would observe**, not
on the subsystem at fault.

**Before you debug anything that misbehaves without erroring, scan this table.**
Then open exactly one file. Each page is self-contained — you will not need to
open a second one.

<!-- BEGIN GENERATED INDEX -- edit the pages, not this block -->

## Traps

Failure modes that produce no error message, indexed by the symptom you
would observe. Read before debugging behaviour that is wrong but not
crashing.

| symptom | page | area | verified |
|---|---|---|---|
| no completed tasks before 2025-05-28" / "history vanished after I reset the poller" / "completed count dropped after redeploy | [COMPLETED_TASKS_MISSING_BEFORE_A_DATE](../../../docs/traps/COMPLETED_TASKS_MISSING_BEFORE_A_DATE.md) | v3 poller replica, checkpoint sync | 2026-10-09 |
| habit streak reset to zero after I renamed the recurring task" / "two different habits share one streak" / "how do I find all occurrences of a recurring task | [HABIT_STREAK_RESETS_OR_MERGES_WHEN_A_RECURRING_TASK_IS_RENAMED](../../../docs/traps/HABIT_STREAK_RESETS_OR_MERGES_WHEN_A_RECURRING_TASK_IS_RENAMED.md) | TickTick v3 source, fct_habit_streaks | 2026-10-09 |
| Dagster UI unreachable after a reboot" / "no new ingest runs since the host restarted" / "cannot assign requested address" / "ticktick-ingest container Exited or Created | [INGEST_STACK_ABSENT_AFTER_HOST_REBOOT](../../../docs/traps/INGEST_STACK_ABSENT_AFTER_HOST_REBOOT.md) | ingest stack host (EL/ticktick/ingest/docker/docker-compose.yml, EL/ticktick/ingest/docker/host/) | 2026-10-11 |
| dashboard data stopped updating" / "ticktick_poller_state loop_running 0" / "action: loop_stopped" / "server_rejected | [POLLER_STOPPED_AND_DASHBOARD_FROZE](../../../docs/traps/POLLER_STOPPED_AND_DASHBOARD_FROZE.md) | v3 poller (EL/ticktick/v3/poller/service.py) | 2026-10-09 |
| I fixed the snapshot model on main but the workflow still runs the old code" / "where is ticktick_fetcher.py" / "Serverless snapshot workflow has no schedule but ran every few minutes | [SNAPSHOT_WORKFLOW_RUNS_CODE_THAT_IS_NOT_ON_MAIN](../../../docs/traps/SNAPSHOT_WORKFLOW_RUNS_CODE_THAT_IS_NOT_ON_MAIN.md) | .github/workflows/serverless_snapshot.yml, incremental_run_gha branch | 2026-10-09 |
| deleted task shows as completed" / "tasks in an archived list counted as done" / "completed_time equals the snapshot run time | [V1_COUNTS_DELETED_AND_MOVED_TASKS_AS_COMPLETED](../../../docs/traps/V1_COUNTS_DELETED_AND_MOVED_TASKS_AS_COMPLETED.md) | legacy v1 models (stg__ticktick__tasks, dbt snapshots) | 2026-10-09 |
| won't do tasks have null completed_time" / "skipped habit shows on the wrong day" / "open task has a completed_time | [WONT_DO_TASKS_MISSING_FROM_COMPLETED_METRICS](../../../docs/traps/WONT_DO_TASKS_MISSING_FROM_COMPLETED_METRICS.md) | stg__ticktick_v3__tasks, fct_habit_streaks, completed-activity marts | 2026-10-09 |

## Reference

Simply true, and expensive to re-derive.

| page | summary | verified |
|---|---|---|
| [Configuration and environment variables](../../../docs/reference/configuration.md) | every deployment-specific value, where it is set (GitHub, poller host, local .env), and its default | 2026-10-11 |
| [TickTick v3 sync payload semantics](../../../docs/reference/ticktick-v3-sync-payload.md) | what /api/v3/batch/check/{checkpoint} returns for each user action, and how the poller merges it | 2026-10-09 |
| [v1 (Open API) vs v3 (sync endpoint) task schema](../../../docs/reference/v1-vs-v3-schema.md) | column-level differences between the two TickTick sources and their dbt chains | 2026-10-09 |

## Decisions

Why the repo is the way it is. A merged decision is immutable -- supersede
it with a new one rather than editing it.

- [Replace the working-notes folder with indexed docs collections](../../../docs/adr/0001-replace-working-notes-with-docs-collections.md)
- [Extract from TickTick's private sync endpoint, not the Open API](../../../docs/adr/0002-extract-from-the-private-sync-endpoint.md)
- [Grafana for dashboards, dbt for semantics; Lightdash retired](../../../docs/adr/0003-grafana-over-lightdash.md)
- [Test Grafana dashboards with declarative contracts and one generic runner](../../../docs/adr/0004-grafana-contracts-as-data.md)
- [The poller stops on any HTTP rejection and waits for a human](../../../docs/adr/0005-poller-halts-on-any-rejection.md)
- [DuckDB copies the SQLite replica to GCS as Parquet after each changed cycle](../../../docs/adr/0006-duckdb-copies-the-replica-to-gcs.md)
- [The current extraction, storage and orchestration are legacy; redesign from the source up](../../../docs/adr/0007-current-extraction-storage-and-orchestration-are-legacy.md)

<!-- END GENERATED INDEX -->

The same tables, browsable, are [docs/README.md](../../../docs/README.md).

## Adding a trap

Write one when you have just spent real time on something that would have taken
minutes if someone had told you. Three tests, all must pass:

1. **It has a symptom.** If a fact is merely true, it is reference, not a trap.
   *If it has a symptom it is a trap; if it is just true it is reference.*
2. **Nothing cheaper catches it.** A doc is the *last* resort, because it only
   works if someone reads it. Stop at the first rung that holds:

   | rung | use when | this repo |
   |---|---|---|
   | make it a **type error** | the mistake is expressible in the type system | none; dbt SQL and the poller are untyped at build time |
   | make it a **test** | the mistake is an assertable behaviour | `uv run --group dev pytest tests/grafana -q` offline; `DBT_PROFILES_DIR=. uv run dbt test` against BigQuery (singular tests in `tests/marts/`) |
   | **comment at the site** | there is exactly one line where someone could get it wrong | yes, models open with a Jinja comment block; see the header of `models/marts/fct_habit_streaks.sql` |
   | **a doc** | the mistake can be made from any of several files, or from a file that does not exist yet | the catalogue above |

   Before adding one, say out loud which single line you would have commented
   instead — if you can name it, comment it and stop.
3. **It is not already in the table.** Extend the existing file. Two docs on one
   fact is how a catalogue rots.

Then:

- **Filename is the identifier.** `SCREAMING_SNAKE.md`, describing the symptom,
  not the fix. It is quoted in code comments and commit messages, so it never
  gets renamed — if the understanding changes, edit the body.
- **`symptom:` is the search key.** The string a frustrated person would paste
  into a search box, not a topic name. If the console prints something, put the
  console text verbatim.
- **Date it.** `verified:` is the day someone last confirmed it in the running
  code. An undated trap is a claim with no expiry.
- **Regenerate the index**: `scripts/gen-docs-index.sh`. The block above is
  generated; hand edits to it are overwritten.

## Writing the body

The reader is a maintainer six months from now who opened this one file from a
search result and has **no other context loaded**. Not you, not this session.

- Resolve every reference inline. No "see the other doc", no ticket numbers, no
  "as discussed". If a line number matters, quote the code.
- Publishing tone. It is a page on the project's documentation site, not a note
  to self.
- Lead with the symptom, then the mechanism, then the fix, then how to verify.
  Someone in the middle of a bug reads the first two lines and stops.
- Include the **evidence** — measured numbers, observed values, verbatim code. A
  trap without evidence gets argued with.
- **Say what is deliberate.** Half of what looks like a bug in a mature codebase
  is a trade someone made on purpose. Write down which, and what the trade was.

## The other collections

`docs/` holds five kinds of page, all generated into the same index by the same
script, all governed by the rules above:

| directory | what belongs there | frontmatter |
|---|---|---|
| `docs/traps/` | it has a symptom | `symptom`, `area`, `verified` |
| `docs/architecture/` | where behaviour lives — one page per area | `title`, `covers`, `verified` |
| `docs/reference/` | simply true, no symptom, worth not re-deriving | `title`, `summary`, `verified` |
| `docs/adr/` | **why the repo is the way it is** — a decision record | none; the `# ` heading is the entry |
| `docs/*.md` | a long-form guide belonging to no single area | `title`, `summary`, `verified` |

The architecture pages are the `codebase-map` skill's index; read that skill
before adding one. The escalation ladder does **not** apply to them — a map is not
a warning. Everything else does: date it, resolve references inline, regenerate
the index.

### Decision records

`docs/adr/NNNN-kebab-slug.md`, sequential, created lazily. Offer one only when
**all three** hold:

1. **hard to reverse** — if it is easy to reverse, skip it; you will just reverse it
2. **surprising without context** — otherwise the code explains itself
3. **the result of a real trade-off** — if there was no genuine alternative, there
   is nothing to record beyond "we did the obvious thing"

One to three sentences is a complete record: the context, what was decided, why.

**A merged record is immutable.** Superseding means a *new* file that names what
it replaces; the old one stays readable, because the reason a decision was made is
not invalidated by the decision changing.

This is the one destination that is append-only and unrecoverable. A trap can be
rewritten later; a rationale never written is gone.

## Removing a trap

**Before trusting a page, check it is still true.** These describe code, and code
moves. If the underlying cause is fixed, **delete the file** and say so in the
commit message. Do not leave it with a "fixed in vX" note — a stale trap costs a
reader the same time as a real one, and costs the catalogue its credibility, which
is the only thing making anyone open the next page. If the fix came with a comment
at the site, that comment is now the record.
