# TickTick ingestion

Loads TickTick tasks, closed tasks, lists and folders into BigQuery with dlt, orchestrated
by Dagster. Two containers run from one image. The **listener** holds TickTick's web-app
websocket open and writes a hint file to a shared volume whenever TickTick says something
changed. **Dagster** (webserver and daemon in one container) runs the `ticktick_sync` job:
the `hint_sensor` launches a sync shortly after each hint, the `safety_net` schedule runs
one every 30 minutes regardless, and a failure sensor posts to ntfy when a run fails. The
dbt models under `models/staging/ticktick/` read the resulting dataset.

## First deploy

On the host, as a user that can run Docker:

1. Clone the repo and check out the branch you deploy:

   ```sh
   git clone https://github.com/luutuankiet/life_admin_dbt <checkout>
   cd <checkout> && git checkout <branch>
   ```

2. In `EL/ticktick/ingest/docker/`, create `.env` from `.env.example` and put the
   BigQuery service-account key at `secrets/sa.json`. Both paths are gitignored; confirm
   with `git check-ignore -v docker/.env docker/secrets/sa.json` before writing them, then
   `chmod 600` both.
3. Start the stack from `EL/ticktick/ingest/docker/`:

   ```sh
   docker compose -p ticktick-ingest up -d --build
   ```

   Wait until the first sensor-launched run (Runs page) has finished before step 4:
   the listener writes a hint as soon as it connects, that hint starts a sync, and the
   sync and `cli backfill` share the same dlt working dir.
4. Load the full closed-task history once:

   ```sh
   docker compose -p ticktick-ingest exec dagster python -m ticktick_ingest.cli backfill
   ```

   After that the sensor and the schedule keep the dataset current.
5. Build the dbt models from the repo root with `TICKTICK_INGEST_DATASET` set to the same
   dataset the stack writes to.

## Redeploy

`git pull` in the checkout, then step 3 again. The `state` volume (hint file, gate cache,
dlt working dir, Dagster run history) survives a rebuild.

## Configuration

Every variable is listed, with a placeholder, in `docker/.env.example`: the TickTick
session (`TICKTICK_COOKIE_T`, `TICKTICK_USER_AGENT`, `TICKTICK_X_DEVICE`,
`TICKTICK_TIMEZONE`), the destination (`TICKTICK_INGEST_DATASET`, `DBT_BQ_PROJECT`,
`DBT_BQ_LOCATION`, `GOOGLE_APPLICATION_CREDENTIALS`), alerts (`NTFY_URL`), state
(`INGEST_STATE_DIR`) and the UI address (`DAGSTER_WEB_BIND`, `DAGSTER_WEB_PORT`). The
repo is public: real values go only in the ignored `docker/.env`.

Each stack sends its own TickTick device id, derived from the compose project name,
because TickTick pushes change hints to one socket per device id: a second stack
under the same id silences the first. A dev stack therefore needs only a different
`-p` name. `TICKTICK_DEVICE_ID` overrides the derived id; `INGEST_LISTENER_IDLE_MINUTES`
(default 60) sets how long the listener waits without a frame before it reconnects.

## CLI

Run inside the Dagster container so it shares the state volume:

```sh
docker compose -p ticktick-ingest exec dagster python -m ticktick_ingest.cli <command>
```

| command | what it does |
|---|---|
| `sync [--kind hint\|safety]` | fetch the delta since the stored checkpoint (what the scheduled runs do) |
| `backfill` | a sync, then page closed tasks back to the oldest available completion |
| `reset` | sync from checkpoint 0, merging every task |
| `rebuild-gate` | delete the local gate cache and rebuild it from the `tasks` table |

Do not run a CLI command while a Dagster run is in progress: both use the same dlt
working directory. Check the Runs page first.

## Dagster UI

Published on port `3070` of the address in `DAGSTER_WEB_BIND` (loopback by default).
Production sets `0.0.0.0` on a host whose provider-level firewall blocks every inbound
port from the internet, and reaches the UI over the VPN, either directly at the host's
VPN name on port `3070` or through a LAN reverse proxy that forwards a private hostname
there. A host firewall alone is not enough: Docker-published ports bypass ufw and host
iptables INPUT rules. After changing the bind, probe the host's public IP on `3070`
from outside the VPN; it must time out.

## Reboot ordering

Only needed when `DAGSTER_WEB_BIND` is a VPN address; with `0.0.0.0` the bind cannot
fail at boot and the drop-in is harmless but optional. When `DAGSTER_WEB_BIND` is a VPN
address (Tailscale), dockerd can start before that address exists. The port bind then fails with `cannot assign requested address` and the
`dagster` container stays down after a reboot, with no alert. Install the drop-in once
per host so docker waits for Tailscale:

```sh
sudo install -D -m 0644 EL/ticktick/ingest/docker/host/wait-for-tailscale.conf \
  /etc/systemd/system/docker.service.d/wait-for-tailscale.conf
sudo systemctl daemon-reload
systemctl show docker -p After -p ExecStartPre   # lists tailscaled.service and tailscale wait
```

No docker restart is needed; it applies from the next boot. The wait is capped at 60 s
and its failure is ignored, so a host with Tailscale logged out still starts every
container except the tailnet-bound port. Details: `docs/traps/INGEST_STACK_ABSENT_AFTER_HOST_REBOOT.md`.

## Alerts

A failed run posts to `NTFY_URL` with the title `ticktick-ingest failed`.

**`cookie rejected: paste a fresh t`** means TickTick answered 401: the web session
cookie expired or was signed out. Log in to TickTick in a browser, copy the value of the
`t` cookie, replace `TICKTICK_COOKIE_T` in `docker/.env`, and run
`docker compose -p ticktick-ingest up -d` to recreate both containers with it. Until
then the listener exits on every restart and every 30-minute safety run fails and alerts again.
