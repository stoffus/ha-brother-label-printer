"""Run inside Core's container; isolated HA instance, no physical printing."""

import asyncio
import os
import threading
import tempfile
from pathlib import Path
from unittest.mock import patch

from homeassistant.core import HomeAssistant, Context
from homeassistant import loader, config_entries
from homeassistant.helpers import device_registry, entity_registry
from homeassistant.setup import async_setup_component
from homeassistant.exceptions import ServiceValidationError, HomeAssistantError


async def main():
    with tempfile.TemporaryDirectory(prefix="brother-label-check-") as directory:
        Path(directory, "custom_components").symlink_to(os.environ.get("BROTHER_COMPONENTS", "/config/custom_components"))
        hass = HomeAssistant(directory)
        hass.config.skip_pip = True
        loader.async_setup(hass)
        hass.config_entries = config_entries.ConfigEntries(hass, {})
        await hass.config_entries.async_initialize()
        device_registry.async_setup(hass)
        await device_registry.async_load(hass)
        await entity_registry.async_load(hass)
        try:
            assert await async_setup_component(hass, "brother_label_printer", {})
            result = await hass.config_entries.flow.async_init(
                "brother_label_printer", context={"source": "user"}
            )
            assert result["type"] == "form", result
            import custom_components.brother_label_printer.config_flow as flow
            values = {"host": "printer.example.test", "port": 9100, "tape_width": 24}
            with patch.object(flow, "check_connection", side_effect=TimeoutError):
                result = await hass.config_entries.flow.async_configure(result["flow_id"], values)
                assert result["errors"] == {"base": "cannot_connect"}
            with patch.object(flow, "check_connection"):
                result = await hass.config_entries.flow.async_configure(result["flow_id"], values)
            assert result["type"] == "create_entry", result
            await hass.async_block_till_done()
            import custom_components.brother_label_printer as integration
            with patch.object(integration, "submit_job") as send:
                result = await hass.services.async_call("brother_label_printer", "print_label", {
                    "text": "Köttfärs\n2026-11-06", "copies": 2,
                }, blocking=True, return_response=True)
                assert result == {"status": "submitted", "copies": 2, "tape_width_mm": 24}, result
                assert send.call_count == 1
                for width in (12, 24):
                    result = await hass.services.async_call("brother_label_printer", "print_label", {
                        "text": "2026-11-06 | 2026-11-09", "tape_width": width,
                    }, blocking=True, return_response=True)
                    assert result["tape_width_mm"] == width
                    payload = send.call_args.args[2]
                    info = payload.index(b"\x1biz")
                    assert payload[info + 5] == width, "Raster media width must match the action"
                assert hass.data["brother_label_printer"][0].data["tape_width"] == 24
                assert send.call_count == 3
                assert send.call_args.args[:2] == ("printer.example.test", 9100)
                assert send.call_args.args[2].endswith(b"\x1a")
                try:
                    await hass.services.async_call("brother_label_printer", "print_label", {
                        "text": "😀",
                    }, blocking=True)
                except ServiceValidationError:
                    pass
                else:
                    raise AssertionError("Invalid text was accepted")
                assert send.call_count == 3
            status = {"tape_width_mm": 24, "media_type": 1, "error": False, "error_bytes": "000000"}
            with patch.object(integration, "read_status", return_value=status), patch.object(integration, "submit_job") as send:
                detected = await hass.services.async_call("brother_label_printer", "get_status", {}, blocking=True, return_response=True)
                assert detected == status
                await hass.services.async_call("brother_label_printer", "print_label", {"text": "Dates", "tape_width": 24, "verify_tape": True}, blocking=True)
                assert send.call_count == 1
                for bad in ({**status, "tape_width_mm": 12}, {**status, "tape_width_mm": 0}, {**status, "error": True}, {**status, "media_type": 3}):
                    with patch.object(integration, "read_status", return_value=bad):
                        try:
                            await hass.services.async_call("brother_label_printer", "print_label", {"text": "Dates", "tape_width": 24, "verify_tape": True}, blocking=True)
                        except ServiceValidationError:
                            pass
                        else:
                            raise AssertionError("Unsafe cassette accepted")
                with patch.object(integration, "read_status", side_effect=TimeoutError):
                    try:
                        await hass.services.async_call("brother_label_printer", "print_label", {"text": "Dates", "verify_tape": True}, blocking=True)
                    except HomeAssistantError:
                        pass
                    else:
                        raise AssertionError("Status timeout accepted")
                assert send.call_count == 1, "Failed tape checks must never submit"
            from custom_components.brother_label_printer.status import parse_status
            raw = bytes.fromhex("80 20 42 30 6F 30 04 00 00 00 18 01 00 00 00 00 00 00 00 00 00 00 00 00 01 08 00 00 00 00 00 00")
            assert parse_status(raw) == status
            for width in (0, 12, 24, 36):
                assert parse_status(raw[:10] + bytes([width]) + raw[11:])["tape_width_mm"] == width
            try:
                parse_status(raw[:20])
            except ValueError:
                pass
            else:
                raise AssertionError("Truncated status accepted")
            with patch.object(integration, "submit_job", side_effect=TimeoutError) as send:
                try:
                    await hass.services.async_call("brother_label_printer", "print_label", {
                        "text": "Test",
                    }, blocking=True)
                except HomeAssistantError:
                    pass
                else:
                    raise AssertionError("Transport error was hidden")
                assert send.call_count == 1, "Must not retry ambiguous submissions"
            async with hass.data["brother_label_printer"][1]:
                try:
                    await hass.services.async_call("brother_label_printer", "print_label", {
                        "text": "Test",
                    }, blocking=True)
                except ServiceValidationError:
                    pass
                else:
                    raise AssertionError("Concurrent submission was accepted")
            # A cancelled caller must not release the print lock while its worker sends.
            started, finish = threading.Event(), threading.Event()
            def blocked_send(*args):
                started.set()
                assert finish.wait(10)
            with patch.object(integration, 'submit_job', side_effect=blocked_send):
                task = asyncio.create_task(hass.services.async_call('brother_label_printer', 'print_label', {'text': 'Cancellation test'}, blocking=True))
                await asyncio.to_thread(started.wait, 5)
                assert started.is_set()
                task.cancel()
                await asyncio.sleep(0.05)
                assert hass.data['brother_label_printer'][1].locked(), 'Cancelled worker released print lock'
                finish.set()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                await hass.async_block_till_done()
                assert not hass.data['brother_label_printer'][1].locked()
            if Path(os.environ.get('BROTHER_FRIDGE_SCRIPT', '/config/scripts/labels.yaml')).exists():
                import yaml
                from homeassistant.helpers.script import Script
                from homeassistant.helpers import config_validation as cv
                sequence = yaml.safe_load(Path(os.environ.get('BROTHER_FRIDGE_SCRIPT', '/config/scripts/labels.yaml')).read_text())['print_fridge_label']['sequence']
                # Skip the UI double-tap delay; exercise the deployed formatting and Auto branches.
                sequence = cv.SCRIPT_SCHEMA(sequence[:-1])
                hass.states.async_set('input_number.fridge_label_days', '3')
                for selection, width in [('Auto', 12), ('Auto', 24), ('12 mm', 12), ('24 mm', 24)]:
                    hass.states.async_set('input_select.fridge_label_width', selection)
                    with patch.object(integration, 'read_status', return_value={**status, 'tape_width_mm': width}) as read, patch.object(integration, 'submit_job') as send, patch.object(integration, 'render_label', wraps=integration.render_label) as render:
                        script = Script(hass, sequence, 'Fridge test', 'test')
                        await script.async_run(context=Context())
                        assert send.call_count == 1
                        text, used_width, size = render.call_args.args
                        assert used_width == width
                        assert (' | ' in text) == (width == 12)
                        assert ('\n' in text) == (width == 24)
                        assert size == (48 if width == 12 else 64)
                        assert read.call_count == (2 if selection == 'Auto' else 0)
                print('PASS: deployed fridge script Auto/manual 12/24 mm layouts; fresh detection and verification.')
            entry = hass.config_entries.async_entries("brother_label_printer")[0]
            assert await hass.config_entries.async_unload(entry.entry_id)
            assert "brother_label_printer" not in hass.data
            print("PASS: config flow, connection-error handling, action rendering, response, "
                  "invalid text, no retry, concurrency guard, unload. No labels printed.")
        finally:
            await hass.async_stop()


asyncio.run(asyncio.wait_for(main(), 45))
