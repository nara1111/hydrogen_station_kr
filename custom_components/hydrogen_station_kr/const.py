# const.py

DOMAIN = "hydrogen_station_kr"

# 기존 상수
CONF_STATION_NAME = "station_name"
CONF_API_KEY = "api_key"

# --- 추가된 상수 ---
# 사용자가 어떤 방식으로 충전소를 찾을지 선택 (이름 or 관리번호)
CONF_ID_TYPE = "id_type" 
ID_TYPE_NAME = "충전소명(chrstn_nm)" # 이름으로 찾기
ID_TYPE_MNO = "충전소관리번호(chrstn_mno)"   # 관리번호로 찾기