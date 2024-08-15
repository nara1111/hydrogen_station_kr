import logging
import asyncio
import aiohttp
from datetime import timedelta

_LOGGER = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 10
UPDATE_INTERVAL = timedelta(minutes=5, seconds=10)

class HydrogenStationAPI:
    def __init__(self, station_name, api_key):
        self.station_name = station_name
        self.api_key = api_key
        self.base_url = "http://el.h2nbiz.or.kr/api/chrstnList"

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
                    _LOGGER.error("Failed to fetch data from API: Empty response")
            except aiohttp.ClientError as e:
                _LOGGER.error(f"Network error during API call (attempt {attempt + 1}/{MAX_RETRIES}): {str(e)}")
            except asyncio.TimeoutError:
                _LOGGER.error(f"Timeout during API call (attempt {attempt + 1}/{MAX_RETRIES})")
            except Exception as e:
                _LOGGER.error(f"Unexpected error during API call (attempt {attempt + 1}/{MAX_RETRIES}): {str(e)}")

            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY)
            else:
                _LOGGER.error("Max retries reached. Unable to fetch data from API.")
                return {"state": "Unknown", "attributes": {}}

    async def _fetch_current_info(self, session):
        async with session.get(f"{self.base_url}/currentInfo", headers={"Authorization": self.api_key}, timeout=30) as response:
            response.raise_for_status()
            data = await response.json()
            return next((station for station in data if station["chrstn_nm"] == self.station_name), None)

    async def _fetch_operation_info(self, session):
        async with session.get(f"{self.base_url}/operationInfo", headers={"Authorization": self.api_key}, timeout=30) as response:
            response.raise_for_status()
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

        is_business_hours = oper_sttus_nm == "운영중"

        if is_business_hours:
            if pos_sttus_nm != "영업중":
                state = pos_sttus_nm
            else:
                state = cnf_sttus_nm
        else:
            state = oper_sttus_nm

        attributes = {
            # "chrstn_nm": current_info["chrstn_nm"],
            "chrstn_mno": current_info["chrstn_mno"],
            "운영상태": oper_sttus_nm,
            "POS상태": pos_sttus_nm,
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
