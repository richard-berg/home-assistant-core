"""Test the Seymour masking screen config flow."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from seymourlib.exceptions import SeymourConnectionError, SeymourTransportError
from seymourlib.protocol import MotorID

from homeassistant import config_entries
from homeassistant.components.seymour_masking_screen.config_flow import (
    MANUAL_IP,
    MANUAL_SERIAL,
    InvalidSerialPort,
)
from homeassistant.components.seymour_masking_screen.const import (
    CONF_CONNECTION_TYPE,
    CONF_MASK_IDS,
    CONF_SERIAL_PORT,
    DOMAIN,
    ConnectionType,
)
from homeassistant.components.seymour_masking_screen.discovery import SeymourDiscovery
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

SERIAL_NUMBER = "AB-0124-12345"


def _make_serial(serial_str: str = SERIAL_NUMBER) -> SimpleNamespace:
    """Create a mock Serial object with to_serial_number."""
    serial = SimpleNamespace()
    serial.to_serial_number = MagicMock(return_value=serial_str)
    return serial


def _mock_client(
    serial_str: str = SERIAL_NUMBER,
    model: str = "Seymour Reference",
) -> AsyncMock:
    """Create a mock SeymourClient for config flow tests."""
    client = AsyncMock()
    client.connect = AsyncMock()
    client.close = AsyncMock()
    client.get_system_info = AsyncMock(
        return_value=SimpleNamespace(
            serial_number=_make_serial(serial_str),
            screen_model=model,
            mask_ids=[MotorID.TOP, MotorID.BOTTOM, MotorID.LEFT, MotorID.RIGHT],
        )
    )
    return client


async def test_user_selects_discovered_device(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test selecting a discovered device creates an entry."""

    discovery = SeymourDiscovery(
        key="serial://usb0",
        title="Serial · USB0",
        connection_type=ConnectionType.SERIAL,
        data={CONF_SERIAL_PORT: "/dev/ttyUSB0"},
        details={},
    )

    client = _mock_client()

    with (
        patch(
            "homeassistant.components.seymour_masking_screen.config_flow.async_discover_devices",
            return_value=[discovery],
        ),
        patch(
            "homeassistant.components.seymour_masking_screen.config_flow._build_client",
            return_value=client,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"selection": discovery.key}
        )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == f"Seymour Reference ({SERIAL_NUMBER})"
    assert result2["data"][CONF_CONNECTION_TYPE] == ConnectionType.SERIAL.value
    assert result2["data"][CONF_SERIAL_PORT] == "/dev/ttyUSB0"
    assert result2["data"][CONF_MASK_IDS] == ["T", "B", "L", "R"]
    client.connect.assert_awaited_once()
    client.close.assert_awaited_once()


async def test_manual_serial_flow_when_no_discovery(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test the flow jumps directly to manual serial when nothing is found."""

    client = _mock_client()

    with (
        patch(
            "homeassistant.components.seymour_masking_screen.config_flow.async_discover_devices",
            return_value=[],
        ),
        patch(
            "homeassistant.components.seymour_masking_screen.config_flow._build_client",
            return_value=client,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "manual_serial"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_SERIAL_PORT: "/dev/ttyUSB1"}
        )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_SERIAL_PORT] == "/dev/ttyUSB1"


async def test_manual_serial_invalid_port_error(
    hass: HomeAssistant,
) -> None:
    """Test invalid serial ports produce an error in the manual form."""

    with (
        patch(
            "homeassistant.components.seymour_masking_screen.config_flow.async_discover_devices",
            return_value=[],
        ),
        patch(
            "homeassistant.components.seymour_masking_screen.config_flow._build_client",
            side_effect=InvalidSerialPort,
        ) as build_client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_SERIAL_PORT: "bad"}
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"]["base"] == "invalid_serial"
    build_client.assert_called_once()


async def test_manual_ip_cannot_connect(
    hass: HomeAssistant,
) -> None:
    """Test manual IP step reports connection errors."""

    client = _mock_client()
    client.connect.side_effect = SeymourConnectionError()

    with (
        patch(
            "homeassistant.components.seymour_masking_screen.config_flow.async_discover_devices",
            return_value=[
                SeymourDiscovery(
                    key="serial://usb0",
                    title="Serial",
                    connection_type=ConnectionType.SERIAL,
                    data={CONF_SERIAL_PORT: "/dev/ttyUSB0"},
                    details={},
                )
            ],
        ),
        patch(
            "homeassistant.components.seymour_masking_screen.config_flow._build_client",
            return_value=client,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"selection": MANUAL_IP}
        )
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], {CONF_HOST: "1.1.1.1", CONF_PORT: 5000}
        )

    assert result3["type"] == FlowResultType.FORM
    assert result3["errors"]["base"] == "cannot_connect"


async def test_reauth_success(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test reauthentication updates the existing entry and reloads it."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_CONNECTION_TYPE: ConnectionType.SERIAL.value,
            CONF_SERIAL_PORT: "/dev/ttyUSB0",
        },
        unique_id=SERIAL_NUMBER,
    )
    entry.add_to_hass(hass)

    client = _mock_client()

    with (
        patch(
            "homeassistant.components.seymour_masking_screen.config_flow.async_discover_devices",
            return_value=[],
        ),
        patch(
            "homeassistant.components.seymour_masking_screen.config_flow._build_client",
            return_value=client,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": entry.entry_id,
            },
            data=entry.data,
        )
        assert result["step_id"] == "manual_serial"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_SERIAL_PORT: "/dev/ttyUSB9"}
        )

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert entry.data[CONF_SERIAL_PORT] == "/dev/ttyUSB9"


async def test_reauth_wrong_device_aborts(
    hass: HomeAssistant,
) -> None:
    """Test reauth aborts when a different controller is provided."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_CONNECTION_TYPE: ConnectionType.SERIAL.value,
            CONF_SERIAL_PORT: "/dev/ttyUSB0",
        },
        unique_id=SERIAL_NUMBER,
    )
    entry.add_to_hass(hass)

    client = _mock_client(serial_str="99999")

    with (
        patch(
            "homeassistant.components.seymour_masking_screen.config_flow.async_discover_devices",
            return_value=[],
        ),
        patch(
            "homeassistant.components.seymour_masking_screen.config_flow._build_client",
            return_value=client,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": entry.entry_id,
            },
            data=entry.data,
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_SERIAL_PORT: "/dev/ttyUSB9"}
        )

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "wrong_account"
    assert entry.data[CONF_SERIAL_PORT] == "/dev/ttyUSB0"


async def test_manual_ip_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test manual IP configuration creates an entry on success."""

    discovery = SeymourDiscovery(
        key="serial://usb0",
        title="Serial",
        connection_type=ConnectionType.SERIAL,
        data={CONF_SERIAL_PORT: "/dev/ttyUSB0"},
        details={},
    )
    client = _mock_client()

    with (
        patch(
            "homeassistant.components.seymour_masking_screen.config_flow.async_discover_devices",
            return_value=[discovery],
        ),
        patch(
            "homeassistant.components.seymour_masking_screen.config_flow._build_client",
            return_value=client,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"selection": MANUAL_IP}
        )
        assert result2["step_id"] == "manual_ip"

        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], {CONF_HOST: "192.168.1.100", CONF_PORT: 4999}
        )

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["data"][CONF_HOST] == "192.168.1.100"
    assert result3["data"][CONF_PORT] == 4999
    assert result3["data"][CONF_CONNECTION_TYPE] == ConnectionType.IP2SL.value


async def test_duplicate_entry_aborted(
    hass: HomeAssistant,
) -> None:
    """Test that creating a duplicate entry is aborted."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_CONNECTION_TYPE: ConnectionType.SERIAL.value,
            CONF_SERIAL_PORT: "/dev/ttyUSB0",
        },
        unique_id=SERIAL_NUMBER,
    )
    entry.add_to_hass(hass)

    client = _mock_client()

    with (
        patch(
            "homeassistant.components.seymour_masking_screen.config_flow.async_discover_devices",
            return_value=[],
        ),
        patch(
            "homeassistant.components.seymour_masking_screen.config_flow._build_client",
            return_value=client,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_SERIAL_PORT: "/dev/ttyUSB1"}
        )

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_disabled_entry_replaced_on_readd(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test that a disabled entry is removed so the user can re-add cleanly."""
    from homeassistant.config_entries import ConfigEntryDisabler

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_CONNECTION_TYPE: ConnectionType.SERIAL.value,
            CONF_SERIAL_PORT: "/dev/ttyUSB0",
            CONF_MASK_IDS: ["T", "B", "L", "R"],
        },
        unique_id=SERIAL_NUMBER,
        disabled_by=ConfigEntryDisabler.USER,
    )
    entry.add_to_hass(hass)
    old_entry_id = entry.entry_id

    client = _mock_client()

    with (
        patch(
            "homeassistant.components.seymour_masking_screen.config_flow.async_discover_devices",
            return_value=[],
        ),
        patch(
            "homeassistant.components.seymour_masking_screen.config_flow._build_client",
            return_value=client,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_SERIAL_PORT: "/dev/ttyUSB1"}
        )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_SERIAL_PORT] == "/dev/ttyUSB1"
    # The old stale entry should have been removed
    assert hass.config_entries.async_get_entry(old_entry_id) is None


async def test_setup_error_entry_replaced_on_readd(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test that a SETUP_ERROR entry is removed so the user can re-add cleanly."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_CONNECTION_TYPE: ConnectionType.SERIAL.value,
            CONF_SERIAL_PORT: "/dev/ttyUSB0",
            CONF_MASK_IDS: ["T", "B", "L", "R"],
        },
        unique_id=SERIAL_NUMBER,
    )
    entry.add_to_hass(hass)
    old_entry_id = entry.entry_id

    # Force the entry into SETUP_ERROR state
    entry.mock_state(hass, config_entries.ConfigEntryState.SETUP_ERROR)

    client = _mock_client()

    with (
        patch(
            "homeassistant.components.seymour_masking_screen.config_flow.async_discover_devices",
            return_value=[],
        ),
        patch(
            "homeassistant.components.seymour_masking_screen.config_flow._build_client",
            return_value=client,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_SERIAL_PORT: "/dev/ttyUSB1"}
        )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_SERIAL_PORT] == "/dev/ttyUSB1"
    # The old stale entry should have been removed
    assert hass.config_entries.async_get_entry(old_entry_id) is None


async def test_reconfigure_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test reconfigure flow updates the entry."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_CONNECTION_TYPE: ConnectionType.SERIAL.value,
            CONF_SERIAL_PORT: "/dev/ttyUSB0",
        },
        unique_id=SERIAL_NUMBER,
    )
    entry.add_to_hass(hass)

    client = _mock_client()

    with (
        patch(
            "homeassistant.components.seymour_masking_screen.config_flow.async_discover_devices",
            return_value=[],
        ),
        patch(
            "homeassistant.components.seymour_masking_screen.config_flow._build_client",
            return_value=client,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": entry.entry_id,
            },
            data=entry.data,
        )
        assert result["step_id"] == "manual_serial"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_SERIAL_PORT: "/dev/ttyUSB5"}
        )

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"
    assert entry.data[CONF_SERIAL_PORT] == "/dev/ttyUSB5"


async def test_reconfigure_wrong_device(
    hass: HomeAssistant,
) -> None:
    """Test reconfigure aborts when a different controller is provided."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_CONNECTION_TYPE: ConnectionType.SERIAL.value,
            CONF_SERIAL_PORT: "/dev/ttyUSB0",
        },
        unique_id=SERIAL_NUMBER,
    )
    entry.add_to_hass(hass)

    client = _mock_client(serial_str="99999")

    with (
        patch(
            "homeassistant.components.seymour_masking_screen.config_flow.async_discover_devices",
            return_value=[],
        ),
        patch(
            "homeassistant.components.seymour_masking_screen.config_flow._build_client",
            return_value=client,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": entry.entry_id,
            },
            data=entry.data,
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_SERIAL_PORT: "/dev/ttyUSB9"}
        )

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "wrong_account"
    assert entry.data[CONF_SERIAL_PORT] == "/dev/ttyUSB0"


async def test_user_selects_manual_serial_from_discovered(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test selecting manual serial from the discovered device list."""

    discovery = SeymourDiscovery(
        key="serial://usb0",
        title="Serial · USB0",
        connection_type=ConnectionType.SERIAL,
        data={CONF_SERIAL_PORT: "/dev/ttyUSB0"},
        details={},
    )
    client = _mock_client()

    with (
        patch(
            "homeassistant.components.seymour_masking_screen.config_flow.async_discover_devices",
            return_value=[discovery],
        ),
        patch(
            "homeassistant.components.seymour_masking_screen.config_flow._build_client",
            return_value=client,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        # Select manual serial entry from discovered list
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"selection": MANUAL_SERIAL}
        )
        assert result2["step_id"] == "manual_serial"

        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], {CONF_SERIAL_PORT: "/dev/ttyUSB1"}
        )

    assert result3["type"] == FlowResultType.CREATE_ENTRY


async def test_manual_serial_cannot_connect_error(
    hass: HomeAssistant,
) -> None:
    """Test manual serial step shows error on cannot connect."""

    client = _mock_client()
    client.connect.side_effect = SeymourConnectionError()

    with (
        patch(
            "homeassistant.components.seymour_masking_screen.config_flow.async_discover_devices",
            return_value=[],
        ),
        patch(
            "homeassistant.components.seymour_masking_screen.config_flow._build_client",
            return_value=client,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["step_id"] == "manual_serial"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_SERIAL_PORT: "/dev/ttyUSB0"}
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"]["base"] == "cannot_connect"


async def test_discovered_device_cannot_connect(
    hass: HomeAssistant,
) -> None:
    """Test selecting a discovered device that can't connect shows error form."""

    discovery = SeymourDiscovery(
        key="serial://usb0",
        title="Serial · USB0",
        connection_type=ConnectionType.SERIAL,
        data={CONF_SERIAL_PORT: "/dev/ttyUSB0"},
        details={},
    )
    client = _mock_client()
    client.connect.side_effect = SeymourConnectionError()

    with (
        patch(
            "homeassistant.components.seymour_masking_screen.config_flow.async_discover_devices",
            return_value=[discovery],
        ),
        patch(
            "homeassistant.components.seymour_masking_screen.config_flow._build_client",
            return_value=client,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"selection": discovery.key}
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"]["base"] == "cannot_connect"


async def test_discovered_device_unknown_error(
    hass: HomeAssistant,
) -> None:
    """Test selecting a discovered device with an unexpected error shows unknown."""

    discovery = SeymourDiscovery(
        key="serial://usb0",
        title="Serial · USB0",
        connection_type=ConnectionType.SERIAL,
        data={CONF_SERIAL_PORT: "/dev/ttyUSB0"},
        details={},
    )
    client = _mock_client()
    client.get_system_info.side_effect = RuntimeError("surprise")

    with (
        patch(
            "homeassistant.components.seymour_masking_screen.config_flow.async_discover_devices",
            return_value=[discovery],
        ),
        patch(
            "homeassistant.components.seymour_masking_screen.config_flow._build_client",
            return_value=client,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"selection": discovery.key}
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"]["base"] == "unknown"


async def test_transport_error_shows_cannot_connect(
    hass: HomeAssistant,
) -> None:
    """Test SeymourTransportError is caught and shown as cannot_connect."""

    client = _mock_client()
    client.connect.side_effect = SeymourTransportError("serial port gone")

    with (
        patch(
            "homeassistant.components.seymour_masking_screen.config_flow.async_discover_devices",
            return_value=[],
        ),
        patch(
            "homeassistant.components.seymour_masking_screen.config_flow._build_client",
            return_value=client,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["step_id"] == "manual_serial"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_SERIAL_PORT: "/dev/ttyUSB0"}
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"]["base"] == "cannot_connect"


async def test_manual_ip_unknown_error(
    hass: HomeAssistant,
) -> None:
    """Test manual IP step shows unknown error for unexpected exceptions."""

    client = _mock_client()
    client.get_system_info.side_effect = RuntimeError("surprise")

    with (
        patch(
            "homeassistant.components.seymour_masking_screen.config_flow.async_discover_devices",
            return_value=[
                SeymourDiscovery(
                    key="serial://usb0",
                    title="Serial",
                    connection_type=ConnectionType.SERIAL,
                    data={CONF_SERIAL_PORT: "/dev/ttyUSB0"},
                    details={},
                )
            ],
        ),
        patch(
            "homeassistant.components.seymour_masking_screen.config_flow._build_client",
            return_value=client,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"selection": MANUAL_IP}
        )
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], {CONF_HOST: "1.1.1.1", CONF_PORT: 5000}
        )

    assert result3["type"] == FlowResultType.FORM
    assert result3["errors"]["base"] == "unknown"


async def test_manual_serial_unknown_error(
    hass: HomeAssistant,
) -> None:
    """Test manual serial step shows unknown error for unexpected exceptions."""

    client = _mock_client()
    client.get_system_info.side_effect = RuntimeError("surprise")

    with (
        patch(
            "homeassistant.components.seymour_masking_screen.config_flow.async_discover_devices",
            return_value=[],
        ),
        patch(
            "homeassistant.components.seymour_masking_screen.config_flow._build_client",
            return_value=client,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["step_id"] == "manual_serial"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_SERIAL_PORT: "/dev/ttyUSB0"}
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"]["base"] == "unknown"
