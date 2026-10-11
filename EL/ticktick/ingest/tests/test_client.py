import json

import httpx
import pytest

from ticktick_ingest.client import (
    AuthRejected,
    TickTickClient,
    TickTickConfig,
    stack_device_id,
)

CONFIG = TickTickConfig(cookie_t="c" * 368, user_agent="UA/1.0", x_device='{"platform":"web"}')


def make_client(handler, **kw):
    sleeps: list[float] = []
    client = TickTickClient(
        CONFIG, transport=httpx.MockTransport(handler), sleep=sleeps.append, **kw
    )
    return client, sleeps


def test_fetch_delta_sends_web_app_headers(load):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=load("delta_empty.json"))

    client, _ = make_client(handler)
    delta = client.fetch_delta(1791561968860)
    assert delta["checkPoint"] == 1791561968860
    req = seen[0]
    assert req.url.path == "/api/v3/batch/check/1791561968860"
    assert req.headers["cookie"] == "t=" + "c" * 368
    assert req.headers["user-agent"] == "UA/1.0"
    assert req.headers["x-device"] == '{"platform":"web"}'
    assert req.headers["x-tz"] == "Asia/Ho_Chi_Minh"
    assert req.headers["hl"] == "en_US"


def test_401_raises_auth_rejected_without_retry():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(401, json={"errorCode": "user_not_sign_on"})

    client, sleeps = make_client(handler)
    with pytest.raises(AuthRejected, match="user_not_sign_on") as exc:
        client.fetch_delta(0)
    assert len(calls) == 1
    assert sleeps == []
    assert "c" * 20 not in str(exc.value)


def test_network_error_retries_then_succeeds(load):
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) < 3:
            raise httpx.ConnectError("boom", request=request)
        return httpx.Response(200, json=load("delta_empty.json"))

    client, sleeps = make_client(handler, backoff_seconds=1.0)
    assert client.fetch_delta(5)["checkPoint"] == 1791561968860
    assert len(calls) == 3
    assert sleeps == [1.0, 2.0]


def test_network_error_gives_up_after_two_retries():
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("slow", request=request)

    client, sleeps = make_client(handler)
    with pytest.raises(httpx.ReadTimeout):
        client.fetch_delta(5)
    assert len(calls) == 3
    assert len(sleeps) == 2


def test_server_error_is_not_retried():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(500)

    client, sleeps = make_client(handler)
    with pytest.raises(httpx.HTTPStatusError):
        client.fetch_delta(5)
    assert len(calls) == 1


def test_completed_page_params(load):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=load("completed_page.json"))

    client, _ = make_client(handler)
    rows = client.completed_page("2026-09-29 09:07:35")
    assert len(rows) == 6
    params = seen[0].url.params
    assert seen[0].url.path == "/api/v2/project/all/completedInAll/"
    assert params["to"] == "2026-09-29 09:07:35"
    assert params["from"] == ""
    assert params["limit"] == "1000"


def _row(i, t):
    return {"id": f"id{i}", "status": 2, "completedTime": f"{t}.000+0000"}


PAGES = {
    "": [_row(1, "2026-10-09T12:00:00"), _row(2, "2026-10-01T08:00:00")],
    "2026-10-01 08:00:00": [_row(2, "2026-10-01T08:00:00"), _row(3, "2026-09-01T00:00:00")],
    "2026-09-01 00:00:00": [_row(3, "2026-09-01T00:00:00")],
}


def _pages_handler(calls):
    def handler(request):
        to = request.url.params["to"]
        calls.append(to)
        return httpx.Response(200, content=json.dumps(PAGES[to]))

    return handler


def test_iter_completed_pages_to_floor_and_dedupes():
    calls = []
    client, _ = make_client(_pages_handler(calls))
    pages = list(client.iter_completed())
    assert [[r["id"] for r in p] for p in pages] == [["id1", "id2"], ["id3"]]
    assert calls == ["", "2026-10-01 08:00:00", "2026-09-01 00:00:00"]


def test_iter_completed_stops_at_cursor_inclusive():
    calls = []
    client, _ = make_client(_pages_handler(calls))
    pages = list(client.iter_completed(stop_at="2026-10-01 08:00:00"))
    assert [[r["id"] for r in p] for p in pages] == [["id1", "id2"]]
    assert calls == [""]


def test_config_from_env_and_repr_hides_cookie():
    env = {
        "TICKTICK_COOKIE_T": "secret" * 10,
        "TICKTICK_USER_AGENT": "UA",
        "TICKTICK_X_DEVICE": "{}",
    }
    cfg = TickTickConfig.from_env(env)
    assert cfg.timezone == "Asia/Ho_Chi_Minh"
    assert "secret" not in repr(cfg)
    with pytest.raises(RuntimeError, match="TICKTICK_COOKIE_T"):
        TickTickConfig.from_env({})


# ---------------------------------------------------------------- device id

DEVICE = '{"platform":"web","name":"browser","id":"aaaaaaaaaaaaaaaaaaaaaaaa","version":1}'


def _env(**extra):
    return {
        "TICKTICK_COOKIE_T": "c",
        "TICKTICK_USER_AGENT": "UA",
        "TICKTICK_X_DEVICE": DEVICE,
    } | extra


def test_x_device_sent_as_given_without_override():
    cfg = TickTickConfig.from_env(_env())
    assert cfg.x_device == DEVICE
    assert cfg.device_id == "aaaaaaaaaaaaaaaaaaaaaaaa"


def test_stack_name_replaces_only_the_device_id():
    cfg = TickTickConfig.from_env(_env(INGEST_STACK_NAME="ticktick-ingest"))
    sent = json.loads(cfg.headers()["X-Device"])
    assert sent["id"] == stack_device_id("ticktick-ingest")
    assert sent["id"] != "aaaaaaaaaaaaaaaaaaaaaaaa"
    rest = {k: v for k, v in sent.items() if k != "id"}
    assert rest == {"platform": "web", "name": "browser", "version": 1}


def test_each_stack_gets_its_own_stable_id():
    prod, e2e = stack_device_id("ticktick-ingest"), stack_device_id("ticktick-ingest-e2e")
    assert prod != e2e
    assert prod == stack_device_id("ticktick-ingest")
    assert len(prod) == 24 and int(prod, 16) >= 0


def test_explicit_device_id_wins_over_stack_name():
    cfg = TickTickConfig.from_env(
        _env(INGEST_STACK_NAME="ticktick-ingest", TICKTICK_DEVICE_ID="0123456789ABCDEF01234567")
    )
    assert cfg.device_id == "0123456789abcdef01234567"


@pytest.mark.parametrize("bad", ["123", "zz23456789abcdef01234567", "0123456789abcdef012345678"])
def test_malformed_explicit_device_id_is_refused(bad):
    with pytest.raises(RuntimeError, match="TICKTICK_DEVICE_ID"):
        TickTickConfig.from_env(_env(TICKTICK_DEVICE_ID=bad))


def test_override_on_non_json_x_device_is_refused():
    with pytest.raises(RuntimeError, match="not JSON"):
        TickTickConfig.from_env(_env(TICKTICK_X_DEVICE="nope", INGEST_STACK_NAME="s"))
