"""Protocol tests independent of Home Assistant and of the physical printer."""

import importlib
import socket
import struct
import sys
import threading
import types
import unittest
from pathlib import Path

from PIL import Image, ImageFont

SOURCE = Path(__file__).resolve().parents[1] / "custom_components" / "brother_label_printer"
package = types.ModuleType("brother_label_printer_test")
package.__path__ = [str(SOURCE)]
sys.modules[package.__name__] = package
printer = importlib.import_module("brother_label_printer_test.printer")


class PrinterTests(unittest.TestCase):
    def test_raster_reconstructs_asymmetric_image(self):
        label = Image.new("1", (57, 320), 1)
        for xy in ((0, 0), (0, 319), (56, 31), (12, 123)):
            label.putpixel(xy, 0)
        data = printer.encode_job(label, 24)
        start = data.index(b"M\x00", 202) + 2
        for x in range(57):
            row = data[start + x * 73:start + (x + 1) * 73]
            self.assertEqual(row[:3], b"G\x46\x00")
            bits = int.from_bytes(row[3:], "big")
            for pin in range(560):
                expected = 128 <= pin < 448 and label.getpixel((x, pin - 128)) == 0
                self.assertEqual(bool(bits & (1 << (559 - pin))), expected)
        self.assertEqual(data[start + 57 * 73:], b"\x1a")

    def test_copy_pages_width_and_cuts(self):
        label = Image.new("1", (57, 320), 1)
        data = printer.encode_job(label, 24, 3, True, True)
        self.assertEqual(data[:202], b"\0" * 200 + b"\x1b@")
        pages = data[202:].split(b"\x1bia\x01")[1:]
        self.assertEqual(len(pages), 3)
        for page, page_type, terminator in zip(pages, (0, 1, 2), (12, 12, 26)):
            self.assertEqual(page[:7], b"\x1biz\x86\x00\x18\x00")
            self.assertEqual(struct.unpack("<I", page[7:11])[0], 57)
            self.assertEqual(page[11:13], bytes((page_type, 0)))
            self.assertIn(b"\x1biM\x40\x1biA\x01\x1biK\x0c", page)
            self.assertEqual(page[-1], terminator)

    def test_invalid_input_and_overflow(self):
        for text, width, size in (("", 24, 64), ("x", 7, 64), ("x", 24, 200),
                                  ("hello\nworld", 6, 64), ("x" * 500, 24, 64),
                                  ("😀", 24, 64), ("a\nb\nc\nd\ne", 24, 16)):
            with self.subTest(text=text[:20], width=width, size=size):
                with self.assertRaises(ValueError):
                    printer.render_label(text, width, size)
        with self.assertRaises(ValueError):
            printer.encode_job(Image.new("1", (57, 320)), 24, 11)
        with self.assertRaises(ValueError):
            printer.encode_job(Image.new("1", (57, 320)), 24, 1, False, True)

    def test_swedish_glyphs_and_multiline(self):
        font = ImageFont.truetype(str(SOURCE / "fonts" / "NotoSans.ttf"), 64)
        missing = bytes(font.getmask("\ufffd"))
        for letter in "ÅÄÖåäö":
            self.assertNotEqual(bytes(font.getmask(letter)), missing)
        label = printer.render_label("Köttfärs\n2026-11-06", 24)
        self.assertEqual(label.height, 320)
        self.assertEqual(label.mode, "1")
        self.assertEqual(label.getextrema(), (0, 255))

    def test_quality_dimensions_and_protocol(self):
        for width, text, size in [(12, "Öppnad: 2026-11-07 | Använd senast: 2026-11-10", 48),
                                  (24, "Öppnad: 2026-11-07\nAnvänd senast: 2026-11-10", 64)]:
            normal = printer.render_label(text, width, size)
            for quality, dpi, mode in [('standard', 360, 0), ('high_resolution', 720, 0x40), ('draft', 180, 1)]:
                with self.subTest(width=width, quality=quality):
                    label = printer.render_label(text, width, size, quality)
                    self.assertEqual(label.height, normal.height)
                    self.assertAlmostEqual(label.width / dpi, normal.width / 360, delta=1 / dpi)
                    # Ink bounds retain physical dimensions within font hinting/rounding tolerance.
                    normal_bounds = normal.convert('L').point(lambda p: 255-p).getbbox()
                    bounds = label.convert('L').point(lambda p: 255-p).getbbox()
                    self.assertAlmostEqual((bounds[2]-bounds[0]) / dpi,
                                           (normal_bounds[2]-normal_bounds[0]) / 360, delta=3 / 180)
                    self.assertAlmostEqual(bounds[3]-bounds[1], normal_bounds[3]-normal_bounds[1], delta=3)
                    if quality == 'high_resolution':
                        self.assertNotEqual(label.tobytes(), normal.resize(label.size, Image.Resampling.NEAREST).tobytes())
                    data = printer.encode_job(label, width, 2, True, True, quality)
                    pages = data[202:].split(b"\x1bia\x01")[1:]
                    for page in pages:
                        self.assertEqual(page[4], 0 if quality == 'standard' else 9)
                        self.assertEqual(struct.unpack('<I', page[7:11])[0], label.width)
                        self.assertIn(b"\x1biK" + bytes([0x0c | mode]), page)
                        self.assertIn(b"\x1bid" + struct.pack('<H', round(dpi / 25.4)), page)
                        start = page.index(b'M\x00') + 2
                        self.assertEqual(len(page[start:-1]), label.width * 73)
                        # Reconstruct every raster column to verify orientation and head padding.
                        for x in range(label.width):
                            row = page[start+x*73:start+(x+1)*73]
                            self.assertEqual(row[:3], b'G\x46\x00')
                            bits = int.from_bytes(row[3:], 'big')
                            pins, padding = printer.TAPES[width]
                            expected = 0
                            for y in range(pins):
                                if label.getpixel((x, y)) == 0:
                                    expected |= 1 << (559-padding-y)
                            self.assertEqual(bits, expected)

    def test_quality_length_limits_and_validation(self):
        for quality, minimum, maximum in [('standard', 57, 4251), ('high_resolution', 114, 8502), ('draft', 29, 2125)]:
            for length in (minimum, maximum):
                printer.encode_job(Image.new('1', (length, 320), 1), 24, print_quality=quality)
            for length in (minimum-1, maximum+1):
                with self.assertRaises(ValueError):
                    printer.encode_job(Image.new('1', (length, 320), 1), 24, print_quality=quality)
            with self.assertRaises(ValueError):
                printer.render_label('x'*500, 24, print_quality=quality)
        with self.assertRaises(ValueError):
            printer.render_label('Test', 24, print_quality='720')
        with self.assertRaises(ValueError):
            printer.encode_job(Image.new('1', (57, 320)), 24, print_quality='720')

    def test_tcp_submission_delivers_exact_job(self):
        received = bytearray()
        with socket.socket() as server:
            server.bind(("127.0.0.1", 0))
            server.listen()
            server.settimeout(5)

            def receive():
                connection, _ = server.accept()
                with connection:
                    connection.settimeout(5)
                    while chunk := connection.recv(4096):
                        received.extend(chunk)

            worker = threading.Thread(target=receive)
            worker.start()
            data = printer.encode_job(printer.render_label("Test", 24), 24)
            printer.submit_job("127.0.0.1", server.getsockname()[1], data)
            worker.join(timeout=6)
            self.assertFalse(worker.is_alive())
            self.assertEqual(received, data)


if __name__ == "__main__":
    unittest.main()
