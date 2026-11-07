"""Render TZe labels and send the documented PT-P900W raster protocol.

TCP submission is not a confirmation that a physical label printed. Never
automatically retry a failed submission: some bytes may already have arrived.
"""

import socket
import struct
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .const import TAPES, DEFAULT_PRINT_QUALITY, PRINT_QUALITIES


def render_label(text: str, width: int, font_size: int = 64,
                 print_quality: str = DEFAULT_PRINT_QUALITY) -> Image.Image:
    """Render up to four lines; reject overflow instead of clipping text."""
    if print_quality not in PRINT_QUALITIES:
        raise ValueError("Unsupported print quality")
    dpi = PRINT_QUALITIES[print_quality][0]
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
    target_length = math.ceil(length * dpi / 360)
    if target_length > math.floor(4251 * dpi / 360):
        raise ValueError("Label exceeds 300 mm; shorten text or reduce font_size")
    # Render high resolution from the font outlines at 2x, then reduce only
    # the head axis. Upscaling a 360 dpi monochrome bitmap adds no detail.
    if dpi == 720:
        high_font = ImageFont.truetype(str(Path(__file__).parent / "fonts" / "NotoSans.ttf"), font_size * 2)
        high_box = probe.multiline_textbbox((0, 0), text, font=high_font, spacing=16, align="center")
        glyphs = Image.new("L", (max(1, math.ceil(high_box[2]-high_box[0])), max(1, math.ceil(high_box[3]-high_box[1]))), 255)
        ImageDraw.Draw(glyphs).multiline_text(
            (-high_box[0], -high_box[1]), text, font=high_font, fill=0, spacing=16, align="center")
        # Font hinting can change advances at a different size. Normalize the
        # outline render to the original layout metrics to preserve label size.
        glyphs = glyphs.resize((max(1, math.ceil(text_width * 2)), max(1, math.ceil(text_height * 2))), Image.Resampling.LANCZOS)
        label = Image.new("L", (length * 2, height * 2), 255)
        label.paste(glyphs, (int((length-text_width)//2)*2, int((height-text_height)//2)*2))
    else:
        label = Image.new("L", (length, height), 255)
        ImageDraw.Draw(label).multiline_text(
            ((length - text_width) // 2 - box[0], (height - text_height) // 2 - box[1]),
            text, font=font, fill=0, spacing=8, align="center",
        )
    if label.size != (target_length, height):
        label = label.resize((target_length, height), Image.Resampling.LANCZOS)
    return label.point(lambda value: 255 if value >= 128 else 0, mode="1")


def encode_job(label: Image.Image, width: int, copies: int = 1,
               auto_cut: bool = True, half_cut: bool = False,
               print_quality: str = DEFAULT_PRINT_QUALITY) -> bytes:
    """Encode columns with 360 dpi head resolution and the chosen feed dpi."""
    if print_quality not in PRINT_QUALITIES:
        raise ValueError("Unsupported print quality")
    dpi, quality_bit = PRINT_QUALITIES[print_quality]
    if width not in TAPES or label.height != TAPES[width][0]:
        raise ValueError("Image height does not match tape width")
    if not math.ceil(57 * dpi / 360) <= label.width <= math.floor(4251 * dpi / 360) or not 1 <= copies <= 10:
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
        data += b"\x1biz" + bytes((0x86, 0 if print_quality == "standard" else 0x09, width, 0))
        data += struct.pack("<I", label.width) + bytes((page_type, 0))
        data += b"\x1biM" + bytes((0x40 if auto_cut else 0,))
        data += b"\x1biA\x01"
        data += b"\x1biK" + bytes((0x08 | quality_bit | (0x04 if half_cut else 0),))
        data += b"\x1bid" + struct.pack("<H", round(dpi / 25.4))  # ~1 mm feed margin.
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
