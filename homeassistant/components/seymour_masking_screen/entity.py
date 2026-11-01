"""Base entity for the Seymour Masking Screen integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import SeymourCoordinator


class SeymourEntity(CoordinatorEntity[SeymourCoordinator]):
    """Base entity for a Seymour masking screen."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SeymourCoordinator, key: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        serial_number = coordinator.serial_number
        model = coordinator.system_info.screen_model or None
        self._attr_unique_id = f"{serial_number}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial_number)},
            manufacturer=MANUFACTURER,
            model=model,
            name=f"Seymour {model}" if model else "Seymour masking screen",
            serial_number=serial_number,
        )
