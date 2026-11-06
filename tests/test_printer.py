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
