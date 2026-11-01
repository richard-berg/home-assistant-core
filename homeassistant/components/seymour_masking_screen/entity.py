"""Entity helpers for the Seymour masking screen integration."""

from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import SeymourMetadataCoordinator, SeymourStatusCoordinator
from .models import SeymourRuntimeData


class SeymourEntity(CoordinatorEntity[SeymourStatusCoordinator]):
    """Base entity wired to the fast status coordinator."""

    _attr_has_entity_name = True

    def __init__(self, runtime_data: SeymourRuntimeData) -> None:
        """Initialize the entity."""
        super().__init__(runtime_data.status_coordinator)
        self._runtime_data = runtime_data
        self._attr_device_info = runtime_data.device_info
        self._attr_unique_id = (
            f"{runtime_data.serial_number}_{self._attr_translation_key}"
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        remove_listener = self._runtime_data.metadata_coordinator.async_add_listener(
            self.async_write_ha_state
        )
        self.async_on_remove(remove_listener)

    @property
    def runtime_data(self) -> SeymourRuntimeData:
        """Return the integration runtime data container."""

        return self._runtime_data


class SeymourMetadataEntity(CoordinatorEntity[SeymourMetadataCoordinator]):
    """Entity bound only to the metadata coordinator."""

    _attr_has_entity_name = True

    def __init__(self, runtime_data: SeymourRuntimeData) -> None:
        """Initialize the entity."""
        super().__init__(runtime_data.metadata_coordinator)
        self._runtime_data = runtime_data
        self._attr_device_info = runtime_data.device_info
        self._attr_unique_id = (
            f"{runtime_data.serial_number}_{self._attr_translation_key}"
        )

    @property
    def runtime_data(self) -> SeymourRuntimeData:
        """Return the integration runtime data container."""

        return self._runtime_data
