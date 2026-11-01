"""Tests for the Seymour Masking Screen integration setup."""

from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from seymourlib.exceptions import SeymourConnectionError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.seymour_masking_screen.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import SERIAL_NUMBER


async def test_setup_and_unload(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_seymour_client: AsyncMock,
) -> None:
    """Test setting up and unloading the integration."""
    assert init_integration.state is ConfigEntryState.LOADED
    mock_seymour_client.close.assert_not_awaited()

    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED
    mock_seymour_client.close.assert_awaited_once()


async def test_device_info(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the device created for the controller."""
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, SERIAL_NUMBER), init_integration.entry_id
    )
    assert device == snapshot


@pytest.mark.parametrize("method", ["connect", "get_system_info", "get_status"])
async def test_setup_retry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_seymour_client: AsyncMock,
    method: str,
) -> None:
    """Test setup is retried, and the connection released, when it fails."""
    getattr(mock_seymour_client, method).side_effect = SeymourConnectionError
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_seymour_client.close.assert_awaited_once()


async def test_setup_retry_hides_api_key(
    hass: HomeAssistant,
    mock_seymour_client: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the setup retry message does not show an ESPHome API key."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: "esphome://proxy.local:6053/?port_name=RS232&key=SECRET"},
        unique_id=SERIAL_NUMBER,
    )
    entry.add_to_hass(hass)
    mock_seymour_client.connect.side_effect = SeymourConnectionError

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert "esphome://proxy.local:6053/" in caplog.text
    assert "SECRET" not in caplog.text
