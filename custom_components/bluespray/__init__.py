"""BlueSpray irrigation controller (read-only)."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import BlueSprayClient
from .const import DOMAIN
from .coordinator import FastCoordinator, SlowCoordinator

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]


@dataclass
class BlueSprayData:
    client: BlueSprayClient
    fast: FastCoordinator
    slow: SlowCoordinator


type BlueSprayConfigEntry = ConfigEntry[BlueSprayData]


async def async_setup_entry(hass: HomeAssistant, entry: BlueSprayConfigEntry) -> bool:
    client = BlueSprayClient(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data.get(CONF_USERNAME),
        entry.data.get(CONF_PASSWORD),
    )
    fast = FastCoordinator(hass, client)
    slow = SlowCoordinator(hass, client)
    await fast.async_config_entry_first_refresh()
    await slow.async_config_entry_first_refresh()
    entry.runtime_data = BlueSprayData(client, fast, slow)

    # Register the controller device first so per-zone devices can link to it.
    system = (slow.data or {}).get("system") or {}
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=(system.get("system") or {}).get("hostname") or "BlueSpray",
        manufacturer="Avidz",
        model="BlueSpray",
        sw_version=(system.get("version") or {}).get("fw"),
        serial_number=system.get("id"),
        configuration_url=f"http://{entry.data[CONF_HOST]}",
    )

    @callback
    def _check_queue() -> None:
        # The controller queues task/zone/settings/season changes into the status
        # response. When something shows up there, refresh the slow data now.
        queue = (fast.data or {}).get("queue") or {}
        if any(queue.values()):
            hass.async_create_task(slow.async_request_refresh())

    entry.async_on_unload(fast.async_add_listener(_check_queue))
    # Coordinators only poll on a schedule while something is listening.
    # No entity listens to the slow coordinator directly, so add a no-op listener.
    entry.async_on_unload(slow.async_add_listener(lambda: None))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BlueSprayConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
