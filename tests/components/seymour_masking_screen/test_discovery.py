"""Tests for Seymour masking screen discovery helpers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from seymourlib.discovery import DiscoveryError

from homeassistant.components.seymour_masking_screen.const import (
    CONF_SERIAL_PORT,
    DEFAULT_TCP_PORT,
    ConnectionType,
)
from homeassistant.components.seymour_masking_screen.discovery import (
    async_discover_devices,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

SERIAL_PATCH = (
    "homeassistant.components.seymour_masking_screen.discovery"
    ".seymour_discovery.enumerate_serial_transports"
)
TCP_PATCH = (
    "homeassistant.components.seymour_masking_screen.discovery"
    ".seymour_discovery.enumerate_tcp_transports"
)


def _serial_candidate(
    device: str = "/dev/ttyUSB0",
    description: str = "Seymour Controller",
    hardware_id: str = "USB VID:PID=1234:5678",
    baudrate: int = 9600,
) -> SimpleNamespace:
    """Create a mock serial discovery candidate."""
    return SimpleNamespace(
        device=device,
        description=description,
        hardware_id=hardware_id,
        baudrate=baudrate,
    )


def _tcp_candidate(
    host: str = "192.168.1.100",
    port: int = DEFAULT_TCP_PORT,
    metadata: dict | None = None,
    raw_beacon: str = "raw_data",
) -> SimpleNamespace:
    """Create a mock TCP discovery candidate."""
    return SimpleNamespace(
        host=host,
        port=port,
        metadata=metadata or {},
        raw_beacon=raw_beacon,
    )


async def test_discover_serial_ports(hass: HomeAssistant) -> None:
    """Test discovery finds serial ports."""
    with (
        patch(SERIAL_PATCH, new_callable=AsyncMock) as mock_serial,
        patch(TCP_PATCH, new_callable=AsyncMock, return_value=[]),
    ):
        mock_serial.return_value = [_serial_candidate()]
        results = await async_discover_devices(hass)

    assert len(results) == 1
    result = results[0]
    assert result.connection_type == ConnectionType.SERIAL
    assert result.data == {CONF_SERIAL_PORT: "/dev/ttyUSB0"}
    assert result.key == "serial:///dev/ttyUSB0"
    assert "Serial" in result.title


async def test_discover_serial_dedup(hass: HomeAssistant) -> None:
    """Test discovery deduplicates serial ports."""
    with (
        patch(SERIAL_PATCH, new_callable=AsyncMock) as mock_serial,
        patch(TCP_PATCH, new_callable=AsyncMock, return_value=[]),
    ):
        mock_serial.return_value = [
            _serial_candidate(),
            _serial_candidate(),  # duplicate
        ]
        results = await async_discover_devices(hass)

    assert len(results) == 1


async def test_discover_serial_no_device(hass: HomeAssistant) -> None:
    """Test discovery skips candidates with empty device."""
    with (
        patch(SERIAL_PATCH, new_callable=AsyncMock) as mock_serial,
        patch(TCP_PATCH, new_callable=AsyncMock, return_value=[]),
    ):
        mock_serial.return_value = [_serial_candidate(device="")]
        results = await async_discover_devices(hass)

    assert len(results) == 0


async def test_discover_serial_no_description(hass: HomeAssistant) -> None:
    """Test discovery uses device path when description is empty."""
    with (
        patch(SERIAL_PATCH, new_callable=AsyncMock) as mock_serial,
        patch(TCP_PATCH, new_callable=AsyncMock, return_value=[]),
    ):
        mock_serial.return_value = [
            _serial_candidate(description="", hardware_id=""),
        ]
        results = await async_discover_devices(hass)

    assert len(results) == 1
    assert "/dev/ttyUSB0" in results[0].title
    assert results[0].details["description"] == ""
    assert results[0].details["hardware_id"] == ""


async def test_discover_serial_error(hass: HomeAssistant) -> None:
    """Test serial discovery handles DiscoveryError gracefully."""
    with (
        patch(
            SERIAL_PATCH,
            new_callable=AsyncMock,
            side_effect=DiscoveryError("no ports"),
        ),
        patch(TCP_PATCH, new_callable=AsyncMock, return_value=[]),
    ):
        results = await async_discover_devices(hass)

    assert len(results) == 0


async def test_discover_serial_import_error(hass: HomeAssistant) -> None:
    """Test serial discovery handles ImportError gracefully."""
    with (
        patch(
            SERIAL_PATCH,
            new_callable=AsyncMock,
            side_effect=ImportError("no pyserial"),
        ),
        patch(TCP_PATCH, new_callable=AsyncMock, return_value=[]),
    ):
        results = await async_discover_devices(hass)

    assert len(results) == 0


async def test_discover_serial_value_error(hass: HomeAssistant) -> None:
    """Test serial discovery handles ValueError gracefully."""
    with (
        patch(
            SERIAL_PATCH,
            new_callable=AsyncMock,
            side_effect=ValueError("bad value"),
        ),
        patch(TCP_PATCH, new_callable=AsyncMock, return_value=[]),
    ):
        results = await async_discover_devices(hass)

    assert len(results) == 0


async def test_discover_tcp(hass: HomeAssistant) -> None:
    """Test discovery finds TCP/IP2SL devices."""
    with (
        patch(SERIAL_PATCH, new_callable=AsyncMock, return_value=[]),
        patch(TCP_PATCH, new_callable=AsyncMock) as mock_tcp,
    ):
        mock_tcp.return_value = [
            _tcp_candidate(metadata={"Model": "iTach"}),
        ]
        results = await async_discover_devices(hass)

    assert len(results) == 1
    result = results[0]
    assert result.connection_type == ConnectionType.IP2SL
    assert result.data == {CONF_HOST: "192.168.1.100"}
    assert "iTach" in result.title
    assert result.key == "ip2sl://192.168.1.100"


async def test_discover_tcp_custom_port(hass: HomeAssistant) -> None:
    """Test discovery stores non-default port."""
    with (
        patch(SERIAL_PATCH, new_callable=AsyncMock, return_value=[]),
        patch(TCP_PATCH, new_callable=AsyncMock) as mock_tcp,
    ):
        mock_tcp.return_value = [_tcp_candidate(port=5000)]
        results = await async_discover_devices(hass)

    assert len(results) == 1
    assert results[0].data[CONF_PORT] == 5000


async def test_discover_tcp_default_port_not_stored(
    hass: HomeAssistant,
) -> None:
    """Test discovery does NOT store default port in data."""
    with (
        patch(SERIAL_PATCH, new_callable=AsyncMock, return_value=[]),
        patch(TCP_PATCH, new_callable=AsyncMock) as mock_tcp,
    ):
        mock_tcp.return_value = [_tcp_candidate(port=DEFAULT_TCP_PORT)]
        results = await async_discover_devices(hass)

    assert len(results) == 1
    assert CONF_PORT not in results[0].data


async def test_discover_tcp_dedup(hass: HomeAssistant) -> None:
    """Test discovery deduplicates TCP hosts."""
    with (
        patch(SERIAL_PATCH, new_callable=AsyncMock, return_value=[]),
        patch(TCP_PATCH, new_callable=AsyncMock) as mock_tcp,
    ):
        mock_tcp.return_value = [_tcp_candidate(), _tcp_candidate()]
        results = await async_discover_devices(hass)

    assert len(results) == 1


async def test_discover_tcp_no_model(hass: HomeAssistant) -> None:
    """Test discovery uses host in title when no model is available."""
    with (
        patch(SERIAL_PATCH, new_callable=AsyncMock, return_value=[]),
        patch(TCP_PATCH, new_callable=AsyncMock) as mock_tcp,
    ):
        mock_tcp.return_value = [_tcp_candidate(metadata={})]
        results = await async_discover_devices(hass)

    assert len(results) == 1
    assert "192.168.1.100" in results[0].title


async def test_discover_tcp_product_name(hass: HomeAssistant) -> None:
    """Test discovery uses Product_Name when Model is absent."""
    with (
        patch(SERIAL_PATCH, new_callable=AsyncMock, return_value=[]),
        patch(TCP_PATCH, new_callable=AsyncMock) as mock_tcp,
    ):
        mock_tcp.return_value = [
            _tcp_candidate(metadata={"Product_Name": "IP2SL"}),
        ]
        results = await async_discover_devices(hass)

    assert len(results) == 1
    assert "IP2SL" in results[0].title


async def test_discover_tcp_error(hass: HomeAssistant) -> None:
    """Test TCP discovery handles DiscoveryError gracefully."""
    with (
        patch(SERIAL_PATCH, new_callable=AsyncMock, return_value=[]),
        patch(
            TCP_PATCH,
            new_callable=AsyncMock,
            side_effect=DiscoveryError("timeout"),
        ),
    ):
        results = await async_discover_devices(hass)

    assert len(results) == 0


async def test_discover_tcp_null_port(hass: HomeAssistant) -> None:
    """Test TCP discovery handles None port by using default."""
    with (
        patch(SERIAL_PATCH, new_callable=AsyncMock, return_value=[]),
        patch(TCP_PATCH, new_callable=AsyncMock) as mock_tcp,
    ):
        mock_tcp.return_value = [_tcp_candidate(port=None)]
        results = await async_discover_devices(hass)

    assert len(results) == 1
    assert CONF_PORT not in results[0].data


async def test_discover_tcp_null_metadata(hass: HomeAssistant) -> None:
    """Test TCP discovery handles None metadata."""
    candidate = SimpleNamespace(
        host="192.168.1.200",
        port=DEFAULT_TCP_PORT,
        metadata=None,
        raw_beacon="beacon_data",
    )
    with (
        patch(SERIAL_PATCH, new_callable=AsyncMock, return_value=[]),
        patch(TCP_PATCH, new_callable=AsyncMock, return_value=[candidate]),
    ):
        results = await async_discover_devices(hass)

    assert len(results) == 1
    assert results[0].details["raw_beacon"] == "beacon_data"


async def test_discover_both_serial_and_tcp(hass: HomeAssistant) -> None:
    """Test discovery returns results from both serial and TCP."""
    with (
        patch(SERIAL_PATCH, new_callable=AsyncMock) as mock_serial,
        patch(TCP_PATCH, new_callable=AsyncMock) as mock_tcp,
    ):
        mock_serial.return_value = [_serial_candidate()]
        mock_tcp.return_value = [_tcp_candidate()]
        results = await async_discover_devices(hass)

    assert len(results) == 2
    types = {r.connection_type for r in results}
    assert types == {ConnectionType.SERIAL, ConnectionType.IP2SL}
