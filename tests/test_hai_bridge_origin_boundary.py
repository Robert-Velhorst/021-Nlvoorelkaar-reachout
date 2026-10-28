"""Origin and authentication regressions using prepared requests, without egress."""

import json

import pytest
import requests

from connectors.hai_bridge import sync_feed


TOKEN = "synthetic-bearer-for-owned-regressions-only"


def capture_send(monkeypatch):
    calls = []

    def send(session, request, **kwargs):
        calls.append((request, kwargs))
        response = requests.Response()
        response.status_code = 200
        response._content = b'{"cursor":"owned","items":[]}'
        response._content_consumed = True
        return response

    monkeypatch.setattr(requests.Session, "send", send)
    return calls


@pytest.mark.parametrize(
    ("origin", "canonical"),
    [
        ("https://reachout.example.com", "https://reachout.example.com"),
        ("https://reachout.example.com/", "https://reachout.example.com"),
        ("https://REACHOUT.example.com:443/", "https://reachout.example.com:443"),
        ("https://reachout.example.com:8443", "https://reachout.example.com:8443"),
        ("https://[2001:db8::1]:443", "https://[2001:db8::1]:443"),
        ("http://127.0.0.1:8765", "http://127.0.0.1:8765"),
        ("http://localhost:8765/", "http://localhost:8765"),
        ("http://[::1]:8765", "http://[::1]:8765"),
    ],
)
def test_bridge_prepares_one_canonical_origin(origin, canonical, tmp_path, monkeypatch):
    monkeypatch.setenv("NETRC", str(tmp_path / "absent-owned.netrc"))
    calls = capture_send(monkeypatch)
    destination = tmp_path / "feed.json"
    result = sync_feed(origin, TOKEN, str(destination), 17)
    assert result["items"] == 0
    assert len(calls) == 1
    request, options = calls[0]
    assert request.url == canonical + "/api/v1/hai/feed?limit=17"
    assert request.headers["Authorization"] == "Bearer " + TOKEN
    assert options["allow_redirects"] is False
    assert options["timeout"] == (5, 15)
    assert json.loads(destination.read_text())["cursor"] == "owned"


@pytest.mark.parametrize(
    "origin",
    [
        "https://synthetic-user@reachout.example.com",
        "https://synthetic-user:synthetic-password@reachout.example.com",
        "https://reachout.example.com@other.example.com",
        "https://reachout.example.com/?next=other",
        "https://reachout.example.com?",
        "https://reachout.example.com/#fragment",
        "https://reachout.example.com#",
        "https://reachout.example.com/prefix",
        "https://reachout.example.com//",
        "https://reachout.example.com/%2f",
        "https://reachout.example.com:invalid",
        "https://reachout.example.com:0",
        "https://reachout.example.com:65536",
        "https://reachout.example.com:",
        "https://reachout.example.com..",
        "https://-invalid.example.com",
        "https://%72eachout.example.com",
        "https://reachout.example.com\\@other.example.com",
        "https://reachout.example.com\n",
        "https://reachout.\texample.com",
        " https://reachout.example.com",
        "https://reachout.example.com\x00",
        "https://[::1]suffix",
        "https://[::1]:443suffix",
        "https://[v1.example.com]",
        "http://other.example.com",
        "http://127.0.0.1.other.example.com",
        "http://127.1",
        "http://2130706433",
        "file:///tmp/feed.json",
        "//reachout.example.com",
        "https:///reachout.example.com",
        "",
    ],
)
def test_bridge_rejects_ambiguous_origin_before_request(origin, tmp_path, monkeypatch):
    calls = []

    def unexpected_get(*args, **kwargs):
        calls.append((args, kwargs))
        pytest.fail("Rejected origin reached the HTTP request boundary")

    monkeypatch.setattr(requests, "get", unexpected_get)
    destination = tmp_path / "feed.json"
    destination.write_text("preserved-private-feed")
    with pytest.raises(ValueError):
        sync_feed(origin, TOKEN, str(destination))
    assert calls == []
    assert destination.read_text() == "preserved-private-feed"


def test_bridge_explicit_bearer_wins_over_owned_netrc(tmp_path, monkeypatch):
    netrc = tmp_path / "owned.netrc"
    netrc.write_text(
        "machine reachout.example.com login synthetic-user password synthetic-password\n"
    )
    monkeypatch.setenv("NETRC", str(netrc))
    calls = capture_send(monkeypatch)
    sync_feed("https://reachout.example.com", TOKEN, str(tmp_path / "feed.json"))
    assert len(calls) == 1
    request, _ = calls[0]
    assert request.headers["Authorization"] == "Bearer " + TOKEN
    assert "synthetic-user" not in request.url
    assert "synthetic-password" not in request.url
