"""Sensor platform for Seymour masking screens."""

from __future__ import annotations

from seymourlib import protocol

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfLength, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SeymourConfigEntry
from .const import DIAGNOSTIC_PREVIEW_LENGTH, SIGNAL_DIAGNOSTICS_UPDATED
from .entity import SeymourEntity, SeymourMetadataEntity
from .models import SeymourRuntimeData

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SeymourConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Seymour masking screen sensors."""

    runtime_data = entry.runtime_data
    metadata = runtime_data.metadata_coordinator.data

    entities: list[SensorEntity] = [
        SeymourStatusSensor(runtime_data),
        SeymourRatioSensor(runtime_data),
        SeymourConnectionSensor(runtime_data),
        SeymourDiagnosticsSensor(runtime_data),
        SeymourDimensionSensor(runtime_data, attribute="width"),
        SeymourDimensionSensor(runtime_data, attribute="height"),
    ]

    for motor in metadata.system_info.mask_ids:
        entities.append(SeymourPositionSensor(runtime_data, motor))

    async_add_entities(entities)


class SeymourStatusSensor(SeymourEntity, SensorEntity):
    """Reports the current mask status code."""

    _attr_translation_key = "status"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [code.name.lower() for code in protocol.StatusCode]

    @property
    def native_value(self) -> str:
        return self.coordinator.data.status.code.name.lower()


class SeymourRatioSensor(SeymourEntity, SensorEntity):
    """Shows the currently targeted ratio preset."""

    _attr_translation_key = "ratio"
    _attr_device_class = SensorDeviceClass.ENUM

    @property
    def native_value(self) -> str | None:
        status = self.coordinator.data.status
        if status.ratio is None:
            return None
        ratio_id = status.ratio.id
        ratios = self.runtime_data.metadata_coordinator.data.ratios
        if ratio := ratios.get(ratio_id):
            if ratio.label:
                return f"{ratio.label} ({ratio_id})"
        return ratio_id


class SeymourConnectionSensor(SeymourEntity, SensorEntity):
    """Exposes the time since the last successful transport operation."""

    _attr_translation_key = "connection_age"
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    @property
    def native_value(self) -> float | None:
        stats = self.runtime_data.client.connection_stats
        value = stats.get("time_since_last_success", -1)
        if value < 0:
            return None
        return round(value, 2)


class SeymourPositionSensor(SeymourEntity, SensorEntity):
    """Reports the current percentage for a given mask motor."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, runtime_data: SeymourRuntimeData, motor: protocol.MotorID
    ) -> None:
        """Initialize the sensor."""
        self._motor = motor
        self._attr_translation_key = f"position_{motor.name.lower()}"
        super().__init__(runtime_data)

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.positions.get(self._motor)


class SeymourDimensionSensor(SeymourMetadataEntity, SensorEntity):
    """Static dimension sensors for width/height."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = UnitOfLength.INCHES
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, runtime_data: SeymourRuntimeData, attribute: str) -> None:
        """Initialize the sensor."""
        self._attribute = attribute
        self._attr_translation_key = f"dimension_{attribute}"
        super().__init__(runtime_data)

    @property
    def native_value(self) -> float:
        system_info = self.coordinator.data.system_info
        return (
            system_info.width_inches
            if self._attribute == "width"
            else system_info.height_inches
        )


class SeymourDiagnosticsSensor(SeymourMetadataEntity, SensorEntity):
    """Text sensor with the last diagnostics payload requested by the user."""

    _attr_translation_key = "diagnostics"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        @callback
        def _handle_update() -> None:
            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_DIAGNOSTICS_UPDATED, _handle_update
            )
        )

    @property
    def native_value(self) -> str | None:
        state = self.runtime_data.diagnostics.state
        if not state.text:
            return None
        if len(state.text) <= DIAGNOSTIC_PREVIEW_LENGTH:
            return state.text
        return f"{state.text[:DIAGNOSTIC_PREVIEW_LENGTH]}…"

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        state = self.runtime_data.diagnostics.state
        return {
            "option": state.option.name if state.option else None,
            "updated": state.updated.isoformat() if state.updated else None,
            "full_text": state.text,
        }
