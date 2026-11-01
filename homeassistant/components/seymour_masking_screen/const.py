"""Constants for the Seymour Masking Screen integration."""

from __future__ import annotations

from datetime import timedelta
from enum import StrEnum

from seymourlib.transport import ITACH_SERIAL_PORT

DOMAIN = "seymour_masking_screen"


class ConnectionType(StrEnum):
    """Supported transport types."""

    SERIAL = "serial"
    IP2SL = "ip2sl"


CONF_CONNECTION_TYPE = "connection_type"
CONF_SERIAL_PORT = "serial_port"
CONF_MASK_IDS = "mask_ids"
CONF_MOTOR = "motor"

DEFAULT_TCP_PORT = ITACH_SERIAL_PORT

DATA_RUNTIME = "runtime"
SIGNAL_DIAGNOSTICS_UPDATED = "seymour_masking_screen_diagnostics_updated"

MANUFACTURER = "Seymour-Screen Excellence"

STATUS_INTERVAL_ACTIVE = timedelta(seconds=1)
STATUS_INTERVAL_IDLE = timedelta(seconds=5)
STATUS_INTERVAL_DEFAULT = timedelta(seconds=2)
METADATA_INTERVAL = timedelta(minutes=5)

DIAGNOSTIC_PREVIEW_LENGTH = 160
