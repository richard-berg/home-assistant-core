"""Tests for the Seymour masking screen button entities."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from seymourlib.protocol import MotorID

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant

BASE = "button.seymour_reference"


@pytest.fixture
def platforms() -> list[Platform]:
    """Override platforms to only load button."""
    return [Platform.BUTTON]


@pytest.mark.usefixtures("init_integration")
async def test_home_button(
    hass: HomeAssistant,
    mock_seymour_client: AsyncMock,
) -> None:
    """Test pressing the home-all button."""
    entity_id = f"{BASE}_home_all_masks"
    state = hass.states.get(entity_id)
    assert state is not None

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_seymour_client.home.assert_awaited_once_with(MotorID.ALL)


@pytest.mark.usefixtures("init_integration")
async def test_halt_button(
    hass: HomeAssistant,
    mock_seymour_client: AsyncMock,
) -> None:
    """Test pressing the halt-all button."""
    entity_id = f"{BASE}_halt_all_masks"

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_seymour_client.halt.assert_awaited_once_with(MotorID.ALL)


@pytest.mark.usefixtures("init_integration")
async def test_calibrate_button(
    hass: HomeAssistant,
    mock_seymour_client: AsyncMock,
) -> None:
    """Test pressing the calibrate-all button."""
    entity_id = f"{BASE}_calibrate_all_masks"

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_seymour_client.calibrate.assert_awaited_once_with(MotorID.ALL)


@pytest.mark.usefixtures("init_integration")
async def test_per_motor_buttons_exist(
    hass: HomeAssistant,
) -> None:
    """Test that per-motor buttons are created for each mask motor."""
    for motor in ("top", "bottom", "left", "right"):
        for action in ("home", "halt", "calibrate"):
            entity_id = f"{BASE}_{action}_{motor}_mask"
            state = hass.states.get(entity_id)
            assert state is not None, f"Missing entity {entity_id}"


@pytest.mark.usefixtures("init_integration")
async def test_diagnostics_button_disabled_by_default(
    hass: HomeAssistant,
) -> None:
    """Test that diagnostics buttons are disabled by default."""
    from homeassistant.helpers import entity_registry as er

    ent_reg = er.async_get(hass)
    for entry in er.async_entries_for_config_entry(
        ent_reg,
        hass.config_entries.async_entries("seymour_masking_screen")[0].entry_id,
    ):
        if "diagnostics_" in entry.entity_id:
            assert entry.disabled_by is not None


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_diagnostics_button_press(
    hass: HomeAssistant,
    mock_seymour_client: AsyncMock,
) -> None:
    """Test pressing a diagnostics button fetches payload and updates store."""
    entity_id = f"{BASE}_diagnostics_file_system"
    state = hass.states.get(entity_id)
    assert state is not None

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_seymour_client.get_diagnostics.assert_awaited_once()
