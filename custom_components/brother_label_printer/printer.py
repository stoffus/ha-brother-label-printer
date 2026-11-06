"""Render TZe labels and send the documented PT-P900W raster protocol.

TCP submission is not a confirmation that a physical label printed. Never
automatically retry a failed submission: some bytes may already have arrived.
"""

import socket
import struct
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .const import TAPES


def render_label(text: str, width: int, font_size: int = 64) -> Image.Image:
    """Render up to four lines; reject overflow instead of clipping text."""
    if width not in TAPES:
        raise ValueError("Unsupported TZe tape width")
    if not text.strip() or len(text) > 500:
        raise ValueError("Provide 1–500 characters of label text")
    if not 16 <= font_size <= 160:
        raise ValueError("Font size must be between 16 and 160 pixels")
    if any((ord(c) < 32 and c != "\n") or ord(c) > 255 or 127 <= ord(c) < 160 for c in text):
        raise ValueError("Use Latin-1 text (including å, ä, ö) and line breaks")
    if len(text.splitlines()) > 4:
        raise ValueError("Use at most four lines")
    font = ImageFont.truetype(str(Path(__file__).parent / "fonts" / "NotoSans.ttf"), font_size)
    probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    box = probe.multiline_textbbox((0, 0), text, font=font, spacing=8, align="center")
    text_width, text_height = box[2] - box[0], box[3] - box[1]
    height = TAPES[width][0]
    if text_height > height - 16:
        raise ValueError("Text is too tall for the tape; reduce font_size or line count")
    # At most 300 mm of image per label; margins are added by the printer.
    length = max(57, math.ceil(text_width + 28))
    if length > 4251:
        raise ValueError("Label exceeds 300 mm; shorten text or reduce font_size")
    label = Image.new("L", (length, height), 255)
    ImageDraw.Draw(label).multiline_text(
        ((length - text_width) // 2 - box[0], (height - text_height) // 2 - box[1]),
        text, font=font, fill=0, spacing=8, align="center",
    )
    return label.point(lambda value: 255 if value >= 128 else 0, mode="1")


def encode_job(label: Image.Image, width: int, copies: int = 1,
               auto_cut: bool = True, half_cut: bool = False) -> bytes:
    """Encode monochrome columns, one bit per pin, at 360 dpi."""
    if width not in TAPES or label.height != TAPES[width][0]:
        raise ValueError("Image height does not match tape width")
    if not 57 <= label.width <= 4251 or not 1 <= copies <= 10:
        raise ValueError("Invalid label length or copies (1–10)")
    if half_cut and not auto_cut:
        raise ValueError("half_cut requires auto_cut")
    # Black pixels must become set bits. Transposition makes each image column
    # a contiguous 560-bit raster row, starting at the right-hand padding.
    inverted = label.convert("L").point(lambda p: 255 if p < 128 else 0, mode="1")
    pins = Image.new("1", (label.width, 560), 0)
    pins.paste(inverted, (0, TAPES[width][1]))
    raster = pins.transpose(Image.Transpose.TRANSPOSE).tobytes()
    rows = b"".join(b"G\x46\x00" + raster[i:i + 70]
                    for i in range(0, len(raster), 70))
    data = bytearray(b"\x00" * 200 + b"\x1b@")
    for page in range(copies):
        page_type = 2 if page == copies - 1 else (0 if page == 0 else 1)
        data += b"\x1bia\x01"
        # Validate tape type and width; enable printer recovery.
        data += b"\x1biz" + bytes((0x86, 0, width, 0))
        data += struct.pack("<I", label.width) + bytes((page_type, 0))
        data += b"\x1biM" + bytes((0x40 if auto_cut else 0,))
        data += b"\x1biA\x01"
        data += b"\x1biK" + bytes((0x08 | (0x04 if half_cut else 0),))
        data += b"\x1bid\x0e\x00"  # 1 mm feed margin.
        data += b"M\x00" + rows
        data += b"\x1a" if page == copies - 1 else b"\x0c"
    return bytes(data)


def check_connection(host: str, port: int) -> None:
    """Check the raw TCP endpoint without sending printer commands."""
    with socket.create_connection((host, port), timeout=5):
        pass


def submit_job(host: str, port: int, payload: bytes) -> None:
    """Submit once, with a bounded timeout and no automatic retries."""
    with socket.create_connection((host, port), timeout=5) as connection:
        connection.settimeout(30)
        connection.sendall(payload)
