# api.py (최종 수정 버전)

import logging
import asyncio
import aiohttp
from datetime import timedelta
from typing import Any
import unicodedata
import re

_LOGGER = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 10
API_TIMEOUT = 30
UPDATE_INTERVAL = timedelta(minutes=5, seconds=10)

def normalize_and_clean_string(text: str) -> str:
    """Normalize unicode, replace all whitespace with a single space, and strip."""
    if not isinstance(text, str):
        return ""
    normalized = unicodedata.normalize('NFC', text)
    no_multi_space = re.sub(r'\s+', ' ', normalized)
    stripped = no_multi_space.strip()
    return stripped

class HydrogenStationAPI:
    def __init__(self, station_name: str, api_key: str):
        self.station_name = station_name
        self.api_key = api_key
        self.base_url = "http://el.h2nbiz.or.kr/api/chrstnList"
        self.station_mno: str | None = None

    async def async_find_station_by_identifier(
        self, session: aiohttp.ClientSession, id_type: str, identifier: str
    ) -> dict[str, Any] | None:
        """Fetch all stations and find one by a given identifier (name or mno)."""
        all_stations = await self._fetch_api_data(session, "operationinfo")
        if not all_stations:
            return None

        key_to_check = "chrstn_nm" if id_type == "name" else "chrstn_mno"
        user_input_clean = normalize_and_clean_string(identifier)
        
        for station in all_stations:
            api_name = station.get(key_to_check)
            if api_name:
                api_name_clean = normalize_and_clean_string(api_name)
                if user_input_clean == api_name_clean:
                    return station
        return None

    async def fetch_data(self) -> dict[str, Any] | None:
        """Fetch and process data for the configured station."""
        for attempt in range(MAX_RETRIES):
            try:
                async with aiohttp.ClientSession() as session:
                    results = await asyncio.gather(
                        self._fetch_api_data(session, "currentInfo"),
                        self._fetch_api_data(session, "operationinfo"),
                        return_exceptions=True,
                    )
                
                for result in results:
                    if isinstance(result, Exception):
                        raise result

                current_info_list, operation_info_list = results
                
                # --- 수정된 부분 ---
                # 1. current_info_list에서 current_info를 찾도록 수정
                current_info = self._find_station_data(current_info_list, self.station_name)
                operation_info = self._find_station_data(operation_info_list, self.station_name)
                # --- 수정 끝 ---

                if current_info and operation_info:
                    data = self._process_data(current_info, operation_info)
                    self.station_name = data["attributes"].get("chrstn_nm", self.station_name)
                    self.station_mno = data["attributes"].get("chrstn_mno")
                    _LOGGER.debug("Data update completed successfully for %s", self.station_name)
                    return data
                
                _LOGGER.warning("Could not find data for '%s' in API response", self.station_name)
                return None
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                _LOGGER.error("Network error on attempt %d: %s", attempt + 1, e)
            except Exception as e:
                _LOGGER.exception("Unexpected error on attempt %d: %s", attempt + 1, e)
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY)
        _LOGGER.error("Max retries reached. Unable to fetch data.")
        return None

    async def _fetch_api_data(self, session: aiohttp.ClientSession, endpoint: str) -> list[dict[str, Any]]:
        """Fetch data from a specific API endpoint."""
        url = f"{self.base_url}/{endpoint}"
        headers = {"Authorization": self.api_key}
        async with session.get(url, headers=headers, timeout=API_TIMEOUT) as response:
            response.raise_for_status()
            return await response.json()

    # --- 수정된 부분: async def -> def 로 변경 ---
    def _find_station_data(self, data_list: list[dict[str, Any]], station_name: str) -> dict[str, Any] | None:
        """Find a station's data from a list by its name after setup."""
        if not data_list:
            return None
        
        station_name_clean = normalize_and_clean_string(station_name)
        for station in data_list:
            api_name = station.get("chrstn_nm")
            if api_name:
                api_name_clean = normalize_and_clean_string(api_name)
                if station_name_clean == api_name_clean:
                    return station
        return None
    # --- 수정 끝 ---

    def _process_data(self, current_info: dict[str, Any], operation_info: dict[str, Any]) -> dict[str, Any]:
        """Process raw API data into a structured format."""
        use_posbl_dotw = operation_info.get("use_posbl_dotw", "")
        day_names = ["월", "화", "수", "목", "금", "토", "일", "공휴일"]
        closed_days = [day for day, is_open in zip(day_names, use_posbl_dotw) if is_open == '0']
        closed_days_str = "휴무 없음" if not closed_days else f"{', '.join(closed_days)} 휴무"
        oper_sttus_nm = current_info.get("oper_sttus_nm", "정보 없음")
        pos_sttus_nm = current_info.get("pos_sttus_nm", "정보 없음")
        cnf_sttus_nm = current_info.get("cnf_sttus_nm", "정보 없음")
        if pos_sttus_nm != "영업중":
            state = pos_sttus_nm
        elif oper_sttus_nm != "운영중":
            state = oper_sttus_nm
        else:
            state = cnf_sttus_nm
        attributes = {
            "chrstn_nm": current_info.get("chrstn_nm"),
            "chrstn_mno": current_info.get("chrstn_mno"),
            "운영상태": oper_sttus_nm,
            "POS상태": pos_sttus_nm,
            "대기차량수": current_info.get("wait_vhcle_alge"),
            "혼잡상태": cnf_sttus_nm,
            "운영상태갱신일자": current_info.get("last_mdfcn_dt"),
            "판매가격": operation_info.get("ntsl_pc"),
            "이용가능요일": closed_days_str,
            "예약가능여부": "가능" if operation_info.get("rsvt_posbl_yn") == "Y" else "불가능",
            "휴식시간": f"{operation_info.get('rest_bgng_hr', '')} - {operation_info.get('rest_end_hr', '')}".strip(" -"),
            "이벤트": operation_info.get("event_cn"),
            "충전기타입": operation_info.get("echrgeqp_ty_nm"),
        }
        for day in ['mon', 'tues', 'wed', 'thur', 'fri', 'sat', 'sun', 'hldy']:
            start_hr = operation_info.get(f'usebhr_hr_{day}')
            end_hr = operation_info.get(f'useehr_hr_{day}')
            if start_hr and end_hr:
                attributes[f"{day}_hours"] = f"{start_hr} - {end_hr}"
        return {"state": state, "attributes": attributes}