import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, CoordinatorEntity

from .const import DOMAIN, CONF_STATION_NAME, CONF_API_KEY
from .api import HydrogenStationAPI, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    station_name = config_entry.data[CONF_STATION_NAME]
    api_key = config_entry.data[CONF_API_KEY]
    api = HydrogenStationAPI(station_name, api_key)
    coordinator = HydrogenStationCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()
    async_add_entities([HydrogenStationKRSensor(coordinator)], True)

class HydrogenStationCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, api):
        super().__init__(
            hass,
            _LOGGER,
            name="Hydrogen Station KR",
            update_method=self._async_update_data,
            update_interval=UPDATE_INTERVAL,
        )
        self.api = api

    async def _async_update_data(self):
        _LOGGER.debug("Starting data update for Hydrogen Station KR")
        return await self.api.fetch_data()

class HydrogenStationKRSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"hydrogen_station_kr_{coordinator.api.station_name}"
        self._attr_icon = "mdi:gas-station"

    @property
    def name(self):
        chrstn_mno = self.coordinator.data["attributes"].get("chrstn_mno", "Unknown")
        return f"Hydrogen Station {chrstn_mno}"

    @property
    def state(self):
        return self.coordinator.data["state"]

    @property
    def extra_state_attributes(self):
        return self.coordinator.data["attributes"]
