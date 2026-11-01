"""The Seymour Masking Screen integration."""

from seymourlib.client import SeymourClient
from seymourlib.exceptions import SeymourError
from seymourlib.transport import URLTransport

from homeassistant.const import CONF_DEVICE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import SeymourConfigEntry, SeymourCoordinator

PLATFORMS: list[Platform] = [Platform.COVER]


async def async_setup_entry(hass: HomeAssistant, entry: SeymourConfigEntry) -> None:
    """Set up Seymour Masking Screen from a config entry."""
    url: str = entry.data[CONF_DEVICE]
    client = SeymourClient(URLTransport(url))

    # The Global Caché IP2SL accepts a single TCP connection per serial port,
    # so the client must be closed on every failure path or later retries
    # can't connect.
    try:
        await client.connect()
        system_info = await client.get_system_info()
    except SeymourError as err:
        await client.close()
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            # An ESPHome proxy URL can carry the API key in its query string
            translation_placeholders={"device": url.split("?", 1)[0]},
        ) from err

    coordinator = SeymourCoordinator(hass, entry, client, system_info)
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        await client.close()
        raise

    entry.runtime_data = coordinator
    entry.async_on_unload(client.close)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: SeymourConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
