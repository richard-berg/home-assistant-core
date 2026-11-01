"""Button entities for Seymour masking screens."""

from __future__ import annotations

from seymourlib import protocol

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SeymourConfigEntry
from .entity import SeymourEntity
from .models import SeymourRuntimeData

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SeymourConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    runtime_data = entry.runtime_data
    metadata = runtime_data.metadata_coordinator.data

    entities: list[ButtonEntity] = []
    motors = set(metadata.system_info.mask_ids)
    motors.add(protocol.MotorID.ALL)

    for motor in sorted(motors, key=lambda item: item.value):
        entities.append(SeymourMotorButton(runtime_data, motor, action="home"))
        entities.append(SeymourMotorButton(runtime_data, motor, action="halt"))
        entities.append(SeymourMotorButton(runtime_data, motor, action="calibrate"))

    for option in protocol.DiagnosticOption:
        entities.append(SeymourDiagnosticsButton(runtime_data, option))

    async_add_entities(entities)


class SeymourMotorButton(SeymourEntity, ButtonEntity):
    """Motor-specific control buttons."""

    def __init__(
        self, runtime_data: SeymourRuntimeData, motor: protocol.MotorID, action: str
    ) -> None:
        """Initialize the button."""
        self._motor = motor
        self._action = action
        self._attr_translation_key = f"{action}_{motor.name.lower()}"
        if action in {"home", "calibrate"}:
            self._attr_entity_category = EntityCategory.CONFIG
        super().__init__(runtime_data)

    async def async_press(self) -> None:
        if self._action == "home":
            await self.runtime_data.client.home(self._motor)
        elif self._action == "halt":
            await self.runtime_data.client.halt(self._motor)
        else:
            await self.runtime_data.client.calibrate(self._motor)
        await self.runtime_data.status_coordinator.async_request_refresh()


class SeymourDiagnosticsButton(SeymourEntity, ButtonEntity):
    """Buttons that fetch diagnostic payloads from the controller."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(
        self, runtime_data: SeymourRuntimeData, option: protocol.DiagnosticOption
    ) -> None:
        """Initialize the button."""
        self._option = option
        self._attr_translation_key = f"diagnostics_{option.name.lower()}"
        super().__init__(runtime_data)

    async def async_press(self) -> None:
        payload = await self.runtime_data.client.get_diagnostics(self._option)
        self.runtime_data.diagnostics.update(self._option, payload)
