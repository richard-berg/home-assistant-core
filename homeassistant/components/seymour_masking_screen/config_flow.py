"""Config flow for the Seymour Masking Screen integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from seymourlib import protocol
from seymourlib.client import SeymourClient
from seymourlib.exceptions import SeymourError
from seymourlib.transport import SerialTransport, TCPTransport
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigEntryState,
    ConfigFlowResult,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_CONNECTION_TYPE,
    CONF_MASK_IDS,
    CONF_SERIAL_PORT,
    DEFAULT_TCP_PORT,
    DOMAIN,
    ConnectionType,
)
from .discovery import SeymourDiscovery, async_discover_devices

_LOGGER = logging.getLogger(__name__)

MANUAL_SERIAL = "manual_serial"
MANUAL_IP = "manual_ip"


class SeymourConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Seymour masking screens."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered: list[SeymourDiscovery] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step where we offer discovered devices."""

        errors: dict[str, str] = {}

        if user_input is not None:
            selection = user_input["selection"]
            if selection == MANUAL_SERIAL:
                return await self.async_step_manual_serial()
            if selection == MANUAL_IP:
                return await self.async_step_manual_ip()
            try:
                return await self._async_handle_discovery(selection)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except AbortFlow:
                raise
            except Exception:
                _LOGGER.exception("Unexpected error during discovery setup")
                errors["base"] = "unknown"

        if not self._discovered:
            self._discovered = await async_discover_devices(self.hass)
        if not self._discovered:
            return await self.async_step_manual_serial()

        options: dict[str, str] = {
            MANUAL_SERIAL: self._titles[ConnectionType.SERIAL],
            MANUAL_IP: self._titles[ConnectionType.IP2SL],
        }
        for candidate in self._discovered:
            options[candidate.key] = candidate.title

        schema = vol.Schema({vol.Required("selection"): vol.In(options)})
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_manual_serial(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manual serial configuration step."""

        errors: dict[str, str] = {}
        if user_input is not None:
            data = {
                CONF_CONNECTION_TYPE: ConnectionType.SERIAL.value,
                CONF_SERIAL_PORT: user_input[CONF_SERIAL_PORT],
            }
            try:
                return await self._async_create_entry(data)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidSerialPort:
                errors["base"] = "invalid_serial"
            except AbortFlow:
                raise
            except Exception:
                _LOGGER.exception("Unexpected error during serial setup")
                errors["base"] = "unknown"

        schema = vol.Schema({vol.Required(CONF_SERIAL_PORT): str})
        return self.async_show_form(
            step_id="manual_serial", data_schema=schema, errors=errors
        )

    async def async_step_manual_ip(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manual IP2SL configuration step."""

        errors: dict[str, str] = {}
        if user_input is not None:
            data = {
                CONF_CONNECTION_TYPE: ConnectionType.IP2SL.value,
                CONF_HOST: user_input[CONF_HOST],
                CONF_PORT: user_input.get(CONF_PORT, DEFAULT_TCP_PORT),
            }
            try:
                return await self._async_create_entry(data)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except AbortFlow:
                raise
            except Exception:
                _LOGGER.exception("Unexpected error during IP setup")
                errors["base"] = "unknown"

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_PORT, default=DEFAULT_TCP_PORT): int,
            }
        )
        return self.async_show_form(
            step_id="manual_ip", data_schema=schema, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication by re-running manual steps."""
        return await self.async_step_user()

    async def async_step_reconfigure(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Allow updating connection details without removing the entry."""
        return await self.async_step_user()

    async def _async_handle_discovery(self, key: str) -> ConfigFlowResult:
        """Handle a user selecting a discovered device."""
        for candidate in self._discovered:
            if candidate.key == key:
                data = {
                    CONF_CONNECTION_TYPE: candidate.connection_type.value,
                    **candidate.data,
                }
                return await self._async_create_entry(data)
        return self.async_abort(reason="unknown")

    async def _async_create_entry(
        self,
        data: Mapping[str, Any],
        *,
        default_title: str | None = None,
    ) -> ConfigFlowResult:
        """Validate, deduplicate, and create or update a config entry."""
        info = await self._async_validate_connection(data)
        serial_str = info.serial_number.to_serial_number()
        existing_entry = await self.async_set_unique_id(serial_str)

        entry_data = dict(data)
        entry_data[CONF_MASK_IDS] = [m.value for m in info.mask_ids]

        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch(reason="wrong_account")
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data_updates=entry_data
            )

        if self.source == SOURCE_RECONFIGURE:
            self._abort_if_unique_id_mismatch(reason="wrong_account")
            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(), data_updates=entry_data
            )

        # If a previous entry for this screen exists but is disabled or
        # permanently failed, remove it so the user can re-add cleanly
        # instead of being stuck with "already configured."
        if existing_entry is not None and (
            existing_entry.disabled_by is not None
            or existing_entry.state is ConfigEntryState.SETUP_ERROR
        ):
            await self.hass.config_entries.async_remove(existing_entry.entry_id)

        self._abort_if_unique_id_configured(updates=dict(data))
        title = default_title or f"{info.screen_model} ({serial_str})"
        return self.async_create_entry(title=title, data=entry_data)

    async def _async_validate_connection(
        self, data: Mapping[str, Any]
    ) -> protocol.SystemInfo:
        """Build a client, connect, fetch system info, and close."""
        client = _build_client(data)
        try:
            await client.connect()
            system_info = await client.get_system_info()
        except SeymourError as exc:
            raise CannotConnect from exc
        finally:
            await client.close()

        return system_info

    @property
    def _titles(self) -> dict[ConnectionType, str]:
        return {
            ConnectionType.SERIAL: "Enter serial port manually",
            ConnectionType.IP2SL: "Enter Global Cache IP",
        }


def _build_client(data: Mapping[str, Any]) -> SeymourClient:
    transport: SerialTransport | TCPTransport
    connection = ConnectionType(data[CONF_CONNECTION_TYPE])
    if connection is ConnectionType.SERIAL:
        port = data.get(CONF_SERIAL_PORT)
        if not port:
            raise InvalidSerialPort
        transport = SerialTransport(port)
    else:
        host = data[CONF_HOST]
        tcp_port = data.get(CONF_PORT, DEFAULT_TCP_PORT)
        transport = TCPTransport(host, tcp_port)

    return SeymourClient(transport)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidSerialPort(HomeAssistantError):
    """Error for missing or invalid serial ports."""
