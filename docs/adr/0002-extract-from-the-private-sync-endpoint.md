# Extract from TickTick's private sync endpoint, not the Open API

The official Open API returns only open tasks, so completion had to be inferred
from dbt snapshots, which counted deletions and archives as completions. The
web app's own sync call, `/api/v3/batch/check/{checkpoint}`, returns real
status codes, completion times, a delete list and folders. We poll it every 30
seconds using a browser session cookie and a replayed `User-Agent`.

## Considered options

- **Open API plus snapshots (the v1 pipeline).** Rejected: cannot tell done from deleted.
- **Per-project completed endpoint (`/api/v2/project/{ids}/completed`) for backfill.**
  Rejected at the time: one request per project and still undocumented. History
  before the first sync was accepted as lost.

## Consequences

The integration can break with any TickTick web release, and the credential is
a human's browser session that expires. The poller stops on any rejection
rather than retrying.
