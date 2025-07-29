# custom_components/hydrogen_station_kr/sensor.py

import logging
from typing import Any, cast
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, CoordinatorEntity

from .const import DOMAIN, CONF_API_KEY
from .api import HydrogenStationAPI, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    api_key = config_entry.data[CONF_API_KEY]
    stations_to_add = config_entry.options.get("stations", {}).values()
    
    sensors = []
    for station in stations_to_add:
        station_mno = station.get("mno")
        station_name = station.get("name", "Unknown Station")
        
        if not station_mno:
            _LOGGER.warning("Skipping station with missing 'mno': %s", station)
            continue

        api = HydrogenStationAPI(api_key=api_key, station_mno=station_mno, station_name=station_name)
        coordinator = DataUpdateCoordinator(
            hass, _LOGGER,
            name=f"{DOMAIN}_{station_name}",
            update_method=api.fetch_data,
            update_interval=UPDATE_INTERVAL,
        )
        coordinator.api = api
        await coordinator.async_config_entry_first_refresh()
        sensors.append(HydrogenStationKRSensor(coordinator))

    async_add_entities(sensors)

class HydrogenStationKRSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True 
    _attr_icon = "mdi:gas-station"

    def __init__(self, coordinator: DataUpdateCoordinator):
        super().__init__(coordinator)
        api: HydrogenStationAPI = coordinator.api
        self._attr_unique_id = api.station_mno
        
        ### 수정된 부분 ###
        # 장치 ID를 새로운 값으로 변경하여, Home Assistant가 기존 캐시를 무시하고
        # 새로운 장치를 등록하도록 강제합니다. 'name' 키는 당연히 없습니다.
        self._attr_device_info = {
            "identifiers": {(DOMAIN, "h2_station_device_v2")},
            "manufacturer": "h2nbiz",
        }

    @property
    def name(self) -> str:
        return self.coordinator.api.station_name

    @property
    def state(self) -> str | None:
        if self.coordinator.data:
            return self.coordinator.data.get("state")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.coordinator.data:
            return self.coordinator.data.get("attributes")
        return None