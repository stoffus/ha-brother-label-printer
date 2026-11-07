"""Defaults for the local Brother P-touch printer."""

DOMAIN = "brother_label_printer"
DEFAULT_HOST = ""
DEFAULT_PORT = 9100
DEFAULT_WIDTH = 24
DEFAULT_POLL_INTERVAL = 30
# Printable pins and right-hand padding, Brother raster reference page 20.
TAPES = {6: (64, 256), 9: (106, 235), 12: (150, 213),
         18: (234, 171), 24: (320, 128), 36: (454, 61)}

DEFAULT_PRINT_QUALITY = "standard"
# Feed-axis dpi and ESC i K mode bit. The print head remains 360 dpi.
PRINT_QUALITIES = {"standard": (360, 0), "high_resolution": (720, 0x40), "draft": (180, 0x01)}
