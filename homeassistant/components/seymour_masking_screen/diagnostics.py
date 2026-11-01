"""Diagnostics support for the Seymour masking screen integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import SeymourConfigEntry
from .const import CONF_SERIAL_PORT

TO_REDACT = {CONF_SERIAL_PORT}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SeymourConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a Seymour config entry."""

    runtime_data = entry.runtime_data
    status = runtime_data.status_coordinator.data
    metadata = runtime_data.metadata_coordinator.data
    diag_state = runtime_data.diagnostics.state

    return {
        "config": async_redact_data(entry.data, TO_REDACT),
        "status": {
            "code": status.status.code.name,
            "ratio": status.status.ratio.id if status.status.ratio else None,
            "positions": {motor.name: pct for motor, pct in status.positions.items()},
        },
        "system": {
            "model": metadata.system_info.screen_model,
            "serial": metadata.system_info.serial_number,
            "motors": [motor.name for motor in metadata.system_info.mask_ids],
            "ratios": [setting.ratio.id for setting in metadata.ratios.values()],
        },
        "diagnostics": {
            "option": diag_state.option.name if diag_state.option else None,
            "updated": diag_state.updated.isoformat() if diag_state.updated else None,
            "preview": diag_state.text,
        },
    }
