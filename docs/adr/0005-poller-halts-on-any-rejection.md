# The poller stops on any HTTP rejection and waits for a human

TickTick's private endpoint answers an expired session, a rate limit or a
changed contract with unpredictable 4xx and 5xx codes. Retrying every 30
seconds against a rejected session risks the account. So any HTTP error stops
the loop immediately, and network errors stop it after three in a row
(`TICKTICK_V3_ERROR_STREAK_HALT`).

## Consequences

Data silently goes stale until someone restarts the loop. The only signals are
the `ticktick_poller_state` metric and an ntfy alert. Any future redesign should
alert on data age, not process health.
