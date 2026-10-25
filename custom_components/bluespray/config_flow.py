"""Config flow for BlueSpray."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import BlueSprayClient, BlueSprayError, as_dict
from .const import DOMAIN


class BlueSprayConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors: dict[str, str] = {}
        if user_input is not None:
            client = BlueSprayClient(
                async_get_clientsession(self.hass),
                user_input[CONF_HOST],
                user_input.get(CONF_USERNAME),
                user_input.get(CONF_PASSWORD),
            )
            try:
                await client.get("status")
                system = as_dict(await client.get("system"))
            except BlueSprayError:
                errors["base"] = "cannot_connect"
            else:
                uid = str(system.get("id") or user_input[CONF_HOST])
                await self.async_set_unique_id(uid)
                self._abort_if_unique_id_configured()
                title = (system.get("system") or {}).get("hostname") or "BlueSpray"
                return self.async_create_entry(title=title, data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_USERNAME): str,
                vol.Optional(CONF_PASSWORD): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
