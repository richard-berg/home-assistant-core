"""Constants for the Seymour Masking Screen integration."""

from datetime import timedelta
import logging

DOMAIN = "seymour_masking_screen"
LOGGER = logging.getLogger(__package__)

MANUFACTURER = "Seymour-Screen Excellence"

# Movement takes several seconds, so poll faster while a mask is moving to
# keep the reported position close to reality.
UPDATE_INTERVAL_IDLE = timedelta(seconds=5)
UPDATE_INTERVAL_MOVING = timedelta(seconds=1)
