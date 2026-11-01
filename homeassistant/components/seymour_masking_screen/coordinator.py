"""Data update coordinator for the Seymour Masking Screen integration."""

from dataclasses import dataclass
from typing import override

from seymourlib.client import SeymourClient
from seymourlib.exceptions import SeymourError
from seymourlib.protocol import MaskStatus, MotorID, StatusCode, SystemInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, UPDATE_INTERVAL_IDLE, UPDATE_INTERVAL_MOVING

type SeymourConfigEntry = ConfigEntry[SeymourCoordinator]

MOVING_STATUS_CODES = frozenset(
    {
        StatusCode.MOVING_INWARD,
        StatusCode.MOVING_OUTWARD,
        StatusCode.MOVING_TO_RATIO,
        StatusCode.HOMING,
        StatusCode.CALIBRATING,
    }
)


@dataclass(slots=True)
class SeymourData:
    """Current status of the masking screen."""

    status: MaskStatus
    positions: dict[MotorID, float]


class SeymourCoordinator(DataUpdateCoordinator[SeymourData]):
    """Poll the status and mask positions of a Seymour controller."""

    config_entry: SeymourConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: SeymourConfigEntry,
        client: SeymourClient,
        system_info: SystemInfo,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL_IDLE,
        )
        self.client = client
        self.system_info = system_info
        self.serial_number = system_info.serial_number.to_serial_number()

    @override
    async def _async_update_data(self) -> SeymourData:
        """Fetch the status and positions from the controller."""
        try:
            status = await self.client.get_status()
            positions = await self.client.get_positions()
        except SeymourError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err

        self.update_interval = (
            UPDATE_INTERVAL_MOVING
            if status.code in MOVING_STATUS_CODES
            else UPDATE_INTERVAL_IDLE
        )
        return SeymourData(
            status=status,
            positions={pos.motor_id: pos.position_pct for pos in positions},
        )
