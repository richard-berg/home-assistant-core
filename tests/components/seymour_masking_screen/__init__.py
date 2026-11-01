"""Tests for the Seymour Masking Screen integration."""

MOCK_DEVICE = "/dev/ttyUSB0"
MOCK_IP2SL_HOST = "192.168.1.70"
MOCK_IP2SL_URL = "socket://192.168.1.70:4999"
SERIAL_NUMBER = "SS-0325-12345"

# Raw controller responses, captured from a real controller (serial number
# replaced) and decoded with seymourlib's own parsers.
SYSTEM_INFO_FRAME = b"[01PRH-123             0123.00069.1SS-0325-12345TBLR]"
STATUS_FRAME = b"[01H]"
POSITIONS_FRAME = b"[014T25.0B25.0L10.0R10.0]"
