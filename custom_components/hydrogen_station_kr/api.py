import logging
import asyncio
import aiohttp
from datetime import timedelta
from typing import Any

_LOGGER = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 10
API_TIMEOUT = 30
UPDATE_INTERVAL = timedelta(minutes=5, seconds=10)

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
        
        return next(
            (station for station in all_stations if station.get(key_to_check) == identifier),
            None,
        )

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
                
                current_info = self._find_station_data(current_info_list, self.station_name)
                operation_info = self._find_station_data(operation_info_list, self.station_name)

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
            except Exception:
                _LOGGER.exception("Unexpected error on attempt %d", attempt + 1)

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
    
    def _find_station_data(self, data_list: list[dict[str, Any]], station_name: str) -> dict[str, Any] | None:
        """Find a station's data from a list by its name."""
        if not data_list:
            return None
        return next(
            (station for station in data_list if station.get("chrstn_nm") == station_name),
            None,
        )

    def _process_data(self, current_info: dict[str, Any], operation_info: dict[str, Any]) -> dict[str, Any]:
        """Process raw API data into a structured format."""
        use_posbl_dotw = operation_info.get("use_posbl_dotw", "")
        day_names = ["월", "화", "수", "목", "금", "토", "일", "공휴일"]
        closed_days = [day for day, is_open in zip(day_names, use_posbl_dotw) if is_open == '0']
        closed_days_str = "휴무 없음" if not closed_days else f"{', '.join(closed_days)} 휴무"

        oper_sttus_nm = current_info.get("oper_sttus_nm", "정보 없음")
        pos_sttus_nm = current_info.get("pos_sttus_nm", "정보 없음")
        cnf_sttus_nm = current_info.get("cnf_sttus_nm", "정보 없음")

        # --- 수정된 최종 로직 ---
        # 1. POS 상태가 '정상(영업중)'이 아니면, 가장 중요한 정보이므로 우선 표시
        if pos_sttus_nm != "영업중":
            state = pos_sttus_nm
        # 2. POS 상태는 정상이지만, 운영 상태가 '정상(운영중)'이 아닐 경우 운영 상태 표시
        elif oper_sttus_nm != "운영중":
            state = oper_sttus_nm
        # 3. 둘 다 정상이면, 혼잡도 표시
        else:
            state = cnf_sttus_nm
        # --- 수정 끝 ---

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