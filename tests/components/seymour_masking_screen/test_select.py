"""Tests for the Seymour masking screen select entities."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from seymourlib.protocol import MotorID

from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from tests.common import MockConfigEntry

BASE = "select.seymour_reference"


@pytest.fixture
def platforms() -> list[Platform]:
    """Override platforms to only load select."""
    return [Platform.SELECT]


@pytest.mark.usefixtures("init_integration")
async def test_ratio_move_select(
    hass: HomeAssistant,
    mock_seymour_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test selecting a ratio triggers move_to_ratio."""
    entity_id = f"{BASE}_move_to_ratio"
    state = hass.states.get(entity_id)
    assert state is not None

    # Options should include ratios from conftest
    options = state.attributes.get("options", [])
    assert len(options) >= 2

    # Motors must be at home for ratio move.
    mock_seymour_client.get_positions.return_value = [
        SimpleNamespace(motor_id=MotorID.TOP, position_pct=0.0),
        SimpleNamespace(motor_id=MotorID.BOTTOM, position_pct=0.0),
        SimpleNamespace(motor_id=MotorID.LEFT, position_pct=0.0),
        SimpleNamespace(motor_id=MotorID.RIGHT, position_pct=0.0),
    ]
    coordinator = mock_config_entry.runtime_data.status_coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Select the first option (should match "16:9 (178)")
    first_option = options[0]
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, "option": first_option},
        blocking=True,
    )

    mock_seymour_client.move_to_ratio.assert_awaited_once()


@pytest.mark.usefixtures("init_integration")
async def test_ratio_update_select(
    hass: HomeAssistant,
    mock_seymour_client: AsyncMock,
) -> None:
    """Test selecting a ratio triggers update_ratio."""
    entity_id = f"{BASE}_update_ratio"
    state = hass.states.get(entity_id)
    assert state is not None

    options = state.attributes.get("options", [])
    first_option = options[0]
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, "option": first_option},
        blocking=True,
    )

    mock_seymour_client.update_ratio.assert_awaited_once()


@pytest.mark.usefixtures("init_integration")
async def test_ratio_reset_select(
    hass: HomeAssistant,
    mock_seymour_client: AsyncMock,
) -> None:
    """Test selecting a ratio for reset triggers reset_factory_default."""
    entity_id = f"{BASE}_reset_ratio"
    state = hass.states.get(entity_id)
    assert state is not None

    options = state.attributes.get("options", [])
    first_option = options[0]
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, "option": first_option},
        blocking=True,
    )

    mock_seymour_client.reset_factory_default.assert_awaited_once()


@pytest.mark.usefixtures("init_integration")
async def test_ratio_reset_all(
    hass: HomeAssistant,
    mock_seymour_client: AsyncMock,
) -> None:
    """Test selecting 'All ratios (factory reset)' resets all ratios."""
    entity_id = f"{BASE}_reset_ratio"
    state = hass.states.get(entity_id)
    options = state.attributes.get("options", [])

    # The reset-all option should be present
    reset_all = [o for o in options if "factory reset" in o.lower()]
    assert len(reset_all) == 1

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, "option": reset_all[0]},
        blocking=True,
    )

    mock_seymour_client.reset_factory_default.assert_awaited_once_with(None)


@pytest.mark.usefixtures("init_integration")
async def test_move_in_select(
    hass: HomeAssistant,
    mock_seymour_client: AsyncMock,
) -> None:
    """Test the move-in select fires move_in."""
    entity_id = f"{BASE}_move_in"
    state = hass.states.get(entity_id)
    assert state is not None

    options = state.attributes.get("options", [])
    assert len(options) > 0

    # Pick the first option
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, "option": options[0]},
        blocking=True,
    )

    mock_seymour_client.move_in.assert_awaited_once()


@pytest.mark.usefixtures("init_integration")
async def test_move_out_select(
    hass: HomeAssistant,
    mock_seymour_client: AsyncMock,
) -> None:
    """Test the move-out select fires move_out."""
    entity_id = f"{BASE}_move_out"
    state = hass.states.get(entity_id)
    assert state is not None

    options = state.attributes.get("options", [])
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, "option": options[0]},
        blocking=True,
    )

    mock_seymour_client.move_out.assert_awaited_once()


@pytest.mark.usefixtures("init_integration")
async def test_ratio_move_unknown_option(
    hass: HomeAssistant,
) -> None:
    """Test selecting an invalid option in ratio_move raises an error."""
    entity_id = f"{BASE}_move_to_ratio"
    state = hass.states.get(entity_id)
    assert state is not None

    # Call entity method directly to bypass HA service option validation
    entity = hass.data["entity_components"]["select"].get_entity(entity_id)
    with pytest.raises(ServiceValidationError):
        await entity.async_select_option("nonexistent_ratio")


@pytest.mark.usefixtures("init_integration")
async def test_ratio_update_unknown_option(
    hass: HomeAssistant,
) -> None:
    """Test selecting an invalid option in ratio_update raises an error."""
    entity_id = f"{BASE}_update_ratio"
    state = hass.states.get(entity_id)
    assert state is not None

    entity = hass.data["entity_components"]["select"].get_entity(entity_id)
    with pytest.raises(ServiceValidationError):
        await entity.async_select_option("nonexistent_ratio")


@pytest.mark.usefixtures("init_integration")
async def test_ratio_reset_unknown_option(
    hass: HomeAssistant,
) -> None:
    """Test selecting an invalid option in ratio_reset raises an error."""
    entity_id = f"{BASE}_reset_ratio"
    state = hass.states.get(entity_id)
    assert state is not None

    entity = hass.data["entity_components"]["select"].get_entity(entity_id)
    with pytest.raises(ServiceValidationError):
        await entity.async_select_option("nonexistent_ratio")


@pytest.mark.usefixtures("init_integration")
async def test_move_in_unknown_option(
    hass: HomeAssistant,
) -> None:
    """Test selecting an invalid option in move_in raises an error."""
    entity_id = f"{BASE}_move_in"
    state = hass.states.get(entity_id)
    assert state is not None

    entity = hass.data["entity_components"]["select"].get_entity(entity_id)
    with pytest.raises(ServiceValidationError):
        await entity.async_select_option("nonexistent_move")


@pytest.mark.usefixtures("init_integration")
async def test_ratio_move_rejected_when_not_at_home(
    hass: HomeAssistant,
    mock_seymour_client: AsyncMock,
) -> None:
    """Test ratio move raises when masks are not at home."""
    entity_id = f"{BASE}_move_to_ratio"
    state = hass.states.get(entity_id)
    assert state is not None

    options = state.attributes.get("options", [])
    first_option = options[0]

    # Default conftest positions are 25%/10% — not at home.
    entity = hass.data["entity_components"]["select"].get_entity(entity_id)
    with pytest.raises(ServiceValidationError, match="home position"):
        await entity.async_select_option(first_option)
    mock_seymour_client.move_to_ratio.assert_not_awaited()


@pytest.mark.usefixtures("init_integration")
async def test_ratio_move_allowed_when_at_home(
    hass: HomeAssistant,
    mock_seymour_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test ratio move succeeds when all masks are at home."""
    # Set all motors to 0%.
    mock_seymour_client.get_positions.return_value = [
        SimpleNamespace(motor_id=MotorID.TOP, position_pct=0.0),
        SimpleNamespace(motor_id=MotorID.BOTTOM, position_pct=0.0),
        SimpleNamespace(motor_id=MotorID.LEFT, position_pct=0.0),
        SimpleNamespace(motor_id=MotorID.RIGHT, position_pct=0.0),
    ]
    coordinator = mock_config_entry.runtime_data.status_coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    entity_id = f"{BASE}_move_to_ratio"
    state = hass.states.get(entity_id)
    options = state.attributes.get("options", [])
    first_option = options[0]

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, "option": first_option},
        blocking=True,
    )
    mock_seymour_client.move_to_ratio.assert_awaited_once()
