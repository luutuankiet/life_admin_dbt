# Replace the working-notes folder with indexed docs collections

Project knowledge used to live in a tracked `gsd-lite/` folder: a 321 KB
chronological work log, plus architecture, project and inbox files written
for one agent workflow. A new reader had to scroll the log to find which of
23 numbered decisions still held. One decision ("v3 delivers completion natively,
snapshots obsolete") turned out to be only half true against the data. We
rewrote the durable parts into `AGENTS.md` and `docs/{architecture,traps,reference,adr}`
with a generated index, opened GitHub issues for the open questions, and
deleted the folder.

## Considered options

- **Keep the folder and add an index on top.** Rejected: two stores of truth,
  and the log keeps growing faster than anyone re-reads it.
- **Promote the log as one long page.** Rejected: nobody finds a trap by
  scrolling. Traps are filed under their symptom instead.

## Consequences

The folder is still readable in git history before this commit. It contains
deployment identifiers, not credentials, and history was deliberately not
rewritten.
