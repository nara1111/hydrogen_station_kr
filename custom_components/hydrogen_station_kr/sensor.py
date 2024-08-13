from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import requests

from .const import DOMAIN, CONF_STATION_NAME, CONF_API_KEY

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    station_name = config_entry.data[CONF_STATION_NAME]
    api_key = config_entry.data[CONF_API_KEY]

    async_add_entities([HydrogenStationKRSensor(station_name, api_key)], True)

class HydrogenStationKRSensor(SensorEntity):
    def __init__(self, station_name, api_key):
        self._station_name = station_name
        self._api_key = api_key
        self._attr_name = f"Hydrogen Station KR {station_name}"
        self._attr_unique_id = f"hydrogen_station_kr_{station_name}"
        self._state = None
        self._attributes = {}

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attributes

    def update(self):
        headers = {"Authorization": self._api_key}
        
        # 실시간 정보 조회
        response = requests.get("http://el.h2nbiz.or.kr/api/chrstnList/currentInfo", headers=headers)
        current_info = next((station for station in response.json() if station["chrstn_nm"] == self._station_name), None)

        # 운영 정보 조회
        response = requests.get("http://el.h2nbiz.or.kr/api/chrstnList/operationInfo", headers=headers)
        operation_info = next((station for station in response.json() if station["chrstn_nm"] == self._station_name), None)

        if current_info and operation_info:
            self._state = current_info["oper_sttus_nm"]
            self._attributes = {
                "대기차량수": current_info["wait_vhcle_alge"],
                "혼잡상태": current_info["cnf_sttus_nm"],
                "운영상태갱신일자": current_info["last_mdfcn_dt"],
                "판매가격": operation_info["ntsl_pc"],
                "이용가능요일": operation_info["use_posbl_dotw"],
                "영업시작시간": operation_info["usebhr_hr_mon"],
                "영업종료시간": operation_info["useehr_hr_mon"],
                "예약가능여부": "가능" if operation_info["rsvt_posbl_yn"] == "Y" else "불가능"
            }
        else:
            self._state = "Unknown"
            self._attributes = {}
