"""Installed tape width, refreshed every 30 seconds."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([TapeWidth(hass.data[DOMAIN][2], entry)])


class TapeWidth(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_name = 'Tape width'
    _attr_native_unit_of_measurement = 'mm'
    _attr_icon = 'mdi:label-outline'

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_unique_id = f'{entry.unique_id}_tape_width'
        self._attr_device_info = {'identifiers': {(DOMAIN, entry.unique_id)}}
        self.entity_id = 'sensor.brother_label_printer_tape_width'

    @property
    def native_value(self):
        return self.coordinator.data['tape_width_mm'] if self.coordinator.data else None

    @property
    def extra_state_attributes(self):
        return self.coordinator.data or {}
