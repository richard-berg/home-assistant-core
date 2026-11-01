"""Config flow for the Seymour Masking Screen integration."""

import asyncio
from typing import Any, override

import probatio
from seymourlib.client import SeymourClient
from seymourlib.discovery import (
    DEFAULT_DISCOVERY_INTERVAL,
    DiscoveryError,
    TCPTransportCandidate,
    enumerate_tcp_transports,
)
from seymourlib.exceptions import SeymourConnectionError, SeymourError
from seymourlib.protocol import SystemInfo
from seymourlib.transport import ITACH_SERIAL_PORT, URLTransport, tcp_url

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    SerialPortSelector,
    TextSelector,
)

from .const import DOMAIN, LOGGER

# Fail fast while the user waits, instead of the library's longer
# retry schedule meant for a running integration.
VALIDATION_TIMEOUT = 5.0
VALIDATION_RETRIES = 1


class NotSeymourError(Exception):
    """Raised when the device answered but is not a Seymour controller."""


async def _async_get_system_info(url: str) -> SystemInfo:
    """Connect to the controller at the given URL and read its system info."""
    client = SeymourClient(
        URLTransport(url, connect_timeout=VALIDATION_TIMEOUT),
        max_retries=VALIDATION_RETRIES,
        request_timeout=VALIDATION_TIMEOUT,
    )
    try:
        await client.connect()
        return await client.get_system_info()
    except SeymourConnectionError:
        raise
    except SeymourError as err:
        raise NotSeymourError from err
    finally:
        # The IP2SL allows one connection per port, so always release it
        # before the config entry sets up its own client.
        await client.close()


async def _async_discover_ip2sl() -> list[TCPTransportCandidate]:
    """Listen for Global Caché IP2SL discovery beacons."""
    try:
        return await enumerate_tcp_transports()
    except (DiscoveryError, OSError) as err:
        LOGGER.debug("IP2SL discovery failed: %s", err)
        return []


class SeymourConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Seymour Masking Screen."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_task: asyncio.Task[list[TCPTransportCandidate]] | None = None
        self._discovered: list[TCPTransportCandidate] = []

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask how the controller is connected."""
        return self.async_show_menu(step_id="user", menu_options=["serial", "ip2sl"])

    async def async_step_serial(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a controller on a serial port or serial proxy."""
        errors: dict[str, str] = {}
        if user_input is not None:
            url = user_input[CONF_DEVICE]
            self._async_abort_entries_match({CONF_DEVICE: url})
            if system_info := await self._async_validate(url, errors):
                return await self._async_create_entry(url, system_info)

        return self.async_show_form(
            step_id="serial",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema({probatio.Required(CONF_DEVICE): SerialPortSelector()}),
                user_input or {},
            ),
            errors=errors,
        )

    async def async_step_ip2sl(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Look for Global Caché IP2SL bridges on the network."""
        if self._discovery_task is None:
            self._discovery_task = self.hass.async_create_task(_async_discover_ip2sl())
        elif self._discovery_task.done():
            self._discovered = self._discovery_task.result()
            return self.async_show_progress_done(next_step_id="ip2sl_host")
        return self.async_show_progress(
            step_id="ip2sl",
            progress_action="discover_ip2sl",
            progress_task=self._discovery_task,
            description_placeholders={
                "seconds": str(round(DEFAULT_DISCOVERY_INTERVAL))
            },
        )

    async def async_step_ip2sl_host(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a controller behind a Global Caché IP2SL bridge."""
        errors: dict[str, str] = {}
        if user_input is not None:
            url = tcp_url(user_input[CONF_HOST].strip(), int(user_input[CONF_PORT]))
            self._async_abort_entries_match({CONF_DEVICE: url})
            if system_info := await self._async_validate(url, errors):
                return await self._async_create_entry(url, system_info)

        host_selector: SelectSelector | TextSelector = TextSelector()
        if self._discovered:
            host_selector = SelectSelector(
                SelectSelectorConfig(
                    options=[
                        SelectOptionDict(
                            value=candidate.host,
                            label=f"{candidate.metadata.get('Model', 'IP2SL')} "
                            f"({candidate.host})",
                        )
                        for candidate in self._discovered
                    ],
                    custom_value=True,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            )

        suggested: dict[str, Any] = {CONF_PORT: ITACH_SERIAL_PORT}
        if self._discovered:
            suggested[CONF_HOST] = self._discovered[0].host
        return self.async_show_form(
            step_id="ip2sl_host",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(
                    {
                        probatio.Required(CONF_HOST): host_selector,
                        probatio.Required(CONF_PORT): NumberSelector(
                            NumberSelectorConfig(
                                min=1, max=65535, step=1, mode=NumberSelectorMode.BOX
                            )
                        ),
                    }
                ),
                user_input or suggested,
            ),
            errors=errors,
        )

    async def _async_validate(
        self, url: str, errors: dict[str, str]
    ) -> SystemInfo | None:
        """Read the system info of the controller, or record an error."""
        try:
            return await _async_get_system_info(url)
        except SeymourConnectionError:
            errors["base"] = "cannot_connect"
        except NotSeymourError:
            errors["base"] = "not_seymour"
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        return None

    async def _async_create_entry(
        self, url: str, system_info: SystemInfo
    ) -> ConfigFlowResult:
        """Create the config entry for a validated controller."""
        await self.async_set_unique_id(system_info.serial_number.to_serial_number())
        self._abort_if_unique_id_configured(updates={CONF_DEVICE: url})
        model = system_info.screen_model or None
        return self.async_create_entry(
            title=f"Seymour {model}" if model else "Seymour masking screen",
            data={CONF_DEVICE: url},
        )
