---
symptom: "Dagster UI unreachable after a reboot" / "no new ingest runs since the host restarted" / "cannot assign requested address" / "ticktick-ingest container Exited or Created"
area: ingest stack host (EL/ticktick/ingest/docker/docker-compose.yml, EL/ticktick/ingest/docker/host/)
verified: 2026-10-11
---

# After a host reboot the ingest stack is silently down

**Symptom.** After the host restarts, the Dagster UI does not answer and no new
runs appear. Nothing alerts: the failure sensor lives inside the container that did
not start. `docker ps -a` shows the `dagster` container as `Exited` or `Created`,
and `docker inspect` or `journalctl -u docker` mentions
`cannot assign requested address` for the UI port.

**Applies only when `DAGSTER_WEB_BIND` is a VPN address.** Production now binds
`0.0.0.0` (behind a provider-level firewall that blocks the port publicly), which
cannot fail at boot; the drop-in stays installed there as a harmless guard.

**Mechanism.** The UI is published on `DAGSTER_WEB_BIND`, here the host's VPN
(Tailscale) address. That address exists only once `tailscaled` has
connected. On boot `dockerd` brings up `unless-stopped` containers as soon as it
starts, and stock `docker.service` is ordered only after `network-online.target`,
not after Tailscale. If dockerd wins the race, the port bind fails, the container
does not start, and the restart policy does not retry a container that failed at
daemon start.

**Fix.** Bind `0.0.0.0` behind a provider-level firewall (Docker-published ports
bypass host ufw, so a host firewall alone does not protect the port), or install the drop-in `EL/ticktick/ingest/docker/host/wait-for-tailscale.conf`
on the host (steps in `EL/ticktick/ingest/README.md`, "Reboot ordering"). It orders
`docker.service` after `tailscaled.service` and runs `tailscale wait --timeout=60s`
before dockerd starts. A failed or timed-out wait is ignored, so a host with a broken
Tailscale still starts docker after 60 s. To recover a host that is already in this
state: `docker compose -p ticktick-ingest up -d` from `EL/ticktick/ingest/docker/`.

**Verify.** `systemctl show docker -p After -p ExecStartPre` lists
`tailscaled.service` and the `tailscale wait` line. Installing needs only
`systemctl daemon-reload`; it takes effect on the next boot, so a real reboot is
the only end-to-end test.

**General rule.** A port published on an address that a separate daemon assigns
needs that daemon ordered before dockerd. Restart policies cover crashes, not a
container that never started.
