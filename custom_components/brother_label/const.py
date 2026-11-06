"""Defaults for the local Brother P-touch printer."""

DOMAIN = "brother_label"
DEFAULT_HOST = ""
DEFAULT_PORT = 9100
DEFAULT_WIDTH = 24
# Printable pins and right-hand padding, Brother raster reference page 20.
TAPES = {6: (64, 256), 9: (106, 235), 12: (150, 213),
         18: (234, 171), 24: (320, 128), 36: (454, 61)}
