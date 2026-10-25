"""Shared entity base."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BlueSprayConfigEntry
from .const import DOMAIN


class BlueSprayEntity(CoordinatorEntity):
    """All entities hang off the fast coordinator and also read the slow data."""

    _attr_has_entity_name = True

    def __init__(self, entry: BlueSprayConfigEntry, description) -> None:
        super().__init__(entry.runtime_data.fast)
        self._slow = entry.runtime_data.slow
        self.entity_description = description
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def _fast_data(self) -> dict:
        return self.coordinator.data or {}

    @property
    def _slow_data(self) -> dict:
        return self._slow.data or {}

    @property
    def device_info(self) -> DeviceInfo:
        system = self._slow_data.get("system", {})
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=(system.get("system") or {}).get("hostname") or "BlueSpray",
            manufacturer="Avidz",
            model="BlueSpray",
            sw_version=(system.get("version") or {}).get("fw"),
            serial_number=system.get("id"),
        )
