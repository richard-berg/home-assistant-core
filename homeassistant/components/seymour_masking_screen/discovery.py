"""Discovery helpers for Seymour masking screens."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from typing import Any

from seymourlib import discovery as seymour_discovery
from seymourlib.discovery import DiscoveryError

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import CONF_SERIAL_PORT, DEFAULT_TCP_PORT, ConnectionType

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class SeymourDiscovery:
    """Container with discovery metadata."""

    key: str
    title: str
    connection_type: ConnectionType
    data: dict[str, Any]
    details: dict[str, str]


async def async_discover_devices(hass: HomeAssistant) -> list[SeymourDiscovery]:
    """Discover Seymour masking screens via serial ports and IP beacons."""

    serial_task = hass.async_create_task(_discover_serial_ports())
    tcp_task = hass.async_create_task(_discover_ip2sl_devices())
    serial_candidates, tcp_candidates = await asyncio.gather(serial_task, tcp_task)
    return [*serial_candidates, *tcp_candidates]


async def _discover_serial_ports() -> list[SeymourDiscovery]:
    try:
        candidates = await seymour_discovery.enumerate_serial_transports()
    except (DiscoveryError, ImportError, ValueError) as exc:
        _LOGGER.debug("Serial discovery unavailable: %s", exc)
        return []
    except Exception as exc:  # pragma: no cover - unexpected failures
        _LOGGER.debug("Unexpected serial discovery failure: %s", exc)
        return []

    results: list[SeymourDiscovery] = []
    seen: set[str] = set()
    for candidate in candidates:
        device = candidate.device
        if not device or device in seen:
            continue
        seen.add(device)

        title = candidate.description or device
        details = {
            "device": device,
            "description": candidate.description or "",
            "hardware_id": candidate.hardware_id or "",
            "baudrate": str(candidate.baudrate),
        }

        results.append(
            SeymourDiscovery(
                key=f"serial://{device}",
                title=f"Serial · {title}",
                connection_type=ConnectionType.SERIAL,
                data={CONF_SERIAL_PORT: device},
                details=details,
            )
        )

    return results


async def _discover_ip2sl_devices() -> list[SeymourDiscovery]:
    try:
        candidates = await seymour_discovery.enumerate_tcp_transports()
    except DiscoveryError as exc:
        _LOGGER.debug("IP discovery unavailable: %s", exc)
        return []
    except Exception as exc:  # pragma: no cover - unexpected failures
        _LOGGER.debug("Unexpected IP discovery failure: %s", exc)
        return []

    results: list[SeymourDiscovery] = []
    seen: set[str] = set()
    for candidate in candidates:
        host = candidate.host
        if host in seen:
            continue
        seen.add(host)

        metadata = {key: value for key, value in (candidate.metadata or {}).items()}
        metadata.setdefault("raw_beacon", candidate.raw_beacon)

        model = metadata.get("Model") or metadata.get("Product_Name")
        title = f"IP2SL · {model} @ {host}" if model else f"IP2SL · {host}"

        tcp_port = candidate.port or DEFAULT_TCP_PORT
        data: dict[str, Any] = {CONF_HOST: host}
        if tcp_port != DEFAULT_TCP_PORT:
            data[CONF_PORT] = tcp_port

        results.append(
            SeymourDiscovery(
                key=f"ip2sl://{host}",
                title=title,
                connection_type=ConnectionType.IP2SL,
                data=data,
                details=metadata,
            )
        )

    return results
