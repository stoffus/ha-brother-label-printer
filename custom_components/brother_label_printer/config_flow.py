"""Set up one local P-touch printer through the Home Assistant UI."""

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import config_validation as cv

from .const import DEFAULT_HOST, DEFAULT_PORT, DEFAULT_WIDTH, DOMAIN, TAPES
from .printer import check_connection


class BrotherLabelConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        errors = {}
        if user_input is not None:
            user_input["host"] = user_input["host"].strip().lower()
            try:
                await self.hass.async_add_executor_job(
                    check_connection, user_input["host"], user_input["port"]
                )
            except OSError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Brother Label Printer", data=user_input)
        defaults = user_input or {}
        return self.async_show_form(step_id="user", errors=errors, data_schema=vol.Schema({
            vol.Required("host", default=defaults.get("host", DEFAULT_HOST)): vol.All(cv.string, vol.Length(min=1, max=253)),
            vol.Required("port", default=defaults.get("port", DEFAULT_PORT)): cv.port,
            vol.Required("tape_width", default=defaults.get("tape_width", DEFAULT_WIDTH)): vol.In(TAPES),
        }))
