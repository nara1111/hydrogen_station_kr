async def fetch_data(self):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get("http://el.h2nbiz.or.kr/api/chrstnList/currentInfo", headers={"Authorization": self.api_key}, timeout=30) as response:
                current_info = await response.json()
                current_info = next((station for station in current_info if station["chrstn_nm"] == self.station_name), None)

            async with session.get("http://el.h2nbiz.or.kr/api/chrstnList/operationInfo", headers={"Authorization": self.api_key}, timeout=30) as response:
                operation_info = await response.json()
                operation_info = next((station for station in operation_info if station["chrstn_nm"] == self.station_name), None)

            if current_info and operation_info:
                use_posbl_dotw = operation_info.get("use_posbl_dotw", "")
                day_names = ["월", "화", "수", "목", "금", "토", "일", "공휴일"]
                closed_days = [day for day, is_open in zip(day_names, use_posbl_dotw) if is_open == '0']
                closed_days_str = "휴무 없음" if not closed_days else f"{', '.join(closed_days)} 휴무"

                pos_sttus_nm = current_info["pos_sttus_nm"]
                oper_sttus_nm = current_info["oper_sttus_nm"]
                if pos_sttus_nm == "운영중":
                    state = current_info["cnf_sttus_nm"]
                else:
                    state = pos_sttus_nm

                return {
                    "state": state,
                    "attributes": {
                        "chrstn_mno": current_info["chrstn_mno"],
                        "POS상태": pos_sttus_nm,
                        "운영상태": oper_sttus_nm,  # 추가된 부분
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
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            _LOGGER.error(f"Error fetching data: {str(e)}")
            return {"state": "Unknown", "attributes": {}}
