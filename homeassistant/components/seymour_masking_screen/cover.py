"""Cover platform for Seymour masking screens.

Each physical mask motor is exposed as an individual cover entity.
Group aliases supported by the controller (vertical, horizontal, all)
are exposed as additional cover entities that aggregate the positions
of their constituent motors.
"""

from __future__ import annotations

from typing import Any

from seymourlib import protocol

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SeymourConfigEntry
from .const import DOMAIN
from .coordinator import is_at_home
from .entity import SeymourEntity
from .models import SeymourRuntimeData

PARALLEL_UPDATES = 1

# Maps each group alias to the individual motors it aggregates.
_GROUP_MEMBERS: dict[protocol.MotorID, list[protocol.MotorID]] = {
    protocol.MotorID.VERTICAL: [protocol.MotorID.TOP, protocol.MotorID.BOTTOM],
    protocol.MotorID.HORIZONTAL: [protocol.MotorID.LEFT, protocol.MotorID.RIGHT],
}

# Individual physical motors (not aliases).
_INDIVIDUAL_MOTORS: set[protocol.MotorID] = {
    protocol.MotorID.TOP,
    protocol.MotorID.BOTTOM,
    protocol.MotorID.LEFT,
    protocol.MotorID.RIGHT,
}


def _resolve_group_motors(
    motor_id: protocol.MotorID,
    mask_ids: list[protocol.MotorID],
) -> list[protocol.MotorID]:
    """Return the individual motors aggregated by *motor_id*.

    For individual motors the list contains only that motor.
    For ALL, every detected mask is included.
    For VERTICAL / HORIZONTAL, the corresponding pair is returned.
    """
    if motor_id in _INDIVIDUAL_MOTORS:
        return [motor_id]
    if motor_id is protocol.MotorID.ALL:
        return list(mask_ids)
    return _GROUP_MEMBERS.get(motor_id, [motor_id])


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SeymourConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Seymour masking screen cover entities."""
    runtime_data = entry.runtime_data
    mask_ids = runtime_data.mask_ids
    mask_id_set = set(mask_ids)

    entities: list[CoverEntity] = []

    # One cover per detected physical motor.
    for motor in mask_ids:
        entities.append(SeymourMaskCover(runtime_data, motor))

    # Group alias covers — only when all constituent motors are present.
    for alias, members in _GROUP_MEMBERS.items():
        if all(m in mask_id_set for m in members):
            entities.append(SeymourMaskCover(runtime_data, alias))

    # ALL alias — always created when at least one mask exists.
    if mask_ids:
        entities.append(SeymourMaskCover(runtime_data, protocol.MotorID.ALL))

    async_add_entities(entities)


class SeymourMaskCover(SeymourEntity, CoverEntity):
    """Representation of a single mask motor or motor group as a cover."""

    _attr_device_class = CoverDeviceClass.SHADE

    def __init__(
        self,
        runtime_data: SeymourRuntimeData,
        motor_id: protocol.MotorID,
    ) -> None:
        """Initialize the cover entity."""
        self._motor_id = motor_id
        self._member_motors = _resolve_group_motors(motor_id, runtime_data.mask_ids)
        self._attr_translation_key = f"mask_{motor_id.name.lower()}"

        # Only the ALL group supports set_position via ratio presets.
        features = (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
        )
        if motor_id is protocol.MotorID.ALL:
            features |= CoverEntityFeature.SET_POSITION
        self._attr_supported_features = features

        super().__init__(runtime_data)

    @property
    def current_cover_position(self) -> int | None:
        """Return the position of this mask or motor group.

        HA convention: 0 = closed, 100 = fully open.
        seymourlib: 0 = fully retracted (open), 100 = fully extended (closed).
        We invert: ha_pos = 100 - seymourlib_pos.
        """
        positions = self.coordinator.data.positions
        values = [positions[m] for m in self._member_motors if m in positions]
        if not values:
            return None
        avg = sum(values) / len(values)
        return round(100 - avg)

    @property
    def is_closed(self) -> bool | None:
        """Return True if the mask(s) are fully deployed (closed)."""
        pos = self.current_cover_position
        if pos is None:
            return None
        return pos <= 2

    @property
    def is_opening(self) -> bool:
        """Return True if the screen masks are retracting (opening)."""
        return self.coordinator.data.status.code is protocol.StatusCode.MOVING_OUTWARD

    @property
    def is_closing(self) -> bool:
        """Return True if the screen masks are extending (closing)."""
        return self.coordinator.data.status.code is protocol.StatusCode.MOVING_INWARD

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Retract the mask(s)."""
        await self.runtime_data.client.move_out(
            self._motor_id, protocol.MovementCode.UNTIL_LIMIT
        )
        await self.runtime_data.status_coordinator.async_request_refresh()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Extend the mask(s)."""
        await self.runtime_data.client.move_in(
            self._motor_id, protocol.MovementCode.UNTIL_LIMIT
        )
        await self.runtime_data.status_coordinator.async_request_refresh()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Halt the mask motor(s) immediately."""
        await self.runtime_data.client.halt(self._motor_id)
        await self.runtime_data.status_coordinator.async_request_refresh()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move masks to a position by selecting the nearest ratio preset.

        Only supported on the ALL motor group because move_to_ratio always
        commands every motor simultaneously.

        HA position: 0 = closed, 100 = open.
        """
        ha_position: int = kwargs[ATTR_POSITION]
        target_pct = 100 - ha_position  # invert for seymourlib convention

        ratios = self.runtime_data.metadata_coordinator.data.ratios
        if not ratios:
            if ha_position >= 50:
                await self.async_open_cover()
            else:
                await self.async_close_cover()
            return

        # Find the closest ratio by average motor position.
        best_ratio: protocol.Ratio | None = None
        best_distance = float("inf")
        for setting in ratios.values():
            motor_positions = setting.motor_positions_pct
            if motor_positions:
                avg_pct = sum(motor_positions) / len(motor_positions)
                distance = abs(avg_pct - target_pct)
                if distance < best_distance:
                    best_distance = distance
                    best_ratio = setting.ratio

        if best_ratio is not None:
            if not is_at_home(
                self.coordinator.data.positions,
                self.runtime_data.mask_ids,
            ):
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="not_at_home",
                )
            await self.runtime_data.client.move_to_ratio(best_ratio)
        elif ha_position >= 50:
            await self.async_open_cover()
        else:
            await self.async_close_cover()

        await self.runtime_data.status_coordinator.async_request_refresh()
