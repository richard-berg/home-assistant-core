"""Tests for the Seymour masking screen cover entities."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from seymourlib.protocol import MotorID, MovementCode, StatusCode

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    SERVICE_STOP_COVER,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

# Entity IDs for the default 4-mask setup (T, B, L, R).
ENTITY_TOP = "cover.seymour_reference_top_mask"
ENTITY_BOTTOM = "cover.seymour_reference_bottom_mask"
ENTITY_LEFT = "cover.seymour_reference_left_mask"
ENTITY_RIGHT = "cover.seymour_reference_right_mask"
ENTITY_VERTICAL = "cover.seymour_reference_vertical_masks"
ENTITY_HORIZONTAL = "cover.seymour_reference_horizontal_masks"
ENTITY_ALL = "cover.seymour_reference_all_masks"


@pytest.fixture
def platforms() -> list[Platform]:
    """Override platforms to only load cover."""
    return [Platform.COVER]


@pytest.mark.usefixtures("init_integration")
async def test_individual_mask_entities_created(
    hass: HomeAssistant,
) -> None:
    """Test that individual cover entities are created for each mask motor."""
    for entity_id in (ENTITY_TOP, ENTITY_BOTTOM, ENTITY_LEFT, ENTITY_RIGHT):
        state = hass.states.get(entity_id)
        assert state is not None, f"{entity_id} not found"


@pytest.mark.usefixtures("init_integration")
async def test_group_alias_entities_created(
    hass: HomeAssistant,
) -> None:
    """Test that group alias covers (vertical, horizontal, all) are created."""
    for entity_id in (ENTITY_VERTICAL, ENTITY_HORIZONTAL, ENTITY_ALL):
        state = hass.states.get(entity_id)
        assert state is not None, f"{entity_id} not found"


@pytest.mark.usefixtures("init_integration")
async def test_individual_mask_position(
    hass: HomeAssistant,
) -> None:
    """Test individual mask cover reports its own motor position."""
    # From conftest: TOP=25%, BOTTOM=25%, LEFT=10%, RIGHT=10%
    # HA position = 100 - seymourlib_pct
    state = hass.states.get(ENTITY_TOP)
    assert state is not None
    assert state.state == STATE_OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 75  # 100 - 25

    state = hass.states.get(ENTITY_LEFT)
    assert state is not None
    assert state.attributes[ATTR_CURRENT_POSITION] == 90  # 100 - 10


@pytest.mark.usefixtures("init_integration")
async def test_group_vertical_position(
    hass: HomeAssistant,
) -> None:
    """Test vertical group averages top and bottom positions."""
    # TOP=25%, BOTTOM=25% -> avg=25%, HA=75
    state = hass.states.get(ENTITY_VERTICAL)
    assert state is not None
    assert state.attributes[ATTR_CURRENT_POSITION] == 75


@pytest.mark.usefixtures("init_integration")
async def test_group_horizontal_position(
    hass: HomeAssistant,
) -> None:
    """Test horizontal group averages left and right positions."""
    # LEFT=10%, RIGHT=10% -> avg=10%, HA=90
    state = hass.states.get(ENTITY_HORIZONTAL)
    assert state is not None
    assert state.attributes[ATTR_CURRENT_POSITION] == 90


@pytest.mark.usefixtures("init_integration")
async def test_all_group_position(
    hass: HomeAssistant,
) -> None:
    """Test ALL group averages all motor positions."""
    # (25+25+10+10)/4 = 17.5 -> HA = 82 (rounded)
    state = hass.states.get(ENTITY_ALL)
    assert state is not None
    assert state.state == STATE_OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 82


@pytest.mark.usefixtures("init_integration")
async def test_individual_open_cover(
    hass: HomeAssistant,
    mock_seymour_client: AsyncMock,
) -> None:
    """Test opening an individual mask sends the correct motor ID."""
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: ENTITY_TOP},
        blocking=True,
    )
    mock_seymour_client.move_out.assert_awaited_once_with(
        MotorID.TOP, MovementCode.UNTIL_LIMIT
    )


@pytest.mark.usefixtures("init_integration")
async def test_individual_close_cover(
    hass: HomeAssistant,
    mock_seymour_client: AsyncMock,
) -> None:
    """Test closing an individual mask sends the correct motor ID."""
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: ENTITY_BOTTOM},
        blocking=True,
    )
    mock_seymour_client.move_in.assert_awaited_once_with(
        MotorID.BOTTOM, MovementCode.UNTIL_LIMIT
    )


@pytest.mark.usefixtures("init_integration")
async def test_individual_stop_cover(
    hass: HomeAssistant,
    mock_seymour_client: AsyncMock,
) -> None:
    """Test stopping an individual mask sends the correct motor ID."""
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: ENTITY_LEFT},
        blocking=True,
    )
    mock_seymour_client.halt.assert_awaited_once_with(MotorID.LEFT)


@pytest.mark.usefixtures("init_integration")
async def test_group_open_cover(
    hass: HomeAssistant,
    mock_seymour_client: AsyncMock,
) -> None:
    """Test opening a group alias sends the alias motor ID."""
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: ENTITY_VERTICAL},
        blocking=True,
    )
    mock_seymour_client.move_out.assert_awaited_once_with(
        MotorID.VERTICAL, MovementCode.UNTIL_LIMIT
    )


@pytest.mark.usefixtures("init_integration")
async def test_all_open_cover(
    hass: HomeAssistant,
    mock_seymour_client: AsyncMock,
) -> None:
    """Test opening the ALL group sends MotorID.ALL."""
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: ENTITY_ALL},
        blocking=True,
    )
    mock_seymour_client.move_out.assert_awaited_once_with(
        MotorID.ALL, MovementCode.UNTIL_LIMIT
    )


@pytest.mark.usefixtures("init_integration")
async def test_all_close_cover(
    hass: HomeAssistant,
    mock_seymour_client: AsyncMock,
) -> None:
    """Test closing the ALL group sends MotorID.ALL."""
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: ENTITY_ALL},
        blocking=True,
    )
    mock_seymour_client.move_in.assert_awaited_once_with(
        MotorID.ALL, MovementCode.UNTIL_LIMIT
    )


@pytest.mark.usefixtures("init_integration")
async def test_all_stop_cover(
    hass: HomeAssistant,
    mock_seymour_client: AsyncMock,
) -> None:
    """Test stopping the ALL group sends MotorID.ALL."""
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: ENTITY_ALL},
        blocking=True,
    )
    mock_seymour_client.halt.assert_awaited_once_with(MotorID.ALL)


@pytest.mark.usefixtures("init_integration")
async def test_all_set_position(
    hass: HomeAssistant,
    mock_seymour_client: AsyncMock,
    mock_config_entry,
) -> None:
    """Test setting position on ALL matches to nearest ratio."""
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

    # Target HA position 70 -> seymourlib = 30 -> closest ratio 2.35:1 at avg 30
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: ENTITY_ALL, ATTR_POSITION: 70},
        blocking=True,
    )
    mock_seymour_client.move_to_ratio.assert_awaited_once()
    call_args = mock_seymour_client.move_to_ratio.call_args[0][0]
    assert call_args.id == "235"


@pytest.mark.usefixtures("init_integration")
async def test_cover_is_closing(
    hass: HomeAssistant,
    mock_seymour_client: AsyncMock,
) -> None:
    """Test cover reports closing when moving inward."""
    mock_seymour_client.get_status.return_value = SimpleNamespace(
        code=StatusCode.MOVING_INWARD,
        ratio=None,
    )
    mock_seymour_client.get_positions.return_value = [
        SimpleNamespace(motor_id=MotorID.TOP, position_pct=95.0),
        SimpleNamespace(motor_id=MotorID.BOTTOM, position_pct=95.0),
        SimpleNamespace(motor_id=MotorID.LEFT, position_pct=95.0),
        SimpleNamespace(motor_id=MotorID.RIGHT, position_pct=95.0),
    ]

    config_entry = hass.config_entries.async_entries("seymour_masking_screen")[0]
    coordinator = config_entry.runtime_data.status_coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ALL)
    assert state is not None
    assert state.state == STATE_CLOSING


@pytest.mark.usefixtures("init_integration")
async def test_cover_is_opening(
    hass: HomeAssistant,
    mock_seymour_client: AsyncMock,
) -> None:
    """Test cover reports opening when moving outward."""
    mock_seymour_client.get_status.return_value = SimpleNamespace(
        code=StatusCode.MOVING_OUTWARD,
        ratio=None,
    )

    config_entry = hass.config_entries.async_entries("seymour_masking_screen")[0]
    coordinator = config_entry.runtime_data.status_coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_TOP)
    assert state is not None
    assert state.state == STATE_OPENING


@pytest.mark.usefixtures("init_integration")
async def test_cover_is_closed(
    hass: HomeAssistant,
    mock_seymour_client: AsyncMock,
) -> None:
    """Test cover reports closed when all motors fully extended."""
    mock_seymour_client.get_status.return_value = SimpleNamespace(
        code=StatusCode.STOPPED_AT_RATIO,
        ratio=SimpleNamespace(id="178"),
    )
    mock_seymour_client.get_positions.return_value = [
        SimpleNamespace(motor_id=MotorID.TOP, position_pct=99.0),
        SimpleNamespace(motor_id=MotorID.BOTTOM, position_pct=99.0),
        SimpleNamespace(motor_id=MotorID.LEFT, position_pct=99.0),
        SimpleNamespace(motor_id=MotorID.RIGHT, position_pct=99.0),
    ]

    config_entry = hass.config_entries.async_entries("seymour_masking_screen")[0]
    coordinator = config_entry.runtime_data.status_coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ALL)
    assert state is not None
    assert state.state == STATE_CLOSED
    assert state.attributes[ATTR_CURRENT_POSITION] == 1


@pytest.mark.usefixtures("init_integration")
async def test_all_set_position_no_ratios(
    hass: HomeAssistant,
    mock_seymour_client: AsyncMock,
    mock_config_entry,
) -> None:
    """Test set_position falls back to open/close when no ratios exist."""
    mock_config_entry.runtime_data.metadata_coordinator.data.ratios = {}

    # Position >= 50 -> open
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: ENTITY_ALL, ATTR_POSITION: 80},
        blocking=True,
    )
    mock_seymour_client.move_out.assert_awaited_once()

    mock_seymour_client.move_out.reset_mock()
    mock_seymour_client.move_in.reset_mock()

    # Position < 50 -> close
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: ENTITY_ALL, ATTR_POSITION: 20},
        blocking=True,
    )
    mock_seymour_client.move_in.assert_awaited_once()


@pytest.mark.usefixtures("init_integration")
async def test_cover_position_none_when_no_positions(
    hass: HomeAssistant,
    mock_seymour_client: AsyncMock,
    mock_config_entry,
) -> None:
    """Test cover position is None when positions dict is empty."""
    mock_seymour_client.get_status.return_value = SimpleNamespace(
        code=StatusCode.STOPPED_AT_RATIO,
        ratio=SimpleNamespace(id="178"),
    )
    mock_seymour_client.get_positions.return_value = []

    coordinator = mock_config_entry.runtime_data.status_coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_TOP)
    assert state is not None
    assert state.attributes.get(ATTR_CURRENT_POSITION) is None


@pytest.mark.usefixtures("init_integration")
async def test_all_set_position_no_motor_positions(
    hass: HomeAssistant,
    mock_seymour_client: AsyncMock,
    mock_config_entry,
) -> None:
    """Test set_position fallback when ratios have empty motor_positions_pct."""
    mock_config_entry.runtime_data.metadata_coordinator.data.ratios = {
        "178": SimpleNamespace(
            ratio=SimpleNamespace(id="178"),
            label="16:9",
            motor_positions_pct=[],
            motor_adjustments_pct=[],
            width_inches=120.0,
            height_inches=67.5,
        ),
    }

    # Position >= 50 -> open fallback
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: ENTITY_ALL, ATTR_POSITION: 80},
        blocking=True,
    )
    mock_seymour_client.move_out.assert_awaited()

    mock_seymour_client.move_out.reset_mock()
    mock_seymour_client.move_in.reset_mock()

    # Position < 50 -> close fallback
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: ENTITY_ALL, ATTR_POSITION: 20},
        blocking=True,
    )
    mock_seymour_client.move_in.assert_awaited()


@pytest.mark.usefixtures("init_integration")
async def test_set_position_rejected_when_not_at_home(
    hass: HomeAssistant,
    mock_seymour_client: AsyncMock,
) -> None:
    """Test set_cover_position raises when masks are not at home."""
    # Default conftest positions are 25%/10% — not at home.
    with pytest.raises(ServiceValidationError, match="home position"):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_POSITION,
            {ATTR_ENTITY_ID: ENTITY_ALL, ATTR_POSITION: 70},
            blocking=True,
        )
    mock_seymour_client.move_to_ratio.assert_not_awaited()


@pytest.mark.usefixtures("init_integration")
async def test_set_position_allowed_when_at_home(
    hass: HomeAssistant,
    mock_seymour_client: AsyncMock,
    mock_config_entry,
) -> None:
    """Test set_cover_position succeeds when all masks are at home."""
    # Move all motors to 0% (home).
    mock_seymour_client.get_positions.return_value = [
        SimpleNamespace(motor_id=MotorID.TOP, position_pct=0.0),
        SimpleNamespace(motor_id=MotorID.BOTTOM, position_pct=0.0),
        SimpleNamespace(motor_id=MotorID.LEFT, position_pct=0.0),
        SimpleNamespace(motor_id=MotorID.RIGHT, position_pct=0.0),
    ]
    coordinator = mock_config_entry.runtime_data.status_coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: ENTITY_ALL, ATTR_POSITION: 70},
        blocking=True,
    )
    mock_seymour_client.move_to_ratio.assert_awaited_once()


@pytest.mark.usefixtures("init_integration")
async def test_set_position_allowed_within_tolerance(
    hass: HomeAssistant,
    mock_seymour_client: AsyncMock,
    mock_config_entry,
) -> None:
    """Test set_cover_position succeeds when motors are within 1% tolerance."""
    mock_seymour_client.get_positions.return_value = [
        SimpleNamespace(motor_id=MotorID.TOP, position_pct=0.5),
        SimpleNamespace(motor_id=MotorID.BOTTOM, position_pct=1.0),
        SimpleNamespace(motor_id=MotorID.LEFT, position_pct=0.0),
        SimpleNamespace(motor_id=MotorID.RIGHT, position_pct=0.8),
    ]
    coordinator = mock_config_entry.runtime_data.status_coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: ENTITY_ALL, ATTR_POSITION: 70},
        blocking=True,
    )
    mock_seymour_client.move_to_ratio.assert_awaited_once()


@pytest.mark.usefixtures("init_integration")
async def test_set_position_rejected_mixed_positions(
    hass: HomeAssistant,
    mock_seymour_client: AsyncMock,
    mock_config_entry,
) -> None:
    """Test set_cover_position rejected when some motors at home, others not."""
    mock_seymour_client.get_positions.return_value = [
        SimpleNamespace(motor_id=MotorID.TOP, position_pct=0.0),
        SimpleNamespace(motor_id=MotorID.BOTTOM, position_pct=0.0),
        SimpleNamespace(motor_id=MotorID.LEFT, position_pct=0.0),
        SimpleNamespace(motor_id=MotorID.RIGHT, position_pct=15.0),
    ]
    coordinator = mock_config_entry.runtime_data.status_coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError, match="home position"):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_POSITION,
            {ATTR_ENTITY_ID: ENTITY_ALL, ATTR_POSITION: 70},
            blocking=True,
        )
    mock_seymour_client.move_to_ratio.assert_not_awaited()


@pytest.mark.usefixtures("init_integration")
async def test_set_position_rejected_position_data_missing(
    hass: HomeAssistant,
    mock_seymour_client: AsyncMock,
    mock_config_entry,
) -> None:
    """Test set_cover_position rejected when position data is unavailable."""
    mock_seymour_client.get_positions.return_value = []
    coordinator = mock_config_entry.runtime_data.status_coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError, match="home position"):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_POSITION,
            {ATTR_ENTITY_ID: ENTITY_ALL, ATTR_POSITION: 70},
            blocking=True,
        )
    mock_seymour_client.move_to_ratio.assert_not_awaited()


@pytest.mark.usefixtures("init_integration")
async def test_set_position_no_ratios_fallback_allowed_not_at_home(
    hass: HomeAssistant,
    mock_seymour_client: AsyncMock,
    mock_config_entry,
) -> None:
    """Test directional fallback (no ratios) is allowed even when not at home."""
    mock_config_entry.runtime_data.metadata_coordinator.data.ratios = {}

    # Not at home, but fallback path (no ratios) should still work.
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: ENTITY_ALL, ATTR_POSITION: 80},
        blocking=True,
    )
    mock_seymour_client.move_out.assert_awaited_once()
