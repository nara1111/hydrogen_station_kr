# custom_components/hydrogen_station_kr/__init__.py

from __future__ import annotations
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform

from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    _LOGGER.debug("Setting up entry %s.", entry.entry_id)
    
    entry.async_on_unload(entry.add_update_listener(options_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    _LOGGER.debug("Unloading entry %s.", entry.entry_id)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

async def options_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    _LOGGER.info("Configuration options for %s have changed, reloading.", entry.entry_id)
    await hass.config_entries.async_reload(entry.entry_id)