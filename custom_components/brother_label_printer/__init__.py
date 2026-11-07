"""Local text-label printing for a Brother PT-P900W(c)."""

import asyncio
import logging
from datetime import timedelta

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .status import read_status

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import DOMAIN, TAPES
from .printer import encode_job, render_label, submit_job

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
SERVICE_SCHEMA = vol.Schema({
    vol.Required("text"): vol.All(cv.string, vol.Length(min=1, max=500)),
    vol.Optional("verify_tape", default=False): cv.boolean,
    vol.Optional("tape_width"): vol.All(vol.Coerce(int), vol.In(TAPES)),
    vol.Optional("font_size", default=64): vol.All(vol.Coerce(int), vol.Range(min=16, max=160)),
    vol.Optional("copies", default=1): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
    vol.Optional("auto_cut", default=True): cv.boolean,
    vol.Optional("half_cut", default=False): cv.boolean,
})


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register the action even when the printer is offline."""
    async def print_label(call: ServiceCall):
        runtime = hass.data.get(DOMAIN)
        if runtime is None:
            raise ServiceValidationError("Configure Brother Label Printer first")
        entry, lock, coordinator = runtime
        width = call.data.get("tape_width", entry.data["tape_width"])
        # Reject overlapping requests instead of building an unbounded queue.
        if lock.locked():
            raise ServiceValidationError("A label submission is already in progress")
        async with lock:
            try:
                label = await hass.async_add_executor_job(
                    render_label, call.data["text"], width, call.data["font_size"]
                )
                payload = await hass.async_add_executor_job(
                    encode_job, label, width, call.data["copies"],
                    call.data["auto_cut"], call.data["half_cut"],
                )
            except ValueError as err:
                raise ServiceValidationError(str(err)) from err
            if call.data["verify_tape"]:
                detected = await fresh_status(coordinator)
                if detected['error'] or detected['media_type'] != 1 or detected['tape_width_mm'] != width:
                    raise ServiceValidationError(
                        f"Tape check failed: expected {width} mm TZe, detected "
                        f"{detected['tape_width_mm']} mm (errors {detected['error_bytes']}). "
                        "Check the cassette and try again.")
            try:
                submission = hass.async_add_executor_job(
                    submit_job, entry.data["host"], entry.data["port"], payload
                )
                try:
                    await asyncio.shield(submission)
                except asyncio.CancelledError:
                    # Cancellation cannot stop a socket operation in a worker.
                    # Retain the lock until it finishes to prevent overlapping jobs.
                    try:
                        await submission
                    except OSError:
                        pass
                    raise
            except OSError as err:
                raise HomeAssistantError(
                    "Printer submission failed. Check the printer before retrying; "
                    "the label may already have been received."
                ) from err
        return {"status": "submitted", "copies": call.data["copies"],
                "tape_width_mm": width}

    hass.services.async_register(DOMAIN, "print_label", print_label,
                                 schema=SERVICE_SCHEMA, supports_response=SupportsResponse.OPTIONAL)
    async def get_status(call):
        runtime = hass.data.get(DOMAIN)
        if runtime is None:
            raise ServiceValidationError("Configure Brother Label Printer first")
        return await fresh_status(runtime[2])

    hass.services.async_register(DOMAIN, "get_status", get_status,
                                 schema=vol.Schema({}), supports_response=SupportsResponse.ONLY)
    return True


async def fresh_status(coordinator):
    # Explicit refresh bypasses the polling interval and debouncer cache.
    await coordinator.async_refresh()
    if not coordinator.last_update_success or coordinator.data is None:
        raise HomeAssistantError("Cannot detect tape. Check printer/SNMP or choose a manual width.")
    return coordinator.data


async def async_setup_entry(hass, entry) -> None:
    registry = dr.async_get(hass)
    device = registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, entry.unique_id)},
        name="Brother Label Printer", manufacturer="Brother", model=entry.data.get("model_override") or "Unknown",
    )
    async def update():
        try:
            status = await read_status(entry.data['host'])
            model = entry.data.get('model_override') or status['model']
            current = registry.async_get(device.id)
            if current is not None and current.model != model:
                registry.async_update_device(device.id, model=model)
            return status
        except Exception as err:
            raise UpdateFailed(f"Cannot read Brother tape status: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass, logging.getLogger(__name__), name='Brother label status',
        update_method=update, update_interval=timedelta(seconds=30), config_entry=entry)
    # An offline SNMP endpoint must not prevent manual printing.
    await coordinator.async_refresh()
    hass.data[DOMAIN] = (entry, asyncio.Lock(), coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, ['sensor'])


async def async_unload_entry(hass, entry) -> None:
    await hass.config_entries.async_unload_platforms(entry, ['sensor'])
    runtime = hass.data.get(DOMAIN)
    if runtime:
        async with runtime[1]:
            hass.data.pop(DOMAIN, None)
