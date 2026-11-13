"""BlueSpray buttons: start a configured program as a manual run."""
from __future__ import annotations

import asyncio
import logging

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BlueSprayConfigEntry
from .api import BlueSprayError, manual_run_payload
from .entity import BlueSprayEntity
from .sensor import running_terminals

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: BlueSprayConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    slow = entry.runtime_data.slow
    known: set[int] = set()

    @callback
    def _add_new_programs() -> None:
        new = []
        for program in (slow.data or {}).get("programs", []):
            pid = program.get("id")
            if pid is None or pid in known:
                continue
            known.add(pid)
            new.append(BlueSprayProgramButton(entry, program))
        if new:
            async_add_entities(new)

    _add_new_programs()
    # Programs created on the controller later appear without a reload.
    entry.async_on_unload(slow.async_add_listener(_add_new_programs))


class BlueSprayProgramButton(BlueSprayEntity, ButtonEntity):
    """Pressing this starts the program immediately as a manual run."""

    _attr_icon = "mdi:play-circle"

    def __init__(self, entry: BlueSprayConfigEntry, program: dict) -> None:
        self._program_id = program["id"]
        super().__init__(entry, ButtonEntityDescription(key=f"program_{program['id']}"))

    @property
    def _program(self) -> dict | None:
        for program in self._slow_data.get("programs", []):
            if program.get("id") == self._program_id:
                return program
        return None

    @property
    def name(self) -> str:
        program = self._program
        if program and program.get("name"):
            return f"Run program - {program['name']}"
        return f"Run program {self._program_id}"

    @property
    def available(self) -> bool:
        # Unavailable if the program was deleted on the controller.
        return super().available and self._program is not None

    async def async_press(self) -> None:
        program = self._program
        if program is None:
            raise HomeAssistantError("This program no longer exists on the controller")
        payload = manual_run_payload(program)
        if payload is None:
            raise HomeAssistantError(f"Program '{program.get('name')}' has no run times")

        data = self._entry.runtime_data

        # Refuse to start while anything is already watering. Refresh the status
        # first so we don't rely on data that could be up to 30 seconds old.
        await data.fast.async_refresh()
        if not data.fast.last_update_success:
            raise HomeAssistantError(
                f"Program '{program.get('name')}' was not started: "
                "could not confirm the controller is idle"
            )
        slow_data = data.slow.data or {}
        running = running_terminals(data.fast.data or {}, slow_data)
        if running:
            zone_names = {
                z.get("terminal"): z.get("name") or f"Zone {z.get('terminal')}"
                for z in slow_data.get("zones", [])
            }
            active = ", ".join(zone_names.get(t, f"terminal {t}") for t in running)
            raise HomeAssistantError(
                f"Program '{program.get('name')}' was not started: "
                f"the controller is already irrigating ({active})"
            )

        _LOGGER.info("Starting program '%s' as a manual run: %s", program.get("name"), payload)
        try:
            result = await data.client.set("manual", payload)
        except BlueSprayError as err:
            raise HomeAssistantError(f"Could not start program: {err}") from err
        _LOGGER.debug("Manual run response: %s", result)

        # Give the controller a moment, then pull fresh status and task data.
        await asyncio.sleep(2)
        await data.fast.async_refresh()
        await data.slow.async_request_refresh()
