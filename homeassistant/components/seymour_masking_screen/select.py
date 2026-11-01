"""Select platform for Seymour masking screens."""

from __future__ import annotations

from seymourlib import protocol

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SeymourConfigEntry
from .const import DOMAIN
from .coordinator import is_at_home
from .entity import SeymourEntity, SeymourMetadataEntity
from .models import SeymourRuntimeData

RESET_ALL_LABEL = "All ratios (factory reset)"


PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SeymourConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up select entities for a config entry."""

    runtime_data = entry.runtime_data

    entities: list[SelectEntity] = [
        SeymourRatioMoveSelect(runtime_data),
        SeymourRatioUpdateSelect(runtime_data),
        SeymourRatioResetSelect(runtime_data),
        SeymourMoveSelect(runtime_data, direction="in"),
        SeymourMoveSelect(runtime_data, direction="out"),
    ]

    async_add_entities(entities)


class SeymourRatioSelect(SeymourMetadataEntity, SelectEntity):
    """Base class for selects that operate on preset ratios."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, runtime_data: SeymourRuntimeData) -> None:
        super().__init__(runtime_data)
        self._option_map: dict[str, str] = {}

    def _build_options(self) -> list[str]:
        ratios = self.runtime_data.metadata_coordinator.data.ratios.values()
        option_map: dict[str, str] = {}
        for setting in sorted(ratios, key=lambda item: item.ratio.id):
            label = self._format_ratio(setting)
            option_map[label] = setting.ratio.id
        self._option_map = option_map
        return list(option_map)

    @staticmethod
    def _format_ratio(setting: protocol.RatioSetting) -> str:
        label = setting.label or f"Ratio {setting.ratio.id}"
        return f"{label} ({setting.ratio.id})"

    @property
    def options(self) -> list[str]:
        return self._build_options()


class SeymourRatioMoveSelect(SeymourRatioSelect):
    _attr_translation_key = "ratio_move"

    async def async_select_option(self, option: str) -> None:
        """Move to the selected ratio."""
        ratio_id = self._option_map.get(option)
        if ratio_id is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unknown_ratio",
            )
        if not is_at_home(
            self.runtime_data.status_coordinator.data.positions,
            self.runtime_data.mask_ids,
        ):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="not_at_home",
            )
        await self.runtime_data.client.move_to_ratio(protocol.Ratio(ratio_id))
        await self.runtime_data.status_coordinator.async_request_refresh()


class SeymourRatioUpdateSelect(SeymourRatioSelect):
    _attr_translation_key = "ratio_update"

    async def async_select_option(self, option: str) -> None:
        """Update the current position as the selected ratio."""
        ratio_id = self._option_map.get(option)
        if ratio_id is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unknown_ratio",
            )
        await self.runtime_data.client.update_ratio(protocol.Ratio(ratio_id))
        await self.runtime_data.metadata_coordinator.async_request_refresh()


class SeymourRatioResetSelect(SeymourRatioSelect):
    _attr_translation_key = "ratio_reset"

    def _build_options(self) -> list[str]:
        options = super()._build_options()
        options.append(RESET_ALL_LABEL)
        return options

    async def async_select_option(self, option: str) -> None:
        """Reset the selected ratio to factory default."""
        if option == RESET_ALL_LABEL:
            await self.runtime_data.client.reset_factory_default(None)
        else:
            ratio_id = self._option_map.get(option)
            if ratio_id is None:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="unknown_ratio",
                )
            await self.runtime_data.client.reset_factory_default(
                protocol.Ratio(ratio_id)
            )
        await self.runtime_data.metadata_coordinator.async_request_refresh()


class SeymourMoveSelect(SeymourEntity, SelectEntity):
    """Select entity that fires move_in or move_out commands."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, runtime_data: SeymourRuntimeData, *, direction: str) -> None:
        """Initialize the select."""
        self._direction = direction
        self._attr_translation_key = f"move_{direction}"
        self._options: dict[str, tuple[protocol.MotorID, protocol.MovementCode]] = {}
        super().__init__(runtime_data)

    @property
    def options(self) -> list[str]:
        option_map: dict[str, tuple[protocol.MotorID, protocol.MovementCode]] = {}
        motors = set(self.runtime_data.metadata_coordinator.data.system_info.mask_ids)
        motors.add(protocol.MotorID.ALL)
        for motor in sorted(motors, key=lambda item: item.value):
            for movement in protocol.MovementCode:
                movement_label = movement.name.replace("_", " ").title()
                label = f"{motor.name.title()} · {movement_label}"
                option_map[label] = (motor, movement)
        self._options = option_map
        return list(option_map)

    async def async_select_option(self, option: str) -> None:
        """Execute the selected move command."""
        if option not in self._options:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unknown_move_option",
            )
        motor, movement = self._options[option]
        if self._direction == "in":
            await self.runtime_data.client.move_in(motor, movement)
        else:
            await self.runtime_data.client.move_out(motor, movement)
        await self.runtime_data.status_coordinator.async_request_refresh()
