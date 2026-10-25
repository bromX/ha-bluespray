"""BlueSpray binary sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BlueSprayConfigEntry
from .entity import BlueSprayEntity
from .sensor import running_terminals


@dataclass(frozen=True, kw_only=True)
class BSBinaryDescription(BinarySensorEntityDescription):
    value_fn: Callable[[dict, dict], bool | None]
    attrs_fn: Callable[[dict, dict], dict] | None = None


def _sensor_cfg(slow: dict, typ: int) -> dict:
    for s in slow.get("sensors", []):
        if s.get("type") == typ:
            return s
    return {}


def _rain_tripped(fast: dict, slow: dict):
    state = (fast.get("sensors") or {}).get("rain")
    if state is None:
        return None
    params = _sensor_cfg(slow, 1).get("params") or [0]
    normally_closed = params[0] == 1  # params[0]: 0 = normally open, 1 = normally closed
    # Status: 0 = opened, 1 = closed. Tripped = state differs from the resting state.
    return (state == 0) if normally_closed else (state == 1)


def _door_open(fast: dict, _slow: dict):
    state = (fast.get("sensors") or {}).get("door")
    return None if state is None else state == 0  # 0 = opened, 1 = closed


BINARY_SENSORS: tuple[BSBinaryDescription, ...] = (
    BSBinaryDescription(
        key="irrigating", name="Irrigating", device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda f, s: bool(running_terminals(f)),
        attrs_fn=lambda f, s: {"terminals": running_terminals(f)},
    ),
    BSBinaryDescription(
        key="rain_sensor", name="Rain sensor tripped", device_class=BinarySensorDeviceClass.MOISTURE,
        value_fn=_rain_tripped,
        attrs_fn=lambda f, s: {"raw_state": (f.get("sensors") or {}).get("rain"),
                               "bypassed": bool((s.get("settings") or {}).get("bypass"))},
    ),
    BSBinaryDescription(
        key="door_sensor", name="Door", device_class=BinarySensorDeviceClass.GARAGE_DOOR,
        value_fn=_door_open,
    ),
    BSBinaryDescription(
        key="system_on", name="Watering enabled",
        value_fn=lambda f, s: None if "state" not in (s.get("settings") or {}) else bool(s["settings"]["state"]),
    ),
    BSBinaryDescription(
        key="rain_bypass", name="Rain sensor bypassed", entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda f, s: None if "bypass" not in (s.get("settings") or {}) else bool(s["settings"]["bypass"]),
    ),
    BSBinaryDescription(
        key="firmware_update", name="Firmware update available",
        device_class=BinarySensorDeviceClass.UPDATE, entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda f, s: ((((s.get("system") or {}).get("version") or {}).get("latest")) or {}).get("update"),
        attrs_fn=lambda f, s: {"latest_fw": ((((s.get("system") or {}).get("version") or {}).get("latest")) or {}).get("fw")},
    ),
)


def _zone_description(zone: dict) -> BSBinaryDescription:
    terminal = zone.get("terminal")
    return BSBinaryDescription(
        key=f"zone_{zone.get('id')}",
        name=zone.get("name") or f"Zone {terminal}",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda f, s, t=terminal: t in running_terminals(f),
        attrs_fn=lambda f, s, z=zone: {
            "terminal": z.get("terminal"),
            "enabled": bool(z.get("enabled")),
            "flow_rate": z.get("flow"),
            "type": "light" if z.get("type") == 1 else "irrigation",
        },
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: BlueSprayConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    slow = entry.runtime_data.slow.data or {}
    types = {s.get("type") for s in slow.get("sensors", [])}
    skip = set()
    if 1 not in types:
        skip.add("rain_sensor")
    if 0 not in types:
        skip.add("door_sensor")
    descriptions = [d for d in BINARY_SENSORS if d.key not in skip]
    descriptions += [_zone_description(z) for z in slow.get("zones", [])]
    async_add_entities(BlueSprayBinarySensor(entry, d) for d in descriptions)


class BlueSprayBinarySensor(BlueSprayEntity, BinarySensorEntity):
    entity_description: BSBinaryDescription

    @property
    def is_on(self):
        return self.entity_description.value_fn(self._fast_data, self._slow_data)

    @property
    def extra_state_attributes(self):
        fn = self.entity_description.attrs_fn
        return fn(self._fast_data, self._slow_data) if fn else None
