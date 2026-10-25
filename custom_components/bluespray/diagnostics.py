"""Diagnostics for BlueSpray (Device page > Download diagnostics)."""
from __future__ import annotations

from homeassistant.components.diagnostics import async_redact_data

TO_REDACT = {
    "username", "password", "key", "ssid", "ipaddr", "gateway", "dns",
    "lat", "lng", "id", "ntp",
}


async def async_get_config_entry_diagnostics(hass, entry):
    data = entry.runtime_data
    return {
        "status": async_redact_data(data.fast.data or {}, TO_REDACT),
        "config": async_redact_data(data.slow.data or {}, TO_REDACT),
    }
