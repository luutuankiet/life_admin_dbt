import asyncio
import contextlib
import json
import os

import httpx
import pytest

from ticktick_ingest import listener
from ticktick_ingest.client import AuthRejected, TickTickConfig

TOKEN = "6ac90cc98f082d55e43e2fbc----"
NEED_SYNC = json.dumps({"data": 1760000000000, "type": "needSync", "ctime": 1760000002000})
CONFIG = TickTickConfig(cookie_t="c" * 10, user_agent="UA", x_device='{"id":"x"}')


class FakeSocket:
    """Replays frames; raises ConnectionError once they run out (a drop)."""

    def __init__(self, frames):
        self.frames = list(frames)
        self.sent = []

    async def send(self, message):
        self.sent.append(message)

    async def recv(self):
        await asyncio.sleep(0)
        if not self.frames:
            raise ConnectionError("closed")
        return self.frames.pop(0)


class Clock:
    def __init__(self, start=1000):
        self.t = start

    def __call__(self):
        self.t += 1
        return self.t


def run(coro):
    return asyncio.run(coro)


async def _register_ok(token, seen):
    seen.append(token)


def test_write_hint_is_atomic_and_overwrites(tmp_path):
    listener.write_hint(tmp_path, 1)
    listener.write_hint(tmp_path, 1760000000123)
    assert (tmp_path / "last_hint").read_text() == "1760000000123"
    assert listener.read_hint(tmp_path) == 1760000000123
    assert os.listdir(tmp_path) == ["last_hint"]  # no temp file left behind


def test_write_hint_never_exposes_partial_file(tmp_path, monkeypatch):
    listener.write_hint(tmp_path, 42)

    def boom(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(listener.os, "replace", boom)
    with pytest.raises(OSError):
        listener.write_hint(tmp_path, 99)
    assert listener.read_hint(tmp_path) == 42
    assert os.listdir(tmp_path) == ["last_hint"]


def test_write_hint_creates_state_dir(tmp_path):
    listener.write_hint(tmp_path / "state", 7)
    assert listener.read_hint(tmp_path / "state") == 7


@pytest.mark.parametrize(
    ("frame", "expected"),
    [
        (NEED_SYNC, True),
        (NEED_SYNC.encode(), True),
        (TOKEN, False),
        ("hello", False),
        ('{"type":"other"}', False),
        ("[1,2]", False),
    ],
)
def test_is_need_sync(frame, expected):
    assert listener.is_need_sync(frame) is expected


def test_session_registers_first_frame_and_writes_hint_per_need_sync(tmp_path):
    ws = FakeSocket([TOKEN, NEED_SYNC, "hello", NEED_SYNC])
    seen, hints = [], []
    clock = Clock()

    with pytest.raises(ConnectionError):
        run(
            listener.run_session(
                ws,
                state_dir=tmp_path,
                register=lambda t: _register_ok(t, seen),
                clock=clock,
                on_hint=lambda ms, f: hints.append(ms),
            )
        )
    assert seen == [TOKEN]
    assert ws.sent[0] == "hello"
    assert hints == [1002, 1003]  # 1001 was the on-connect hint
    assert listener.read_hint(tmp_path) == 1003


def test_session_writes_hint_on_connect_before_any_frame(tmp_path):
    ws = FakeSocket([])
    with pytest.raises(ConnectionError):
        run(
            listener.run_session(
                ws, state_dir=tmp_path, register=lambda t: _register_ok(t, []), clock=Clock(5)
            )
        )
    assert listener.read_hint(tmp_path) == 6


def test_session_sends_hello_keep_alive(tmp_path):
    class SlowSocket(FakeSocket):
        async def recv(self):
            if self.frames:
                return self.frames.pop(0)
            await asyncio.sleep(0.05)
            raise ConnectionError("closed")

    ws = SlowSocket([TOKEN])
    with pytest.raises(ConnectionError):
        run(
            listener.run_session(
                ws, state_dir=tmp_path, register=lambda t: _register_ok(t, []),
                hello_interval=0.01,
            )
        )
    assert ws.sent.count("hello") >= 3


def _connector(sockets):
    it = iter(sockets)

    @contextlib.asynccontextmanager
    async def connect():
        yield next(it)

    return connect


def test_listen_reconnects_with_backoff_and_rewrites_hint(tmp_path):
    sleeps = []

    async def fake_sleep(s):
        sleeps.append(s)

    run(
        listener.listen(
            CONFIG,
            tmp_path,
            connect=_connector([FakeSocket([TOKEN]), FakeSocket([TOKEN]), FakeSocket([TOKEN])]),
            register=lambda t: _register_ok(t, []),
            sleep=fake_sleep,
            max_sessions=3,
        )
    )
    assert sleeps == [2.0, 4.0, 8.0]
    assert listener.read_hint(tmp_path) is not None


def test_listen_stops_on_auth_rejected_without_retry(tmp_path):
    calls = []

    async def reject(token):
        calls.append(token)
        raise AuthRejected("401 user_not_sign_on")

    async def no_sleep(s):
        raise AssertionError("must not back off and retry a 401")

    with pytest.raises(AuthRejected):
        run(
            listener.listen(
                CONFIG,
                tmp_path,
                connect=_connector([FakeSocket([TOKEN]), FakeSocket([TOKEN])]),
                register=reject,
                sleep=no_sleep,
            )
        )
    assert calls == [TOKEN]


def test_register_push_posts_token_and_raises_on_401():
    requests = []

    def handler(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(200, json={})
        return httpx.Response(401, json={"errorCode": "user_not_sign_on"})

    transport = httpx.MockTransport(handler)
    listener.register_push(CONFIG, TOKEN, transport=transport)
    req = requests[0]
    assert req.url.path == "/api/v2/push/register"
    assert json.loads(req.content) == {"pushToken": TOKEN, "osType": 41, "hl": "en_US"}
    assert req.headers["Cookie"] == "t=" + "c" * 10
    with pytest.raises(AuthRejected, match="user_not_sign_on"):
        listener.register_push(CONFIG, TOKEN, transport=transport)
    assert len(requests) == 2


def test_main_exits_non_zero_on_cookie_rejected(monkeypatch, tmp_path, caplog):
    async def fake_listen(config, state_dir, **kwargs):
        raise AuthRejected("401 user_not_sign_on")

    monkeypatch.setattr(listener, "listen", fake_listen)
    monkeypatch.setenv("INGEST_STATE_DIR", str(tmp_path))
    for name in ("INGEST_STACK_NAME", "TICKTICK_DEVICE_ID", "INGEST_LISTENER_IDLE_MINUTES"):
        monkeypatch.delenv(name, raising=False)
    for name in ("TICKTICK_COOKIE_T", "TICKTICK_USER_AGENT", "TICKTICK_X_DEVICE"):
        monkeypatch.setenv(name, "x")
    with caplog.at_level("ERROR"):
        assert listener.main() != 0
    assert "cookie rejected" in caplog.text


# ---------------------------------------------------------------- idle reconnect


class QuietSocket(FakeSocket):
    """Replays frames, then stays open and silent (no drop, no frame)."""

    async def recv(self):
        await asyncio.sleep(0)
        if self.frames:
            return self.frames.pop(0)
        await asyncio.Event().wait()


@pytest.mark.parametrize(
    ("raw", "seconds"), [(None, 3600.0), ("", 3600.0), ("5", 300.0), ("0.5", 30.0), ("0", None)]
)
def test_idle_timeout_from_env(raw, seconds):
    env = {} if raw is None else {"INGEST_LISTENER_IDLE_MINUTES": raw}
    assert listener.idle_timeout_from_env(env) == seconds


@pytest.mark.parametrize("raw", ["abc", "-1"])
def test_idle_timeout_rejects_garbage(raw):
    with pytest.raises(RuntimeError, match="INGEST_LISTENER_IDLE_MINUTES"):
        listener.idle_timeout_from_env({"INGEST_LISTENER_IDLE_MINUTES": raw})


def test_silent_session_raises_idle_after_one_hint(tmp_path):
    hints = []
    with pytest.raises(listener.ListenerIdle):
        run(
            listener.run_session(
                QuietSocket([TOKEN]),
                state_dir=tmp_path,
                register=lambda t: _register_ok(t, []),
                clock=Clock(),
                on_hint=lambda ms, f: hints.append(ms),
                idle_timeout=0.05,
            )
        )
    assert listener.read_hint(tmp_path) == 1001  # the on-connect hint only
    assert hints == []


def test_frames_inside_the_timeout_keep_the_session(tmp_path):
    class Trickle(QuietSocket):
        async def recv(self):
            if self.frames:
                await asyncio.sleep(0.03)  # each gap is under the timeout, the sum is over
            return await super().recv()

    hints = []
    with pytest.raises(listener.ListenerIdle):
        run(
            listener.run_session(
                Trickle([TOKEN, NEED_SYNC, NEED_SYNC, NEED_SYNC]),
                state_dir=tmp_path,
                register=lambda t: _register_ok(t, []),
                on_hint=lambda ms, f: hints.append(ms),
                idle_timeout=0.06,
            )
        )
    assert len(hints) == 3


def test_idle_session_reconnects_at_once_without_backoff(tmp_path, caplog):
    sleeps, seen = [], []

    async def fake_sleep(s):
        sleeps.append(s)

    with caplog.at_level("INFO"):
        run(
            listener.listen(
                CONFIG,
                tmp_path,
                connect=_connector([QuietSocket([TOKEN]), QuietSocket([TOKEN]), FakeSocket([])]),
                register=lambda t: _register_ok(t, seen),
                sleep=fake_sleep,
                max_sessions=3,
                idle_timeout=0.05,
            )
        )
    assert seen == [TOKEN, TOKEN]  # re-registered on the fresh socket
    assert sleeps == [2.0]  # only the third session's drop backs off
    assert caplog.text.count("no frame for") == 2
    assert caplog.text.count("reconnecting in") == 1


def test_no_idle_timeout_waits_forever(tmp_path):
    async def go():
        task = asyncio.create_task(
            listener.run_session(
                QuietSocket([TOKEN]), state_dir=tmp_path, register=lambda t: _register_ok(t, [])
            )
        )
        await asyncio.sleep(0.1)
        assert not task.done()
        task.cancel()

    run(go())
