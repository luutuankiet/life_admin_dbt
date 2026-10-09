---
symptom: "I fixed the snapshot model on main but the workflow still runs the old code" / "where is ticktick_fetcher.py" / "Serverless snapshot workflow has no schedule but ran every few minutes"
area: .github/workflows/serverless_snapshot.yml, incremental_run_gha branch
verified: 2026-10-09
---

# The snapshot workflow runs code from another branch

**Symptom.** You edit the extraction or snapshot logic on `main`, and the
scheduled pipeline ignores it. The workflow file has no `schedule:` block, yet
its history shows a run every 15 minutes.

**Mechanism.** Two things are split:

1. **Code lives off `main`.** `.github/workflows/serverless_snapshot.yml` is on
   `main` but its first step is:

   ```yaml
   uses: actions/checkout@v4
   with:
     ref: incremental_run_gha
   ```

   The comment there gives the reason: dispatch-triggered workflows must be
   defined on the default branch. So the YAML is on `main` and everything it
   executes (`ticktick_fetcher.py`, its own `dbt_project.yml`, `profiles.yml`,
   `snapshots/`) is on the long-lived branch `incremental_run_gha`. Last commit
   there: `eaec99a`, `2025-12-07`, "hotfix: pipeline crash when inbox 0".
2. **The trigger lives outside the repo.** The workflow listens for
   `repository_dispatch` of type `serverless_snapshot`. A scheduler somewhere
   else POSTs that event using a GitHub token. Nothing in this repository says
   where it runs or how often.

The two branches drift silently, and a fix on one never reaches the other.
The external scheduler can also keep spending Actions minutes or fail runs
while this repo shows no `cron:` anywhere.

**Fix.** The pipeline is retired. Keep the workflow disabled, delete the branch
and the workflow file when v1 is removed, and find and turn off whatever sends
the dispatch (it needs a GitHub token with repo scope, so revoke that token too).
Any future frequent job should keep its code and its schedule in the same branch
as its workflow.

**Verify.**

```sh
gh workflow list --all         # "Serverless snapshot" should be disabled_manually
gh run list --workflow serverless_snapshot.yml -L 5 --json event,createdAt
```

New `repository_dispatch` runs after the disable date mean the external
scheduler is still firing.

**General rule.** A workflow that checks out a different ref than the one it is
defined on is two programs. Treat the ref as part of the code under review.
