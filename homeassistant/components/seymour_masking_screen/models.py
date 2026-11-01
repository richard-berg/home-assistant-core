"""Runtime data models for the Seymour masking screen integration."""

from __future__ import annotations

from dataclasses import dataclass

from seymourlib.client import SeymourClient
from seymourlib.protocol import MotorID

from homeassistant.helpers.device_registry import DeviceInfo

from .coordinator import (
    SeymourDiagnosticsStore,
    SeymourMetadataCoordinator,
    SeymourStatusCoordinator,
)


@dataclass(slots=True)
class SeymourRuntimeData:
    """Container for config entry runtime data."""

    client: SeymourClient
    status_coordinator: SeymourStatusCoordinator
    metadata_coordinator: SeymourMetadataCoordinator
    diagnostics: SeymourDiagnosticsStore
    device_info: DeviceInfo
    serial_number: str
    mask_ids: list[MotorID]
