"""Snapshot tests for Seymour masking screen entity platforms."""

from __future__ import annotations

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import SERIAL_NUMBER

from tests.common import MockConfigEntry, snapshot_platform

DOMAIN = "seymour_masking_screen"


@pytest.fixture(
    params=[Platform.BUTTON, Platform.COVER, Platform.SELECT, Platform.SENSOR]
)
def platforms(request: pytest.FixtureRequest) -> list[Platform]:
    """Yield each platform individually so snapshot_platform sees one at a time."""
    return [request.param]


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Snapshot-test all entities for each platform."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    # Verify every entity is assigned to the expected device.
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, SERIAL_NUMBER)}
    )
    assert device_entry is not None

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    for entity_entry in entity_entries:
        assert entity_entry.device_id == device_entry.id
