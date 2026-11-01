"""The Seymour Masking Screen integration."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
import logging
from typing import Any

from seymourlib.client import SeymourClient
from seymourlib.exceptions import SeymourError
from seymourlib.protocol import MotorID
from seymourlib.transport import SerialTransport, TCPTransport

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceInfo

from .const import (
    CONF_CONNECTION_TYPE,
    CONF_MASK_IDS,
    CONF_SERIAL_PORT,
    DEFAULT_TCP_PORT,
    DOMAIN,
    MANUFACTURER,
    ConnectionType,
)
from .coordinator import (
    SeymourDiagnosticsStore,
    SeymourMetadataCoordinator,
    SeymourStatusCoordinator,
)
from .models import SeymourRuntimeData

_LOGGER = logging.getLogger(__name__)

CONNECT_TIMEOUT = 10

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.COVER,
    Platform.SELECT,
    Platform.SENSOR,
]

type SeymourConfigEntry = ConfigEntry[SeymourRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: SeymourConfigEntry) -> bool:
    """Set up Seymour Masking Screen from a config entry.

    The IP2SL accepts only one TCP connection per serial port, so care is
    taken to close the client on every failure path.  If we let an orphaned
    socket leak, subsequent setup retries will hang or fail because the
    IP2SL slot is still occupied.
    """

    client = _create_client(entry.data)
    try:
        async with asyncio.timeout(CONNECT_TIMEOUT):
            await client.connect()
    except (SeymourError, OSError, TimeoutError) as exc:
        await client.close()
        raise ConfigEntryNotReady(
            "Unable to connect to Seymour masking screen"
        ) from exc

    try:
        status_coordinator = SeymourStatusCoordinator(hass, client, entry)
        metadata_coordinator = SeymourMetadataCoordinator(hass, client, entry)

        await metadata_coordinator.async_config_entry_first_refresh()
        await status_coordinator.async_config_entry_first_refresh()
    except Exception:
        await client.close()
        raise

    # Start health monitoring only after both coordinators succeed;
    # otherwise its background task leaks alongside the client.
    await client.start_health_monitoring()

    system_info = metadata_coordinator.data.system_info
    serial_str = system_info.serial_number.to_serial_number()
    device_info = DeviceInfo(
        identifiers={(DOMAIN, serial_str)},
        manufacturer=MANUFACTURER,
        name=system_info.screen_model or "Seymour Masking Screen",
        model=system_info.screen_model,
        hw_version=str(system_info.serial_number),
    )

    # Resolve mask IDs from config data (set during config flow) or fall
    # back to the live system_info for entries created before this field
    # was persisted.
    raw_ids: list[str] = entry.data.get(
        CONF_MASK_IDS, [m.value for m in system_info.mask_ids]
    )
    mask_ids = [MotorID(v) for v in raw_ids]

    entry.runtime_data = SeymourRuntimeData(
        client=client,
        status_coordinator=status_coordinator,
        metadata_coordinator=metadata_coordinator,
        diagnostics=SeymourDiagnosticsStore(hass),
        device_info=device_info,
        serial_number=serial_str,
        mask_ids=mask_ids,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SeymourConfigEntry) -> bool:
    """Unload a config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok and hasattr(entry, "runtime_data"):
        await entry.runtime_data.client.close()
    return unload_ok


def _create_client(config: Mapping[str, Any]) -> SeymourClient:
    connection = ConnectionType(config[CONF_CONNECTION_TYPE])
    transport: SerialTransport | TCPTransport
    if connection is ConnectionType.SERIAL:
        port = config[CONF_SERIAL_PORT]
        transport = SerialTransport(port)
    else:
        host = config[CONF_HOST]
        tcp_port = config.get(CONF_PORT, DEFAULT_TCP_PORT)
        transport = TCPTransport(host, tcp_port)

    return SeymourClient(transport)
