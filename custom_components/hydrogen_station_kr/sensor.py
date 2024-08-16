import logging
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, CoordinatorEntity

from .const import DOMAIN, CONF_STATION_NAME, CONF_API_KEY
from .api import HydrogenStationAPI, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


# async def async_setup_entry(
#     hass: HomeAssistant,
#     config_entry: ConfigEntry,
#     async_add_entities: AddEntitiesCallback,
# ) -> None:
#     station_name = config_entry.data[CONF_STATION_NAME]
#     api_key = config_entry.data[CONF_API_KEY]
#     api = HydrogenStationAPI(station_name, api_key)
#     coordinator = HydrogenStationCoordinator(hass, api)
#     await coordinator.async_config_entry_first_refresh()

#     if coordinator.data and "attributes" in coordinator.data:
#         sensor = HydrogenStationKRSensor(coordinator)
#         sensor.entity_id = f"sensor.hydrogen_station_{api.station_mno}"
#         async_add_entities([sensor], True)
#     else:
#         _LOGGER.error("데이터 부족으로 수소충전소 센서 초기화 실패")

async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    station_name = config_entry.data[CONF_STATION_NAME]
    api_key = config_entry.data[CONF_API_KEY]
    api = HydrogenStationAPI(station_name, api_key)

    # API에서 초기 데이터를 가져옵니다
    initial_data = await api.fetch_data()

    if initial_data and "attributes" in initial_data:
        coordinator = HydrogenStationCoordinator(hass, api)
        await coordinator.async_refresh()  # 코디네이터를 통해 데이터를 다시 가져옵니다

        entity_id = f"sensor.hydrogen_station_{api.station_mno}"
        sensor = HydrogenStationKRSensor(coordinator, entity_id)
        async_add_entities([sensor], True)
    else:
        _LOGGER.error("초기 데이터 가져오기 실패로 수소충전소 센서 초기화 실패")


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


class HydrogenStationCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, api):
        super().__init__(
            hass,
            _LOGGER,
            name="Hydrogen Station KR",
            update_method=self._async_update_data,
            update_interval=UPDATE_INTERVAL,
        )
        self.api = api  # API 인스턴스 저장

    async def _async_update_data(self):
        _LOGGER.debug("Starting data update for Hydrogen Station KR")
        return await self.api.fetch_data()


class HydrogenStationKRSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, entity_id):
        super().__init__(coordinator)
        self._attr_icon = "mdi:gas-station"
        self._api = coordinator.api
        self.entity_id = entity_id
        self._attr_unique_id = f"hydrogen_station_kr_{self._api.station_mno}"
        self._attr_name = f"Hydrogen Station KR {self._api.station_name}"

    @property
    def state(self):
        return self.coordinator.data["state"]

    @property
    def extra_state_attributes(self):
        return self.coordinator.data["attributes"]
