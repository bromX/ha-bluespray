"""BlueSpray sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfTime, UnitOfVolumeFlowRate
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import BlueSprayConfigEntry
from .api import to_seconds
from .entity import BlueSprayEntity


@dataclass(frozen=True, kw_only=True)
class BSSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict, dict], Any]
    attrs_fn: Callable[[dict, dict], dict] | None = None
    # True for sensors that need /api/wx data. The slow coordinator only
    # fetches /api/wx while at least one such sensor is enabled.
    uses_wx: bool = False


def running_terminals(fast: dict) -> list[int]:
    now = to_seconds(fast.get("time")) or dt_util.utcnow().timestamp()
    out = []
    for z in fast.get("active_zones") or []:
        on, off = to_seconds(z.get("on")) or 0, to_seconds(z.get("off")) or 0
        if on <= now and (not off or now < off):
            out.append(z.get("terminal"))
    return out


def _flow(idx: int):
    def fn(fast: dict, _slow: dict):
        flow = (fast.get("sensors") or {}).get("flow") or []
        return flow[idx] if len(flow) > idx else None
    return fn


def _upcoming(slow: dict) -> list[dict]:
    now = dt_util.utcnow().timestamp()
    tasks = [
        t for t in slow.get("tasks", [])
        if not t.get("cancel") and (to_seconds(t.get("start_time")) or 0) > now
    ]
    return sorted(tasks, key=lambda t: to_seconds(t["start_time"]))


def _next_run(_fast: dict, slow: dict):
    up = _upcoming(slow)
    return dt_util.utc_from_timestamp(to_seconds(up[0]["start_time"])) if up else None


def _next_run_attrs(_fast: dict, slow: dict) -> dict:
    up = _upcoming(slow)
    if not up:
        return {}
    t = up[0]
    return {
        "schedule": t.get("schedule"),
        "program": t.get("program"),
        "duration_min": t.get("duration"),
        "runs": t.get("runs"),
        "manual": t.get("manual"),
    }


def _tasks_today(_fast: dict, slow: dict):
    today = [t for t in slow.get("tasks", []) if t.get("day", 0) == 0 and not t.get("cancel")]
    return len(today)


def _wx_first(kind: str, field: str):
    def fn(_fast: dict, slow: dict):
        items = ((slow.get("wx") or {}).get("forecast") or {}).get(kind) or []
        return items[0].get(field) if items else None
    return fn


def _wx_max_rain(_fast: dict, slow: dict):
    items = ((slow.get("wx") or {}).get("forecast") or {}).get("rain") or []
    vals = [i.get("por") for i in items if i.get("por") is not None]
    return max(vals) if vals else None


SENSORS: tuple[BSSensorDescription, ...] = (
    BSSensorDescription(
        key="flow_3s", name="Flow (3 s avg)", entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.GALLONS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT, value_fn=_flow(0),
    ),
    BSSensorDescription(
        key="flow_5s", name="Flow (5 s avg)", entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.GALLONS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT, value_fn=_flow(1),
    ),
    BSSensorDescription(
        key="flow_10s", name="Flow (10 s avg)", entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.GALLONS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT, value_fn=_flow(2),
    ),
    BSSensorDescription(
        key="active_zones", name="Active zones", state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda f, s: len(running_terminals(f)),
        attrs_fn=lambda f, s: {"terminals": running_terminals(f)},
    ),
    BSSensorDescription(
        key="next_run", name="Next run", device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_next_run, attrs_fn=_next_run_attrs,
    ),
    BSSensorDescription(key="tasks_today", name="Tasks today", value_fn=_tasks_today),
    BSSensorDescription(
        key="delay_days", name="Watering delay", device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.DAYS,
        value_fn=lambda f, s: (s.get("settings") or {}).get("delay"),
    ),
    BSSensorDescription(
        key="wx_rain_next", name="Forecast rain chance (next)", native_unit_of_measurement="%",
        entity_registry_enabled_default=False, uses_wx=True,
        value_fn=_wx_first("rain", "por"),
    ),
    BSSensorDescription(
        key="wx_rain_max", name="Forecast rain chance (max)", native_unit_of_measurement="%",
        entity_registry_enabled_default=False, uses_wx=True,
        value_fn=_wx_max_rain,
        attrs_fn=lambda f, s: {"threshold": (s.get("wx") or {}).get("rain"),
                               "forecast_hours": (s.get("wx") or {}).get("hr")},
    ),
    BSSensorDescription(
        key="wx_wind_next", name="Forecast wind (next)",
        entity_registry_enabled_default=False, uses_wx=True,
        value_fn=_wx_first("wind", "wind"),
        attrs_fn=lambda f, s: {"threshold": (s.get("wx") or {}).get("wind")},
    ),
    BSSensorDescription(
        key="wx_temp_next", name="Forecast temperature (next)",
        entity_registry_enabled_default=False, uses_wx=True,
        value_fn=_wx_first("temp", "temp"),
        attrs_fn=lambda f, s: {"threshold": (s.get("wx") or {}).get("temp")},
    ),
    BSSensorDescription(
        key="firmware", name="Firmware", entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda f, s: ((s.get("system") or {}).get("version") or {}).get("fw"),
    ),
    BSSensorDescription(
        key="controller_time", name="Controller time", entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.TIMESTAMP, entity_registry_enabled_default=False,
        value_fn=lambda f, s: dt_util.utc_from_timestamp(to_seconds(f["time"])) if to_seconds(f.get("time")) else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: BlueSprayConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    slow = entry.runtime_data.slow.data or {}
    has_flow = any(s.get("type") == 2 for s in slow.get("sensors", []))
    entities = [
        BlueSpraySensor(entry, d) for d in SENSORS
        if has_flow or not d.key.startswith("flow_")
    ]
    async_add_entities(entities)


class BlueSpraySensor(BlueSprayEntity, SensorEntity):
    entity_description: BSSensorDescription

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self.entity_description.uses_wx:
            # Only entities that are actually enabled get added, so this counts
            # the enabled forecast sensors. /api/wx is fetched only while > 0.
            self._slow.wx_consumers += 1
            self.async_on_remove(self._release_wx)
            if self._slow.wx_consumers == 1:
                # First forecast sensor enabled: fetch weather now.
                self.hass.async_create_task(self._slow.async_request_refresh())

    def _release_wx(self) -> None:
        self._slow.wx_consumers = max(0, self._slow.wx_consumers - 1)

    @property
    def native_value(self):
        return self.entity_description.value_fn(self._fast_data, self._slow_data)

    @property
    def extra_state_attributes(self):
        fn = self.entity_description.attrs_fn
        return fn(self._fast_data, self._slow_data) if fn else None
