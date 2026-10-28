"""Fetch NLVE's private API into an atomic HAI Generic JSON Feed file."""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import requests


def _validate_url(raw_url: str) -> str:
    """Accept one operator-selected origin, without URL credentials or routing data."""
    error = "NLVE_API_URL must be an HTTPS origin or a literal loopback HTTP origin"
    if not isinstance(raw_url, str) or re.search(r"[\s\\\x00-\x1f\x7f]", raw_url):
        raise ValueError(error)
    try:
        parsed = urlsplit(raw_url)
        host = parsed.hostname
        port = parsed.port
        if (
            not host
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
            or "?" in raw_url
            or "#" in raw_url
            or "%" in parsed.netloc
            or (port is not None and not 1 <= port <= 65535)
            or (parsed.netloc.endswith(":"))
        ):
            raise ValueError(error)
        if parsed.scheme != "https" and not (
            parsed.scheme == "http" and host in {"127.0.0.1", "localhost", "::1"}
        ):
            raise ValueError(error)
        if ":" in host:
            if not re.fullmatch(r"\[[0-9a-fA-F:.]+\](?::[0-9]+)?", parsed.netloc):
                raise ValueError(error)
            authority = "[" + ipaddress.IPv6Address(host).compressed + "]"
        else:
            if "[" in parsed.netloc or "]" in parsed.netloc:
                raise ValueError(error)
            authority = host.encode("idna").decode("ascii").lower()
            if len(authority) > 253 or not all(
                re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                for label in authority.removesuffix(".").split(".")
            ):
                raise ValueError(error)
        if port is not None:
            authority += f":{port}"
        return urlunsplit((parsed.scheme, authority, "", "", ""))
    except (ValueError, UnicodeError):
        raise ValueError(error) from None


class _BearerAuth(requests.auth.AuthBase):
    """Keep an explicit bearer token authoritative over ambient netrc credentials."""

    def __init__(self, token: str):
        self._token = token

    def __call__(self, request):
        request.headers["Authorization"] = f"Bearer {self._token}"
        return request


def _validate_feed(payload: object) -> dict:
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise ValueError("NLVE returned an invalid HAI feed envelope")
    if len(payload["items"]) > 500:
        raise ValueError("NLVE returned more than 500 HAI feed items")
    for index, item in enumerate(payload["items"]):
        if not isinstance(item, dict):
            raise ValueError(f"HAI feed item {index} is not an object")
        for required in ("externalId", "provider", "itemType"):
            if not str(item.get(required) or "").strip():
                raise ValueError(f"HAI feed item {index} is missing {required}")
        if item.get("provider") != "generic_json_feed":
            raise ValueError(f"HAI feed item {index} has an unsupported provider")
    return payload


def sync_feed(api_url: str, token: str, output_path: str, limit: int = 100) -> dict:
    """Fetch one bounded feed and replace the destination only after validation."""
    base_url = _validate_url(api_url)
    token = token.strip()
    if len(token) < 32:
        raise ValueError("NLVE_API_TOKEN must contain at least 32 characters")
    if not 1 <= int(limit) <= 500:
        raise ValueError("limit must be between 1 and 500")

    try:
        with requests.get(
            f"{base_url}/api/v1/hai/feed",
            params={"limit": int(limit)},
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            auth=_BearerAuth(token),
            timeout=(5, 15),
            allow_redirects=False,
            stream=True,
        ) as response:
            if response.status_code != 200:
                raise RuntimeError(f"NLVE HAI feed request failed with HTTP {response.status_code}")
            payload = bytearray()
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if len(payload) + len(chunk) > 5 * 1024 * 1024:
                    raise RuntimeError("NLVE HAI feed exceeds 5 MiB")
                payload.extend(chunk)
    except requests.RequestException:
        raise RuntimeError("NLVE HAI feed request failed") from None
    try:
        decoded = json.loads(payload)
    except (ValueError, UnicodeError):
        raise RuntimeError("NLVE returned invalid JSON") from None
    feed = _validate_feed(decoded)

    destination = Path(output_path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(feed, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, destination)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)
    return {"path": str(destination), "items": len(feed["items"]), "cursor": feed.get("cursor", "")}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Sync the NLVE read-only HAI feed")
    parser.add_argument("output", help="HAI feed JSON destination")
    parser.add_argument("--url", default=os.environ.get("NLVE_API_URL", "http://127.0.0.1:8765"))
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args(argv)
    result = sync_feed(args.url, os.environ.get("NLVE_API_TOKEN", ""), args.output, args.limit)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
