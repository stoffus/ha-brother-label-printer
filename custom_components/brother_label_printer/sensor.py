"""Printer status and tape polling, plus restored submission history."""
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][2]
    async_add_entities([TapeWidth(coordinator, entry), PrinterStatus(coordinator, entry),
                        PrinterErrors(coordinator, entry), LastSubmission(coordinator, entry)])


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
        data = self.coordinator.data
        # An open cover makes cassette detection unreliable, even if firmware
        # retains a positive width. Never present a guessed or stale width.
        if not data or 'Cover open' in data.get('errors', []):
            return None
        return data['tape_width_mm'] or None

    @property
    def extra_state_attributes(self):
        return self.coordinator.data or {}


class PrinterStatus(TapeWidth):
    _attr_name = None
    _attr_translation_key = 'printer_status'
    _attr_native_unit_of_measurement = None
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ['ready', 'busy', 'error', 'no_tape', 'unsupported_tape', 'powered_off', 'unknown']
    _attr_icon = 'mdi:printer-check'

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f'{entry.unique_id}_status'
        self.entity_id = 'sensor.brother_label_printer_status'

    @property
    def native_value(self):
        return self.coordinator.data['printer_status'] if self.coordinator.data else None


class PrinterErrors(TapeWidth):
    _attr_name = 'Printer errors'
    _attr_native_unit_of_measurement = None
    _attr_icon = 'mdi:printer-alert'

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f'{entry.unique_id}_errors'
        self.entity_id = 'sensor.brother_label_printer_errors'

    @property
    def native_value(self):
        if not self.coordinator.data:
            return None
        return (', '.join(self.coordinator.data['errors']) or 'None')[:255]


class LastSubmission(SensorEntity, RestoreEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = 'last_submission'
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ['idle', 'preparing', 'submitting', 'submitted', 'failed', 'rejected', 'cancelled', 'unknown']
    _attr_icon = 'mdi:printer-clock'

    def __init__(self, coordinator, entry):
        self.coordinator = coordinator
        self._attr_unique_id = f'{entry.unique_id}_last_submission'
        self._attr_device_info = {'identifiers': {(DOMAIN, entry.unique_id)}}
        self.entity_id = 'sensor.brother_label_printer_last_submission'

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        previous = await self.async_get_last_state()
        if previous and previous.state in self._attr_options and self.coordinator.submission['state'] == 'idle':
            allowed = ('detail', 'started_at', 'completed_at', 'last_sent_at', 'copies', 'tape_width_mm')
            self.coordinator.submission = {k: previous.attributes[k] for k in allowed if k in previous.attributes}
            self.coordinator.submission['state'] = previous.state
            if previous.state in ('preparing', 'submitting'):
                self.coordinator.submission.update(state='unknown',
                    detail='Interrupted before outcome was recorded. Check printer before retrying.')
        self.async_on_remove(async_dispatcher_connect(
            self.hass, self.coordinator.submission_signal, self.async_write_ha_state))

    @property
    def native_value(self):
        return self.coordinator.submission['state']

    @property
    def extra_state_attributes(self):
        return {k: v for k, v in self.coordinator.submission.items() if k != 'state'}
