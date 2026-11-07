"""Polling and submission state shared by the printer entities."""
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util


class PrinterCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, logger, **kwargs):
        super().__init__(hass, logger, **kwargs)
        self.submission_signal = f"brother_label_printer_submission_{kwargs['config_entry'].entry_id}"
        self.submission = {'state': 'idle', 'detail': 'No submission recorded'}

    @callback
    def record_submission(self, state, detail, **attributes):
        now = dt_util.utcnow().isoformat()
        if state == 'preparing':
            previous_sent = self.submission.get('last_sent_at')
            self.submission = {'started_at': now, 'last_sent_at': previous_sent}
        self.submission.update(state=state, detail=detail, **attributes)
        if state in ('submitted', 'failed', 'rejected', 'cancelled', 'unknown'):
            self.submission['completed_at'] = now
        if state == 'submitted':
            self.submission['last_sent_at'] = now
        async_dispatcher_send(self.hass, self.submission_signal)
