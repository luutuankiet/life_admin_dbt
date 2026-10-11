"""Websocket listener: turns TickTick's push channel into a "last hint" file.

TickTick has no webhooks. The web app keeps a socket open to
``wss://wss.ticktick.com/web``; the server sends one frame per change,
``{"data": <ms>, "type": "needSync", "ctime": <ms>}``, and the app then fetches the
sync delta. This process does the socket half only. It writes the current time in ms
to ``$INGEST_STATE_DIR/last_hint`` on every ``needSync`` frame and on every
(re)connect (frames sent while disconnected are lost, so a reconnect is a hint too).
The Dagster sensor reads that file and decides whether to fetch.

Protocol, as the web app does it:
- the first frame is a raw push token (not JSON); register it with
  ``POST /api/v2/push/register {"pushToken": <frame>, "osType": 41, "hl": "en_US"}``,
  otherwise no change frames arrive;
- send the text ``hello`` on open and every 540 s as keep-alive.

A 401 on register means the ``t`` cookie is dead: log "cookie rejected" and exit
non-zero. It is never retried and there is no login. Anything else (drop, network
error, non-401 register failure) reconnects with exponential backoff.

Idle reconnect: the server sends nothing between changes (no reply to ``hello``, no
heartbeat), so a socket whose registration was taken over looks exactly like a quiet
account. When no frame has arrived for ``INGEST_LISTENER_IDLE_MINUTES`` (default 60,
0 = never), the listener logs one line and reconnects at once. Like any reconnect,
that writes one hint, so a quiet account costs one empty fetch per idle period.

Run: ``python -m ticktick_ingest.listener``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import tempfile
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, Protocol

import httpx

from .client import AuthRejected, TickTickConfig, _error_code

WS_URL = "wss://wss.ticktick.com/web"
ORIGIN = "https://ticktick.com"
HELLO = "hello"
HELLO_INTERVAL_S = 540.0
BACKOFF_START_S = 2.0
BACKOFF_MAX_S = 300.0
HINT_FILE = "last_hint"
IDLE_MINUTES_DEFAULT = 60.0

log = logging.getLogger("ticktick_ingest.listener")


class ListenerIdle(Exception):
    """No frame arrived within the idle timeout."""


def idle_timeout_from_env(env: dict[str, str] | None = None) -> float | None:
    """Seconds from ``INGEST_LISTENER_IDLE_MINUTES`` (default 60); ``None`` when 0."""
    env = dict(os.environ) if env is None else env
    raw = (env.get("INGEST_LISTENER_IDLE_MINUTES") or "").strip()
    try:
        minutes = float(raw) if raw else IDLE_MINUTES_DEFAULT
    except ValueError as exc:
        raise RuntimeError(f"INGEST_LISTENER_IDLE_MINUTES is not a number: {raw!r}") from exc
    if minutes < 0:
        raise RuntimeError("INGEST_LISTENER_IDLE_MINUTES must be 0 (off) or more")
    return minutes * 60 if minutes > 0 else None


class Socket(Protocol):
    async def send(self, message: str) -> None: ...
    async def recv(self) -> str | bytes: ...


def now_ms() -> int:
    return int(time.time() * 1000)


def write_hint(state_dir: Path, ms: int) -> Path:
    """Write ``ms`` to ``state_dir/last_hint`` atomically: temp file in the same
    directory, fsync, then rename over the target. A reader never sees a partial file."""
    state_dir.mkdir(parents=True, exist_ok=True)
    target = state_dir / HINT_FILE
    fd, tmp = tempfile.mkstemp(prefix=f".{HINT_FILE}.", dir=state_dir)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(str(int(ms)))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return target


def read_hint(state_dir: Path) -> int | None:
    try:
        return int((state_dir / HINT_FILE).read_text().strip())
    except (FileNotFoundError, ValueError):
        return None


def is_need_sync(frame: str | bytes) -> bool:
    """True for a ``{"type": "needSync", ...}`` frame. Anything else (the push token,
    keep-alive echoes, unknown types) is not a hint."""
    if isinstance(frame, bytes):
        frame = frame.decode("utf-8", "replace")
    try:
        payload = json.loads(frame)
    except ValueError:
        return False
    return isinstance(payload, dict) and payload.get("type") == "needSync"


def register_push(config: TickTickConfig, token: str, *, transport=None) -> None:
    """Register the socket's push token. Raises ``AuthRejected`` on 401."""
    headers = config.headers() | {"Content-Type": "application/json;charset=utf-8"}
    body = {"pushToken": token, "osType": 41, "hl": config.locale}
    with httpx.Client(
        base_url=config.base_url, headers=headers, timeout=30.0, transport=transport
    ) as http:
        response = http.post("/api/v2/push/register", json=body)
    if response.status_code == 401:
        raise AuthRejected(f"TickTick rejected the t cookie (401 {_error_code(response)})")
    response.raise_for_status()


async def run_session(
    ws: Socket,
    *,
    state_dir: Path,
    register: Callable[[str], Awaitable[None]],
    clock: Callable[[], int] = now_ms,
    hello_interval: float = HELLO_INTERVAL_S,
    on_hint: Callable[[int, str], None] | None = None,
    idle_timeout: float | None = None,
) -> None:
    """Serve one connected socket until it closes (returns or raises).

    Writes a hint at once (a (re)connect is a hint), sends ``hello``, registers the
    first frame as the push token, then writes a hint per ``needSync`` frame. Raises
    ``ListenerIdle`` when no frame arrives for ``idle_timeout`` seconds."""

    async def recv() -> str | bytes:
        if idle_timeout is None:
            return await ws.recv()
        try:
            return await asyncio.wait_for(ws.recv(), idle_timeout)
        except TimeoutError:
            raise ListenerIdle(f"no frame for {idle_timeout / 60:g} min") from None

    write_hint(state_dir, clock())
    log.info("connected; hint written")
    await ws.send(HELLO)

    async def keep_alive() -> None:
        while True:
            await asyncio.sleep(hello_interval)
            await ws.send(HELLO)

    pinger = asyncio.create_task(keep_alive())
    try:
        token = await recv()
        if isinstance(token, bytes):
            token = token.decode("utf-8", "replace")
        await register(token)
        log.info("push token registered (%d chars)", len(token))
        while True:
            if pinger.done():  # keep-alive failed: surface its error
                pinger.result()
            frame = await recv()
            if is_need_sync(frame):
                ms = clock()
                write_hint(state_dir, ms)
                log.info("needSync %s -> last_hint=%d", _short(frame), ms)
                if on_hint is not None:
                    on_hint(ms, frame if isinstance(frame, str) else frame.decode())
            else:
                log.info("frame ignored: %s", _short(frame))
    finally:
        pinger.cancel()


def _short(frame: str | bytes, n: int = 120) -> str:
    text = frame if isinstance(frame, str) else frame.decode("utf-8", "replace")
    return text[:n]


async def listen(
    config: TickTickConfig,
    state_dir: Path,
    *,
    connect: Callable[[], Any] | None = None,
    register: Callable[[str], Awaitable[None]] | None = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    max_sessions: int | None = None,
    on_hint: Callable[[int, str], None] | None = None,
    idle_timeout: float | None = None,
) -> None:
    """Connect, serve, reconnect with backoff, forever. ``AuthRejected`` escapes.

    An idle session (``ListenerIdle``) reconnects at once, without backoff.

    ``connect`` returns an async context manager yielding a socket; ``register``
    registers a push token. Both default to the live TickTick endpoints."""
    if connect is None:
        connect = lambda: _ws_connect(config)  # noqa: E731
    if register is None:

        async def register(token: str) -> None:
            await asyncio.to_thread(register_push, config, token)

    backoff = BACKOFF_START_S
    sessions = 0
    while max_sessions is None or sessions < max_sessions:
        sessions += 1
        started = time.monotonic()
        try:
            async with connect() as ws:
                await run_session(
                    ws,
                    state_dir=state_dir,
                    register=register,
                    on_hint=on_hint,
                    idle_timeout=idle_timeout,
                )
        except AuthRejected:
            raise
        except ListenerIdle as exc:
            log.info("%s; reconnecting now", exc)
            backoff = BACKOFF_START_S
            continue
        except Exception as exc:  # drop, network error, non-401 register failure
            log.warning("socket session ended: %s: %s", type(exc).__name__, str(exc)[:200])
        # a session that lived a while resets the backoff
        if time.monotonic() - started > BACKOFF_MAX_S:
            backoff = BACKOFF_START_S
        log.info("reconnecting in %.0f s", backoff)
        await sleep(backoff)
        backoff = min(backoff * 2, BACKOFF_MAX_S)


def _ws_connect(config: TickTickConfig):
    from websockets.asyncio.client import connect

    return connect(
        WS_URL,
        additional_headers={"Cookie": f"t={config.cookie_t}", "Origin": ORIGIN},
        user_agent_header=config.user_agent,
        open_timeout=30,
        ping_interval=None,  # the server's keep-alive is the "hello" text, not WS pings
        max_size=2**20,
    )


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    state_dir = Path(os.environ.get("INGEST_STATE_DIR") or "/state")
    try:
        config = TickTickConfig.from_env()
        idle_timeout = idle_timeout_from_env()
    except RuntimeError as exc:
        log.error("%s", exc)
        return 2
    log.info("listening on %s; hints -> %s", WS_URL, state_dir / HINT_FILE)
    idle = f"{idle_timeout / 60:g} min" if idle_timeout else "off"
    log.info("device id %s; idle reconnect %s", config.device_id, idle)
    try:
        asyncio.run(listen(config, state_dir, idle_timeout=idle_timeout))
    except AuthRejected as exc:
        log.error("cookie rejected: paste a fresh t (%s)", exc)
        return 3
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
