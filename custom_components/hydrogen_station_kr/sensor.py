from datetime import timedelta
import logging
import asyncio
import aiohttp
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN, CONF_STATION_NAME, CONF_API_KEY

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(minutes=5)
MAX_RETRIES = 3
RETRY_DELAY = 10

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    station_name = config_entry.data[CONF_STATION_NAME]
    api_key = config_entry.data[CONF_API_KEY]
    coordinator = HydrogenStationCoordinator(hass, station_name, api_key)
    await coordinator.async_config_entry_first_refresh()
    async_add_entities([HydrogenStationKRSensor(coordinator)], True)

class HydrogenStationCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, station_name, api_key):
        super().__init__(
            hass,
            _LOGGER,
            name="Hydrogen Station KR",
            update_method=self._async_update_data,
            update_interval=UPDATE_INTERVAL,
        )
        self.station_name = station_name
        self.api_key = api_key

    async def _async_update_data(self):
        _LOGGER.debug("Starting data update for Hydrogen Station KR")
        return await self.fetch_data()

    async def fetch_data(self):
        for attempt in range(MAX_RETRIES):
            try:
                async with aiohttp.ClientSession() as session:
                    current_info = await self._fetch_current_info(session)
                    operation_info = await self._fetch_operation_info(session)

                if current_info and operation_info:
                    data = self._process_data(current_info, operation_info)
                    _LOGGER.debug("Data update completed successfully")
                    return data
                else:
                    _LOGGER.error("Failed to fetch data from API")
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                _LOGGER.error(f"Error fetching data (attempt {attempt + 1}/{MAX_RETRIES}): {str(e)}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY)
                else:
                    return {"state": "Unknown", "attributes": {}}

    async def _fetch_current_info(self, session):
        async with session.get("http://el.h2nbiz.or.kr/api/chrstnList/currentInfo", headers={"Authorization": self.api_key}, timeout=30) as response:
            data = await response.json()
            return next((station for station in data if station["chrstn_nm"] == self.station_name), None)

    async def _fetch_operation_info(self, session):
        async with session.get("http://el.h2nbiz.or.kr/api/chrstnList/operationInfo", headers={"Authorization": self.api_key}, timeout=30) as response:
            data = await response.json()
            return next((station for station in data if station["chrstn_nm"] == self.station_name), None)

    def _process_data(self, current_info, operation_info):
        use_posbl_dotw = operation_info.get("use_posbl_dotw", "")
        day_names = ["월", "화", "수", "목", "금", "토", "일", "공휴일"]
        closed_days = [day for day, is_open in zip(day_names, use_posbl_dotw) if is_open == '0']
        closed_days_str = "휴무 없음" if not closed_days else f"{', '.join(closed_days)} 휴무"

        pos_sttus_nm = current_info["pos_sttus_nm"]
        oper_sttus_nm = current_info["oper_sttus_nm"]
        cnf_sttus_nm = current_info["cnf_sttus_nm"]

        is_business_hours = pos_sttus_nm == "운영중"

        if is_business_hours:
            if pos_sttus_nm in ["영업중지", "재고소진"]:
                state = pos_sttus_nm
            else:
                state = cnf_sttus_nm
        else:
            state = oper_sttus_nm

        attributes = {
            "chrstn_mno": current_info["chrstn_mno"],
            "POS상태": pos_sttus_nm,
            "운영상태": oper_sttus_nm,
            "대기차량수": current_info["wait_vhcle_alge"],
            "혼잡상태": cnf_sttus_nm,
            "운영상태갱신일자": current_info["last_mdfcn_dt"],
            "판매가격": operation_info.get("ntsl_pc", "정보 없음"),
            "이용가능요일": closed_days_str,
            "예약가능여부": "가능" if operation_info.get("rsvt_posbl_yn") == "Y" else "불가능",
            "휴식시간": f"{operation_info.get('rest_bgng_hr', '정보 없음')} - {operation_info.get('rest_end_hr', '정보 없음')}",
        }

        for day in ['mon', 'tues', 'wed', 'thur', 'fri', 'sat', 'sun', 'hldy']:
            attributes[f"{day}_hours"] = f"{operation_info.get(f'usebhr_hr_{day}', '정보 없음')} - {operation_info.get(f'useehr_hr_{day}', '정보 없음')}"

        return {"state": state, "attributes": attributes}

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
