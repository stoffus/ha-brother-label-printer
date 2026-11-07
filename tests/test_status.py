"""Model decoding from Brother status packets; no network access."""
import importlib
import sys
import types
import unittest
from pathlib import Path

package = types.ModuleType('brother_status_test')
package.__path__ = [str(Path(__file__).resolve().parents[1] / 'custom_components' / 'brother_label_printer')]
sys.modules[package.__name__] = package
parse_status = importlib.import_module('brother_status_test.status').parse_status


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
