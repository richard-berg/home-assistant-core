"""Data coordinators for the Seymour masking screen integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging

from seymourlib import protocol
from seymourlib.client import SeymourClient
from seymourlib.exceptions import SeymourConnectionError, SeymourError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    METADATA_INTERVAL,
    SIGNAL_DIAGNOSTICS_UPDATED,
    STATUS_INTERVAL_ACTIVE,
    STATUS_INTERVAL_DEFAULT,
    STATUS_INTERVAL_IDLE,
)

_LOGGER = logging.getLogger(__name__)
ISSUE_TRANSPORT_UNREACHABLE = "transport_unreachable"

_HOME_TOLERANCE = 1.0  # percent
_RECONNECT_AFTER_FAILURES = 5


def is_at_home(
    positions: dict[protocol.MotorID, float],
    mask_ids: list[protocol.MotorID],
) -> bool:
    """Return True if every detected mask motor is at the home position.

    A motor is considered "at home" when its position is within
    *_HOME_TOLERANCE* percent of fully retracted (0%).
    If position data is missing for any motor the check fails safe
    and returns False.
    """
    return all(
        (pos := positions.get(motor)) is not None and pos <= _HOME_TOLERANCE
        for motor in mask_ids
    )


@dataclass(slots=True)
class SeymourStatusData:
    """Runtime status information."""

    status: protocol.MaskStatus
    positions: dict[protocol.MotorID, float]


@dataclass(slots=True)
class SeymourMetadata:
    """Slow-changing system information."""

    system_info: protocol.SystemInfo
    ratios: dict[str, protocol.RatioSetting]


@dataclass(slots=True)
class SeymourDiagnosticsResult:
    """Tracks the last diagnostics payload fetched from the controller."""

    option: protocol.DiagnosticOption | None = None
    text: str | None = None
    updated: datetime | None = None


class SeymourDiagnosticsStore:
    """Simple state container to share diagnostics output with entities."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._state = SeymourDiagnosticsResult()

    @property
    def state(self) -> SeymourDiagnosticsResult:
        return self._state

    def update(self, option: protocol.DiagnosticOption, text: str) -> None:
        self._state = SeymourDiagnosticsResult(
            option=option,
            text=text,
            updated=dt_util.utcnow(),
        )
        async_dispatcher_send(self._hass, SIGNAL_DIAGNOSTICS_UPDATED)


class SeymourStatusCoordinator(DataUpdateCoordinator[SeymourStatusData]):
    """Coordinator that retrieves frequently changing mask status and positions."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: SeymourClient,
        config_entry: ConfigEntry,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_status",
            update_interval=STATUS_INTERVAL_DEFAULT,
            config_entry=config_entry,
        )
        self._client = client
        self._failures = 0

    async def _async_update_data(self) -> SeymourStatusData:
        try:
            status = await self._client.get_status()
            positions = await self._client.get_positions()
        except SeymourConnectionError as exc:
            self._failures += 1
            self._maybe_raise_issue()
            await self._maybe_reconnect()
            raise UpdateFailed("Connection to screen failed") from exc
        except SeymourError as exc:
            raise UpdateFailed("Unexpected Seymour protocol error") from exc

        self._failures = 0
        self._maybe_raise_issue(clear=True)
        self._adjust_interval(status.code)
        positions_map = {pos.motor_id: pos.position_pct for pos in positions}
        return SeymourStatusData(status=status, positions=positions_map)

    def _adjust_interval(self, code: protocol.StatusCode) -> None:
        if code in {
            protocol.StatusCode.MOVING_INWARD,
            protocol.StatusCode.MOVING_OUTWARD,
            protocol.StatusCode.MOVING_TO_RATIO,
        }:
            self.update_interval = STATUS_INTERVAL_ACTIVE
        elif code in {protocol.StatusCode.HALTED, protocol.StatusCode.ERROR}:
            self.update_interval = STATUS_INTERVAL_DEFAULT
        else:
            self.update_interval = STATUS_INTERVAL_IDLE

    def _maybe_raise_issue(self, clear: bool = False) -> None:
        if clear or self._failures == 0:
            ir.async_delete_issue(self.hass, DOMAIN, ISSUE_TRANSPORT_UNREACHABLE)
            return
        if self._failures < 3:
            return
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            ISSUE_TRANSPORT_UNREACHABLE,
            is_fixable=True,
            severity=ir.IssueSeverity.ERROR,
            translation_key="transport_unreachable",
        )

    async def _maybe_reconnect(self) -> None:
        """Force a full close/reconnect after sustained failures.

        After *_RECONNECT_AFTER_FAILURES* consecutive connection errors
        the serial buffer is likely desynchronised beyond recovery.  A
        clean TCP teardown and reconnect resets the IP2SL bridge state.
        """
        if self._failures < _RECONNECT_AFTER_FAILURES:
            return
        _LOGGER.warning(
            "Forcing reconnect after %d consecutive failures", self._failures
        )
        try:
            await self._client.close()
            await self._client.connect()
        except Exception:
            _LOGGER.debug(
                "Reconnect attempt failed, will retry next poll", exc_info=True
            )


class SeymourMetadataCoordinator(DataUpdateCoordinator[SeymourMetadata]):
    """Coordinator for infrequent metadata queries."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: SeymourClient,
        config_entry: ConfigEntry,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_metadata",
            update_interval=METADATA_INTERVAL,
            config_entry=config_entry,
        )
        self._client = client

    async def _async_update_data(self) -> SeymourMetadata:
        try:
            system_info = await self._client.get_system_info()
            ratio_settings = await self._client.get_ratio_settings()
        except SeymourConnectionError as exc:
            raise UpdateFailed("Unable to query system information") from exc
        except SeymourError as exc:
            raise UpdateFailed("Unexpected Seymour protocol error") from exc

        ratio_map = {setting.ratio.id: setting for setting in ratio_settings}
        return SeymourMetadata(system_info=system_info, ratios=ratio_map)
