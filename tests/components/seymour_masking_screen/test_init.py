"""Tests for the Seymour masking screen integration setup."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from seymourlib.exceptions import SeymourConnectionError, SeymourError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_seymour_client: AsyncMock,
) -> None:
    """Test successful setup of a config entry."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.seymour_masking_screen.PLATFORMS", []):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_seymour_client.connect.assert_awaited_once()
    mock_seymour_client.start_health_monitoring.assert_awaited_once()


async def test_setup_entry_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_seymour_client: AsyncMock,
) -> None:
    """Test setup raises ConfigEntryNotReady on connection failure."""
    mock_seymour_client.connect.side_effect = SeymourConnectionError("offline")
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.seymour_masking_screen.PLATFORMS", []):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_seymour_client.close.assert_awaited_once()


async def test_setup_entry_protocol_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_seymour_client: AsyncMock,
) -> None:
    """Test setup raises ConfigEntryNotReady on protocol error during connect."""
    mock_seymour_client.connect.side_effect = SeymourError("bad handshake")
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.seymour_masking_screen.PLATFORMS", []):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_seymour_client.close.assert_awaited_once()


async def test_setup_entry_connect_timeout(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_seymour_client: AsyncMock,
) -> None:
    """Test setup raises ConfigEntryNotReady when connect times out."""

    async def _hang() -> None:
        await asyncio.sleep(3600)

    mock_seymour_client.connect.side_effect = _hang
    mock_config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.seymour_masking_screen.PLATFORMS", []),
        patch("homeassistant.components.seymour_masking_screen.CONNECT_TIMEOUT", 0.1),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_seymour_client.close.assert_awaited_once()


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_seymour_client: AsyncMock,
) -> None:
    """Test unloading a config entry closes the client."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.seymour_masking_screen.PLATFORMS", []):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_seymour_client.close.assert_awaited_once()


async def test_setup_entry_os_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_seymour_client: AsyncMock,
) -> None:
    """Test setup raises ConfigEntryNotReady on OS-level socket error."""
    mock_seymour_client.connect.side_effect = OSError("Connection refused")
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.seymour_masking_screen.PLATFORMS", []):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_seymour_client.close.assert_awaited_once()
