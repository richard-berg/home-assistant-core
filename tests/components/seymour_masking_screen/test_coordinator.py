"""Tests for the Seymour masking screen coordinators."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from seymourlib.exceptions import SeymourConnectionError, SeymourTransportError
from seymourlib.protocol import MotorID, StatusCode

from homeassistant.components.seymour_masking_screen.const import (
    STATUS_INTERVAL_ACTIVE,
    STATUS_INTERVAL_IDLE,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[Platform]:
    """Load no platforms, just coordinators."""
    return []


@pytest.mark.usefixtures("init_integration")
async def test_status_coordinator_adjusts_interval_on_movement(
    hass: HomeAssistant,
    mock_seymour_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the coordinator reduces polling interval during movement."""
    coordinator = mock_config_entry.runtime_data.status_coordinator

    mock_seymour_client.get_status.return_value = SimpleNamespace(
        code=StatusCode.MOVING_INWARD,
        ratio=None,
    )
    await coordinator.async_refresh()
    assert coordinator.update_interval == STATUS_INTERVAL_ACTIVE

    mock_seymour_client.get_status.return_value = SimpleNamespace(
        code=StatusCode.STOPPED_AT_RATIO,
        ratio=SimpleNamespace(id="178"),
    )
    await coordinator.async_refresh()
    assert coordinator.update_interval == STATUS_INTERVAL_IDLE


@pytest.mark.usefixtures("init_integration")
async def test_status_coordinator_creates_repair_after_failures(
    hass: HomeAssistant,
    mock_seymour_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that 3 consecutive failures create a repair issue."""
    coordinator = mock_config_entry.runtime_data.status_coordinator

    mock_seymour_client.get_status.side_effect = SeymourConnectionError("timeout")
    mock_seymour_client.get_positions.side_effect = SeymourConnectionError("timeout")

    for _ in range(3):
        await coordinator.async_refresh()

    issues = ir.async_get(hass)
    issue = issues.async_get_issue("seymour_masking_screen", "transport_unreachable")
    assert issue is not None
    assert issue.severity == ir.IssueSeverity.ERROR


@pytest.mark.usefixtures("init_integration")
async def test_status_coordinator_clears_repair_on_recovery(
    hass: HomeAssistant,
    mock_seymour_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that recovery after failures clears the repair issue."""
    coordinator = mock_config_entry.runtime_data.status_coordinator

    mock_seymour_client.get_status.side_effect = SeymourConnectionError("timeout")
    mock_seymour_client.get_positions.side_effect = SeymourConnectionError("timeout")

    for _ in range(3):
        await coordinator.async_refresh()

    # Restore success
    mock_seymour_client.get_status.side_effect = None
    mock_seymour_client.get_status.return_value = SimpleNamespace(
        code=StatusCode.STOPPED_AT_RATIO,
        ratio=SimpleNamespace(id="178"),
    )
    mock_seymour_client.get_positions.side_effect = None
    mock_seymour_client.get_positions.return_value = [
        SimpleNamespace(motor_id=MotorID.TOP, position_pct=0.0),
    ]

    await coordinator.async_refresh()

    issues = ir.async_get(hass)
    issue = issues.async_get_issue("seymour_masking_screen", "transport_unreachable")
    assert issue is None


@pytest.mark.usefixtures("init_integration")
async def test_status_coordinator_handles_transport_error(
    hass: HomeAssistant,
    mock_seymour_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that SeymourTransportError is caught and raises UpdateFailed."""
    coordinator = mock_config_entry.runtime_data.status_coordinator

    mock_seymour_client.get_status.side_effect = SeymourTransportError("broken pipe")

    await coordinator.async_refresh()

    # Coordinator should have handled the error (last_update_success = False)
    assert coordinator.last_update_success is False


@pytest.mark.usefixtures("init_integration")
async def test_metadata_coordinator_handles_transport_error(
    hass: HomeAssistant,
    mock_seymour_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that metadata coordinator catches SeymourTransportError."""
    coordinator = mock_config_entry.runtime_data.metadata_coordinator

    mock_seymour_client.get_system_info.side_effect = SeymourTransportError("closed")

    await coordinator.async_refresh()

    assert coordinator.last_update_success is False


@pytest.mark.usefixtures("init_integration")
async def test_status_coordinator_reconnects_after_sustained_failures(
    hass: HomeAssistant,
    mock_seymour_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the coordinator forces close/connect after N failures."""
    coordinator = mock_config_entry.runtime_data.status_coordinator

    mock_seymour_client.get_status.side_effect = SeymourConnectionError("timeout")
    mock_seymour_client.get_positions.side_effect = SeymourConnectionError("timeout")

    # Should NOT reconnect before the threshold (5).
    for _ in range(4):
        await coordinator.async_refresh()

    mock_seymour_client.close.assert_not_awaited()

    # 5th failure should trigger reconnect.
    await coordinator.async_refresh()

    mock_seymour_client.close.assert_awaited_once()
    mock_seymour_client.connect.assert_awaited()
