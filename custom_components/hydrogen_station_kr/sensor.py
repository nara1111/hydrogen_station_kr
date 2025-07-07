import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, CoordinatorEntity

from .const import DOMAIN, CONF_STATION_NAME, CONF_API_KEY
from .api import HydrogenStationAPI, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


# --- 수정된 부분: 표준적이고 효율적인 설정 로직으로 변경 ---
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    station_name = config_entry.data[CONF_STATION_NAME]
    api_key = config_entry.data[CONF_API_KEY]
    api = HydrogenStationAPI(station_name, api_key)
    
    # 코디네이터를 생성하고, 첫 데이터를 가져옵니다. (API 호출 1번)
    coordinator = HydrogenStationCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()

    # 첫 데이터 로드 성공 여부 확인
    if coordinator.data:
        sensor = HydrogenStationKRSensor(coordinator)
        async_add_entities([sensor])
    else:
        _LOGGER.error(f"Failed to initialize sensor for {station_name} due to missing data.")
# --- 수정 끝 ---


class HydrogenStationCoordinator(DataUpdateCoordinator):
    """Hydrogen Station KR data update coordinator."""
    def __init__(self, hass, api: HydrogenStationAPI):
        super().__init__(
            hass,
            _LOGGER,
            name="Hydrogen Station KR",
            update_method=api.fetch_data, # 바로 api의 fetch_data 메소드를 연결
            update_interval=UPDATE_INTERVAL,
        )
        self.api = api


class HydrogenStationKRSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Hydrogen Station sensor."""
    def __init__(self, coordinator: HydrogenStationCoordinator):
        super().__init__(coordinator)
        # --- 수정된 부분: 더 명확한 이름과 ID 설정 ---
        station_info = coordinator.data.get("attributes", {})
        station_name = station_info.get("chrstn_nm", "Unknown Station")
        station_mno = station_info.get("chrstn_mno", station_name.lower().replace(" ", "_"))

        self._attr_name = station_name # 센서 이름을 충전소 이름으로 설정
        self._attr_unique_id = f"{DOMAIN}_{station_mno}" # 고유 ID 설정
        self._attr_icon = "mdi:gas-station"
        # entity_id는 Home Assistant가 unique_id를 기반으로 자동 생성하므로 수동 설정 불필요
        # --- 수정 끝 ---

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.coordinator.data.get("state")

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self.coordinator.data.get("attributes")

    # --- 추가: 기기 정보를 설정하여 여러 센서를 하나의 기기로 묶음 ---
    @property
    def device_info(self):
        """Return device information."""
        station_info = self.coordinator.data.get("attributes", {})
        return {
            "identifiers": {(DOMAIN, station_info.get("chrstn_mno"))},
            "name": station_info.get("chrstn_nm"),
            "manufacturer": "Hydrogen Station KR",
            "model": station_info.get("충전기타입", "N/A"),
        }
    # --- 추가 끝 ---