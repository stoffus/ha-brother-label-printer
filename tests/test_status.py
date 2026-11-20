"""Brother status decoding and SNMP reads; no network access."""
import asyncio
import importlib
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from pysnmp.proto import errind
from pysnmp.proto.api import v1

package = types.ModuleType('brother_status_test')
package.__path__ = [str(Path(__file__).resolve().parents[1] / 'custom_components' / 'brother_label_printer')]
sys.modules[package.__name__] = package
status_module = importlib.import_module('brother_status_test.status')
parse_status = status_module.parse_status


class StatusTests(unittest.TestCase):
    def test_known_and_unknown_models(self):
        for code, model in [(0x6f, 'PT-P900W'), (0x70, 'PT-P950NW'),
                            (0x71, 'PT-P900'), (0x78, 'PT-P910BT'), (0xff, 'Unknown')]:
            raw = bytearray(32)
            raw[:4] = b'\x80\x20\x42\x30'
            raw[4], raw[10], raw[11] = code, 24, 1
            status = parse_status(bytes(raw))
            self.assertEqual(status['model'], model)
            self.assertEqual(status['model_code'], f'0x{code:02x}')
            self.assertEqual(status['tape_width_mm'], 24)

    def test_malformed_packets(self):
        for raw in [b'', bytes(31), bytes(32), bytes(33)]:
            with self.assertRaises(ValueError):
                parse_status(raw)

    def test_readiness_and_errors(self):
        raw = bytearray(32)
        raw[:4] = b'\x80\x20\x42\x30'
        raw[4], raw[10], raw[11] = 0x6f, 24, 1
        self.assertTrue(parse_status(raw)['ready'])
        for offset, value, message in [(8, 1, 'No tape'), (8, 4, 'Cutter jam'),
                                       (9, 16, 'Cover open'), (9, 32, 'Overheating'),
                                       (7, 0x21, 'Incompatible media')]:
            packet = raw.copy()
            packet[offset] = value
            result = parse_status(packet)
            self.assertFalse(result['ready'])
            self.assertIn(message, result['errors'])
        for offset, value, state in [(10, 0, 'no_tape'), (11, 3, 'unsupported_tape'),
                                     (19, 1, 'busy'), (19, 2, 'unknown'), (18, 4, 'powered_off')]:
            packet = raw.copy()
            packet[offset] = value
            self.assertEqual(parse_status(packet)['printer_status'], state)
            self.assertFalse(parse_status(packet)['ready'])
        packet = raw.copy()
        packet[8], packet[9] = 4, 16
        self.assertEqual(parse_status(packet)['errors'], ['Cutter jam', 'Cover open'])


class ReadStatusTests(unittest.IsolatedAsyncioTestCase):
    async def test_snmp_responses_and_cleanup(self):
        raw = b'\x80\x20\x42\x30\x6f' + bytes(5) + b'\x18\x01' + bytes(20)
        close = status_module.SnmpDispatcher.close
        for case in ('valid', 'oid', 'status', 'timeout', 'exception', 'malformed'):
            with self.subTest(case=case):
                def send(dispatcher, auth, target, request, cbFun, cbCtx):
                    self.assertEqual((auth.communityName, auth.mpModel), ('public', 0))
                    self.assertEqual(target.transport_address, ('127.0.0.1', 161))
                    self.assertEqual((target.timeout, target.retries), (2, 0))
                    bindings = v1.apiPDU.get_varbinds(request)
                    self.assertEqual(len(bindings), 1)
                    self.assertEqual(str(bindings[0][0]), status_module.STATUS_OID)
                    if case == 'exception':
                        raise RuntimeError('send failed')
                    response = v1.apiPDU.get_response(request)
                    oid = '1.3.6.1.2.1.1.1.0' if case == 'oid' else status_module.STATUS_OID
                    value = b'bad' if case == 'malformed' else raw
                    v1.apiPDU.set_varbinds(response, [(oid, v1.OctetString(value))])
                    if case == 'status':
                        v1.apiPDU.set_error_status(response, 2)
                        v1.apiPDU.set_error_index(response, 1)
                    error = errind.RequestTimedOut() if case == 'timeout' else None
                    asyncio.get_running_loop().call_soon(
                        cbFun, dispatcher, 1, error, response, cbCtx)

                with patch.object(status_module.SnmpDispatcher, 'send_pdu',
                                  autospec=True, side_effect=send) as send_mock, \
                     patch.object(status_module.SnmpDispatcher, 'close',
                                  autospec=True, side_effect=close) as closed:
                    if case == 'valid':
                        result = await status_module.read_status('127.0.0.1')
                        self.assertEqual(result, parse_status(raw))
                        self.assertEqual(result['model'], 'PT-P900W')
                        self.assertTrue(result['ready'])
                    else:
                        expected = RuntimeError if case == 'exception' else ValueError
                        with self.assertRaises(expected):
                            await status_module.read_status('127.0.0.1')
                    send_mock.assert_called_once()
                    closed.assert_called_once_with(send_mock.call_args.args[0])

    async def test_target_creation_timeout_closes_dispatcher(self):
        close = status_module.SnmpDispatcher.close
        with patch.object(status_module.UdpTransportTarget, 'create',
                          side_effect=TimeoutError) as create, \
             patch.object(status_module.SnmpDispatcher, 'send_pdu',
                          autospec=True) as send, \
             patch.object(status_module.SnmpDispatcher, 'close',
                          autospec=True, side_effect=close) as closed:
            with self.assertRaises(TimeoutError):
                await status_module.read_status('127.0.0.1')
            create.assert_awaited_once_with(('127.0.0.1', 161), timeout=2, retries=0)
            send.assert_not_called()
            closed.assert_called_once()
