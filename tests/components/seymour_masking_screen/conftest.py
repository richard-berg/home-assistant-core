"""Common fixtures for the Seymour Masking Screen tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from seymourlib.client import SeymourClient
from seymourlib.protocol import decode_positions, decode_status, decode_system_info

from homeassistant.components.seymour_masking_screen.const import DOMAIN
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant

from . import (
    MOCK_DEVICE,
    POSITIONS_FRAME,
    SERIAL_NUMBER,
    STATUS_FRAME,
    SYSTEM_INFO_FRAME,
)


@pytest.fixture(autouse=True)
def mock_usb_component(hass: HomeAssistant) -> None:
    """Mark the USB dependency as set up."""
    hass.config.components.add("usb")


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent the config entry from being set up."""
    with patch(
        "homeassistant.components.seymour_masking_screen.async_setup_entry",
        return_value=None,
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def system_info_frame() -> bytes:
    """Return the system info response of the controller."""
    return SYSTEM_INFO_FRAME


@pytest.fixture
def mock_seymour_client(system_info_frame: bytes) -> Generator[AsyncMock]:
    """Return a mocked Seymour client used by both setup and the config flow."""
    client = AsyncMock(spec=SeymourClient)
    client.get_system_info.return_value = decode_system_info(system_info_frame)
    client.get_status.return_value = decode_status(STATUS_FRAME)
    client.get_positions.return_value = decode_positions(POSITIONS_FRAME)
    with (
        patch(
            "homeassistant.components.seymour_masking_screen.SeymourClient",
            return_value=client,
        ),
        patch(
            "homeassistant.components.seymour_masking_screen.config_flow.SeymourClient",
            return_value=client,
        ),
    ):
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Seymour PRH-123",
        data={CONF_DEVICE: MOCK_DEVICE},
        unique_id=SERIAL_NUMBER,
        entry_id="01KQ0SEYMOURTEST0000000000",
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_seymour_client: AsyncMock,
) -> MockConfigEntry:
    """Set up the integration."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
