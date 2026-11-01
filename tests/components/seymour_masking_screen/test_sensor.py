"""Tests for the Seymour masking screen sensor entities."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from seymourlib.protocol import StatusCode

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

BASE = "sensor.seymour_reference"


@pytest.fixture
def platforms() -> list[Platform]:
    """Override platforms to only load sensor."""
    return [Platform.SENSOR]


@pytest.mark.usefixtures("init_integration")
async def test_status_sensor(hass: HomeAssistant) -> None:
    """Test the status sensor reports the current status code."""
    state = hass.states.get(f"{BASE}_status")
    assert state is not None
    assert state.state == "stopped_at_ratio"


@pytest.mark.usefixtures("init_integration")
async def test_ratio_sensor(hass: HomeAssistant) -> None:
    """Test the ratio sensor reports the current ratio label."""
    state = hass.states.get(f"{BASE}_ratio")
    assert state is not None
    # Ratio 178 has label "16:9"
    assert "16:9" in state.state


@pytest.mark.usefixtures("init_integration")
async def test_ratio_sensor_no_ratio(
    hass: HomeAssistant,
    mock_seymour_client: AsyncMock,
    mock_config_entry,
) -> None:
    """Test the ratio sensor returns None when no ratio is active."""
    mock_seymour_client.get_status.return_value = SimpleNamespace(
        code=StatusCode.STOPPED_AT_RATIO,
        ratio=None,
    )
    coordinator = mock_config_entry.runtime_data.status_coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get(f"{BASE}_ratio")
    assert state is not None
    assert state.state == "unknown"


@pytest.mark.usefixtures("init_integration")
async def test_ratio_sensor_unlabeled(
    hass: HomeAssistant,
    mock_seymour_client: AsyncMock,
    mock_config_entry,
) -> None:
    """Test the ratio sensor returns just the ID when the ratio has no label."""
    mock_seymour_client.get_status.return_value = SimpleNamespace(
        code=StatusCode.STOPPED_AT_RATIO,
        ratio=SimpleNamespace(id="999"),
    )
    coordinator = mock_config_entry.runtime_data.status_coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get(f"{BASE}_ratio")
    assert state is not None
    # Ratio "999" is not in the metadata ratios, so raw id returned
    assert state.state == "999"


@pytest.mark.usefixtures("init_integration")
async def test_position_sensor(hass: HomeAssistant) -> None:
    """Test per-motor position sensors report correct values."""
    state = hass.states.get(f"{BASE}_top_mask_position")
    assert state is not None
    assert float(state.state) == 25.0


@pytest.mark.usefixtures("init_integration")
async def test_dimension_sensors(hass: HomeAssistant) -> None:
    """Test dimension sensors report width and height."""
    width = hass.states.get(f"{BASE}_screen_width")
    height = hass.states.get(f"{BASE}_screen_height")
    assert width is not None
    assert height is not None
    assert float(width.state) == 120.0
    assert float(height.state) == 67.5


@pytest.mark.usefixtures("init_integration")
async def test_connection_age_disabled_by_default(
    hass: HomeAssistant,
) -> None:
    """Test the connection age sensor is disabled by default."""
    from homeassistant.helpers import entity_registry as er

    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get(f"{BASE}_connection_age")
    assert entry is not None
    assert entry.disabled_by is not None


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_connection_age_value(
    hass: HomeAssistant,
) -> None:
    """Test the connection age sensor value when enabled."""
    state = hass.states.get(f"{BASE}_connection_age")
    assert state is not None
    assert float(state.state) == 0.5


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_connection_age_negative(
    hass: HomeAssistant,
    mock_seymour_client: AsyncMock,
    mock_config_entry,
) -> None:
    """Test the connection age sensor returns unknown when value is negative."""
    mock_seymour_client.connection_stats = {
        "last_successful_operation": 0,
        "time_since_last_success": -1,
    }
    coordinator = mock_config_entry.runtime_data.status_coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get(f"{BASE}_connection_age")
    assert state is not None
    assert state.state == "unknown"


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_diagnostics_sensor_default(
    hass: HomeAssistant,
) -> None:
    """Test the diagnostics sensor is empty initially."""
    state = hass.states.get(f"{BASE}_diagnostics")
    assert state is not None
    # No diagnostics have been fetched yet
    assert state.state == "unknown"


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_diagnostics_sensor_with_data(
    hass: HomeAssistant,
    mock_config_entry,
) -> None:
    """Test the diagnostics sensor shows data after a diagnostics update."""
    from seymourlib.protocol import DiagnosticOption

    runtime_data = mock_config_entry.runtime_data
    runtime_data.diagnostics.update(DiagnosticOption.LIST_FS, "file1.txt\nfile2.txt")
    await hass.async_block_till_done()

    state = hass.states.get(f"{BASE}_diagnostics")
    assert state is not None
    assert state.state == "file1.txt\nfile2.txt"
    assert state.attributes["option"] == "LIST_FS"
    assert state.attributes["full_text"] == "file1.txt\nfile2.txt"


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_diagnostics_sensor_long_text(
    hass: HomeAssistant,
    mock_config_entry,
) -> None:
    """Test the diagnostics sensor truncates long text."""
    from seymourlib.protocol import DiagnosticOption

    from homeassistant.components.seymour_masking_screen.const import (
        DIAGNOSTIC_PREVIEW_LENGTH,
    )

    long_text = "A" * (DIAGNOSTIC_PREVIEW_LENGTH + 50)
    runtime_data = mock_config_entry.runtime_data
    runtime_data.diagnostics.update(DiagnosticOption.LIST_FS, long_text)
    await hass.async_block_till_done()

    state = hass.states.get(f"{BASE}_diagnostics")
    assert state is not None
    assert len(state.state) == DIAGNOSTIC_PREVIEW_LENGTH + 1  # +1 for ellipsis
    assert state.state.endswith("…")
    assert state.attributes["full_text"] == long_text
