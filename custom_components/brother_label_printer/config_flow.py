"""Set up one local P-touch printer through the Home Assistant UI."""

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import config_validation as cv

from .const import DEFAULT_HOST, DEFAULT_PORT, DEFAULT_WIDTH, DOMAIN, TAPES
from .printer import check_connection
from .status import read_status


_LOGGER = logging.getLogger(__name__)


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
                self._printer_data = dict(user_input)
                self._detected_model = "Unknown"
                try:
                    status = await read_status(user_input["host"])
                    self._detected_model = status["model"]
                except Exception:
                    # Detection is optional: manual printing must work without SNMP.
                    _LOGGER.debug("Model detection unavailable during setup")
                return await self.async_step_model()
        defaults = user_input or {}
        return self.async_show_form(step_id="user", errors=errors, data_schema=vol.Schema({
            vol.Required("host", default=defaults.get("host", DEFAULT_HOST)): vol.All(cv.string, vol.Length(min=1, max=253)),
            vol.Required("port", default=defaults.get("port", DEFAULT_PORT)): cv.port,
            vol.Required("tape_width", default=defaults.get("tape_width", DEFAULT_WIDTH)): vol.In(list(TAPES)),
        }))

    async def async_step_model(self, user_input=None):
        """Show detection and allow an optional display-only override."""
        if user_input is not None:
            self._abort_if_unique_id_configured()
            data = {**self._printer_data,
                    "model_override": user_input.get("model_override", "").strip()}
            return self.async_create_entry(title="Brother Label Printer", data=data)
        return self.async_show_form(
            step_id="model",
            description_placeholders={"detected_model": self._detected_model},
            data_schema=vol.Schema({
                vol.Optional("model_override", default=""): vol.All(cv.string, vol.Length(max=64)),
            }),
        )

    async def async_step_reconfigure(self, user_input=None):
        """Edit connection and defaults without replacing the config entry."""
        entry = self._get_reconfigure_entry()
        errors = {}
        if user_input is not None:
            data = dict(user_input)
            data['host'] = data['host'].strip().lower()
            data['model_override'] = data.get('model_override', '').strip()
            if not data['host']:
                errors['host'] = 'invalid_host'
            elif (data['host'], data['port']) != (entry.data['host'], entry.data['port']):
                try:
                    await self.hass.async_add_executor_job(check_connection, data['host'], data['port'])
                except OSError:
                    errors['base'] = 'cannot_connect'
            if not errors:
                return self.async_update_reload_and_abort(entry, data_updates=data)
        defaults = user_input or entry.data
        return self.async_show_form(step_id='reconfigure', errors=errors, data_schema=vol.Schema({
            vol.Required('host', default=defaults['host']): vol.All(cv.string, vol.Length(min=1, max=253)),
            vol.Required('port', default=defaults['port']): cv.port,
            vol.Required('tape_width', default=defaults['tape_width']): vol.In(list(TAPES)),
            vol.Optional('model_override', default=defaults.get('model_override', '')): vol.All(cv.string, vol.Length(max=64)),
        }))
