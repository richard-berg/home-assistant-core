"""Tests for the Seymour masking screen diagnostics."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry


@pytest.fixture
def platforms() -> list[Platform]:
    """Load no platforms — diagnostics does not need them."""
    return []


@pytest.mark.usefixtures("init_integration")
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: pytest.fixture,
    mock_config_entry: MockConfigEntry,
    mock_seymour_client: AsyncMock,
) -> None:
    """Test that diagnostics returns expected data with redacted serial port."""
    diag = await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)

    assert "config" in diag
    assert diag["config"]["serial_port"] == "**REDACTED**"
    assert "status" in diag
    assert diag["status"]["code"] == "STOPPED_AT_RATIO"
    assert "system" in diag
    assert diag["system"]["model"] == "Seymour Reference"
    assert "diagnostics" in diag
