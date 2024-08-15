from datetime import datetime, timedelta
import logging
import asyncio
import aiohttp
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, CoordinatorEntity

from .const import DOMAIN, CONF_STATION_NAME, CONF_API_KEY

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    start_time = datetime.now()
    _LOGGER.debug("Starting async_setup_entry")

    station_name = config_entry.data[CONF_STATION_NAME]
    api_key = config_entry.data[CONF_API_KEY]

    coordinator = HydrogenStationCoordinator(hass, station_name, api_key)
    
    _LOGGER.debug("Initializing coordinator")
    init_start = datetime.now()
    await coordinator.async_config_entry_first_refresh()
    _LOGGER.debug(f"Coordinator initialization took {(datetime.now() - init_start).total_seconds():.2f} seconds")

    async_add_entities([HydrogenStationKRSensor(coordinator)], True)

    _LOGGER.debug(f"Total async_setup_entry execution time: {(datetime.now() - start_time).total_seconds():.2f} seconds")

class HydrogenStationCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, station_name, api_key):
        super().__init__(
            hass,
            _LOGGER,
            name="Hydrogen Station KR",
            update_interval=timedelta(minutes=5),
        )
        self.station_name = station_name
        self.api_key = api_key
        self.session = aiohttp.ClientSession()

    async def _async_update_data(self):
        try:
            async with self.session.get("http://el.h2nbiz.or.kr/api/chrstnList/currentInfo", headers={"Authorization": self.api_key}) as response:
                current_info = await response.json()
                current_info = next((station for station in current_info if station["chrstn_nm"] == self.station_name), None)

            async with self.session.get("http://el.h2nbiz.or.kr/api/chrstnList/operationInfo", headers={"Authorization": self.api_key}) as response:
                operation_info = await response.json()
                operation_info = next((station for station in operation_info if station["chrstn_nm"] == self.station_name), None)

            if current_info and operation_info:
                use_posbl_dotw = operation_info.get("use_posbl_dotw", "")
                day_names = ["월", "화", "수", "목", "금", "토", "일", "공휴일"]
                closed_days = [day for day, is_open in zip(day_names, use_posbl_dotw) if is_open == '0']
                closed_days_str = "휴무 없음" if not closed_days else f"{', '.join(closed_days)} 휴무"

                pos_sttus_nm = current_info["pos_sttus_nm"]
                if pos_sttus_nm == "운영중":
                    state = current_info["cnf_sttus_nm"]
                else:
                    state = pos_sttus_nm

                return {
                    "state": state,
                    "attributes": {
                        "chrstn_mno": current_info["chrstn_mno"],
                        "POS상태": pos_sttus_nm,
                        "대기차량수": current_info["wait_vhcle_alge"],
                        "혼잡상태": current_info["cnf_sttus_nm"],
                        "운영상태갱신일자": current_info["last_mdfcn_dt"],
                        "판매가격": operation_info.get("ntsl_pc", "정보 없음"),
                        "이용가능요일": closed_days_str,
                        "예약가능여부": "가능" if operation_info.get("rsvt_posbl_yn") == "Y" else "불가능",
                        "휴식시간": f"{operation_info.get('rest_bgng_hr', '정보 없음')} - {operation_info.get('rest_end_hr', '정보 없음')}",
                        **{f"{day}_hours": f"{operation_info.get(f'usebhr_hr_{day}', '정보 없음')} - {operation_info.get(f'useehr_hr_{day}', '정보 없음')}" 
                          for day in ['mon', 'tues', 'wed', 'thur', 'fri', 'sat', 'sun', 'hldy']}
                    }
                }
            else:
                _LOGGER.error("Failed to fetch data from API")
                return {"state": "Unknown", "attributes": {}}
        except aiohttp.ClientError as e:
            _LOGGER.error(f"Error fetching data: {str(e)}")
            return {"state": "Unknown", "attributes": {}}

    async def async_config_entry_first_refresh(self):
        """Refresh data for the first time when setting up an entry."""
        await self.async_refresh()

class HydrogenStationKRSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"hydrogen_station_kr_{coordinator.station_name}"

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
