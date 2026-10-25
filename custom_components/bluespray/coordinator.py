"""Data coordinators: a fast one for live status, a slow one for everything else."""
from __future__ import annotations

import asyncio
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import BlueSprayClient, BlueSprayError, as_dict, as_list
from .const import DOMAIN, FAST_INTERVAL, SLOW_INTERVAL

_LOGGER = logging.getLogger(__name__)


class FastCoordinator(DataUpdateCoordinator[dict]):
    """Polls /api/status."""

    def __init__(self, hass: HomeAssistant, client: BlueSprayClient) -> None:
        super().__init__(hass, _LOGGER, name=f"{DOMAIN}_status", update_interval=FAST_INTERVAL)
        self.client = client

    async def _async_update_data(self) -> dict:
        try:
            return as_dict(await self.client.get("status"))
        except BlueSprayError as err:
            raise UpdateFailed(str(err)) from err


class SlowCoordinator(DataUpdateCoordinator[dict]):
    """Polls settings, system, zones, sensors, weather and tasks."""

    def __init__(self, hass: HomeAssistant, client: BlueSprayClient) -> None:
        super().__init__(hass, _LOGGER, name=f"{DOMAIN}_config", update_interval=SLOW_INTERVAL)
        self.client = client
        self.wx_consumers = 0  # number of enabled entities that need /api/wx

    async def _async_update_data(self) -> dict:
        c = self.client
        calls = {
            "settings": c.get("settings"),
            "system": c.get("system"),
            "zones": c.get("zones"),
            "sensors": c.get("sensors"),
            "tasks0": c.get("tasks", {"day": 0}),
            "tasks1": c.get("tasks", {"day": 1}),
        }
        if self.wx_consumers > 0:
            calls["wx"] = c.get("wx")

        results = await asyncio.gather(*calls.values(), return_exceptions=True)
        raw = dict(zip(calls, results))
        failed = [k for k, v in raw.items() if isinstance(v, Exception)]
        if len(failed) == len(raw):
            raise UpdateFailed("All BlueSpray requests failed")
        if failed:
            _LOGGER.debug("BlueSpray endpoints failed: %s", failed)

        old = self.data or {}

        def pick(key, fn, default):
            if key not in raw or key in failed:
                return default
            return fn(raw[key])

        tasks: list[dict] = []
        for key in ("tasks0", "tasks1"):
            if key not in failed:
                tasks.extend(as_dict(raw[key]).get("tasks") or [])

        return {
            "settings": pick("settings", as_dict, old.get("settings", {})),
            "system": pick("system", as_dict, old.get("system", {})),
            "zones": pick("zones", as_list, old.get("zones", [])),
            "sensors": pick("sensors", as_list, old.get("sensors", [])),
            "wx": pick("wx", as_dict, old.get("wx", {})),
            "tasks": tasks if not {"tasks0", "tasks1"} <= set(failed) else old.get("tasks", []),
        }
