"""Minimal client for the BlueSpray HTTP/JSON API."""
from __future__ import annotations

import asyncio
import random
from typing import Any

import aiohttp


class BlueSprayError(Exception):
    """Raised on any communication or protocol problem."""


def as_dict(result: Any) -> dict:
    """Normalise a 'result' payload to a single dict."""
    if isinstance(result, list):
        result = result[0] if result else {}
    return result if isinstance(result, dict) else {}


def as_list(result: Any) -> list[dict]:
    """Normalise a 'result' payload to a flat list of dicts."""
    if isinstance(result, dict):
        return [result]
    out: list[dict] = []
    for item in result or []:
        if isinstance(item, list):
            out.extend(i for i in item if isinstance(i, dict))
        elif isinstance(item, dict):
            out.append(item)
    return out


def list_from(result: Any, key: str) -> list[dict]:
    """Extract a list of dicts from {"<key>": [...]} (dict or one-element list)."""
    if (
        isinstance(result, list)
        and len(result) == 1
        and isinstance(result[0], dict)
        and key in result[0]
    ):
        result = result[0]
    if isinstance(result, dict):
        items = result.get(key)
        return [i for i in items if isinstance(i, dict)] if isinstance(items, list) else []
    return as_list(result)


def to_seconds(value: Any) -> float | None:
    """The controller mixes seconds and milliseconds since epoch; return seconds."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v / 1000 if v > 1e11 else v


def manual_run_payload(program: dict) -> dict | None:
    """Build a manual-run payload that starts a program's own settings now.

    Returns None if the program has no run times. `mv` is passed through as the
    program has it (this controller uses 0 = none, 1 = main, 2 = extra valve).
    """
    try:
        runs = [int(r) for r in program.get("runs") or []]
    except (TypeError, ValueError):
        return None
    if not any(r > 0 for r in runs):
        return None
    mv = program.get("mv", 0)
    if isinstance(mv, list):
        mv = mv[0] if mv else 0
    return {
        "start": 0,  # 0 = start immediately
        "unit": program.get("unit") or "m",
        "mv": mv,
        "pause": program.get("pause") or 0,
        "runs": runs,
    }


class BlueSprayClient:
    """Talks to http://<host>/api/<endpoint> using POST + JSON."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        self._session = session
        self._base = f"http://{host}/api"
        self._auth = (
            aiohttp.BasicAuth(username, password) if username and password else None
        )

    async def get(self, endpoint: str, data: dict | None = None) -> Any:
        return await self._request("get", endpoint, data)

    async def set(self, endpoint: str, data: Any) -> Any:
        return await self._request("set", endpoint, data)

    async def _request(self, action: str, endpoint: str, data: Any) -> Any:
        payload = {"action": action, "data": data, "id": random.randint(1, 99999)}
        try:
            async with asyncio.timeout(10):
                async with self._session.post(
                    f"{self._base}/{endpoint}", json=payload, auth=self._auth
                ) as resp:
                    resp.raise_for_status()
                    body = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise BlueSprayError(f"{endpoint}: {err}") from err
        if isinstance(body, dict) and "result" in body:
            return body["result"]
        return body
