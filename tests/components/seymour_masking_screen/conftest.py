"""Common fixtures for Seymour masking screen tests."""

from __future__ import annotations

from collections.abc import Generator
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.seymour_masking_screen.const import (
    CONF_CONNECTION_TYPE,
    CONF_MASK_IDS,
    CONF_SERIAL_PORT,
    DOMAIN,
    ConnectionType,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

SERIAL_NUMBER = "AB-0124-12345"
SCREEN_MODEL = "Seymour Reference"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent real async_setup_entry during config flow tests."""
    with patch(
        "homeassistant.components.seymour_masking_screen.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


def _make_serial_number(serial_str: str = SERIAL_NUMBER) -> SimpleNamespace:
    """Create a mock Serial object matching seymourlib's interface."""
    serial = SimpleNamespace()
    serial.to_serial_number = MagicMock(return_value=serial_str)
    return serial


def _make_system_info(
    serial_str: str = SERIAL_NUMBER,
    model: str = SCREEN_MODEL,
) -> SimpleNamespace:
    """Create a mock SystemInfo matching seymourlib's interface."""
    from seymourlib.protocol import MotorID

    return SimpleNamespace(
        screen_model=model,
        serial_number=_make_serial_number(serial_str),
        width_inches=120.0,
        height_inches=67.5,
        mask_ids=[MotorID.TOP, MotorID.BOTTOM, MotorID.LEFT, MotorID.RIGHT],
    )


def _make_status(code_name: str = "STOPPED_AT_RATIO") -> SimpleNamespace:
    """Create a mock MaskStatus."""
    from seymourlib.protocol import StatusCode

    code = StatusCode[code_name]
    return SimpleNamespace(
        code=code,
        ratio=SimpleNamespace(id="178"),
    )


def _make_positions() -> list[SimpleNamespace]:
    """Create a list of mock MaskPosition objects."""
    from seymourlib.protocol import MotorID

    return [
        SimpleNamespace(motor_id=MotorID.TOP, position_pct=25.0),
        SimpleNamespace(motor_id=MotorID.BOTTOM, position_pct=25.0),
        SimpleNamespace(motor_id=MotorID.LEFT, position_pct=10.0),
        SimpleNamespace(motor_id=MotorID.RIGHT, position_pct=10.0),
    ]


def _make_ratio_settings() -> list[SimpleNamespace]:
    """Create mock ratio settings."""
    return [
        SimpleNamespace(
            ratio=SimpleNamespace(id="178"),
            label="16:9",
            motor_positions_pct=[0.0, 0.0, 0.0, 0.0],
            motor_adjustments_pct=[0.0, 0.0, 0.0, 0.0],
            width_inches=120.0,
            height_inches=67.5,
        ),
        SimpleNamespace(
            ratio=SimpleNamespace(id="235"),
            label="2.35:1",
            motor_positions_pct=[30.0, 30.0, 30.0, 30.0],
            motor_adjustments_pct=[0.0, 0.0, 0.0, 0.0],
            width_inches=120.0,
            height_inches=51.1,
        ),
        SimpleNamespace(
            ratio=SimpleNamespace(id="240"),
            label="2.40:1",
            motor_positions_pct=[35.0, 35.0, 35.0, 35.0],
            motor_adjustments_pct=[0.0, 0.0, 0.0, 0.0],
            width_inches=120.0,
            height_inches=50.0,
        ),
    ]


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"{SCREEN_MODEL} ({SERIAL_NUMBER})",
        data={
            CONF_CONNECTION_TYPE: ConnectionType.SERIAL.value,
            CONF_SERIAL_PORT: "/dev/ttyUSB0",
            CONF_MASK_IDS: ["T", "B", "L", "R"],
        },
        unique_id=SERIAL_NUMBER,
    )


@pytest.fixture
def mock_seymour_client() -> Generator[AsyncMock]:
    """Return a mocked SeymourClient."""
    client = AsyncMock()
    client.connect = AsyncMock()
    client.close = AsyncMock()
    client.start_health_monitoring = AsyncMock()
    client.get_system_info = AsyncMock(return_value=_make_system_info())
    client.get_status = AsyncMock(return_value=_make_status())
    client.get_positions = AsyncMock(return_value=_make_positions())
    client.get_ratio_settings = AsyncMock(return_value=_make_ratio_settings())
    client.get_diagnostics = AsyncMock(return_value="diag payload text")
    client.move_in = AsyncMock()
    client.move_out = AsyncMock()
    client.move_to_ratio = AsyncMock()
    client.halt = AsyncMock()
    client.home = AsyncMock()
    client.calibrate = AsyncMock()
    client.update_ratio = AsyncMock()
    client.reset_factory_default = AsyncMock()
    client.connection_stats = {
        "last_successful_operation": 1000000.0,
        "time_since_last_success": 0.5,
    }
    with patch(
        "homeassistant.components.seymour_masking_screen._create_client",
        return_value=client,
    ):
        yield client


@pytest.fixture
def platforms() -> list[Platform]:
    """Return the platforms to set up."""
    return [Platform.BUTTON, Platform.COVER, Platform.SELECT, Platform.SENSOR]


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_seymour_client: AsyncMock,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the Seymour masking screen integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.seymour_masking_screen.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
