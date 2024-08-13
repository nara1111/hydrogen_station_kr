from homeassistant import config_entries
import voluptuous as vol

from .const import DOMAIN, CONF_STATION_NAME, CONF_API_KEY

class HydrogenStationKRConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            # 여기에서 입력값을 검증할 수 있습니다.
            # 예를 들어, API 키의 유효성을 확인하거나 충전소 이름이 실제로 존재하는지 확인할 수 있습니다.
            
            # 검증이 성공적으로 완료되면 항목을 생성합니다.
            return self.async_create_entry(
                title=user_input[CONF_STATION_NAME],
                data=user_input
            )

        # 사용자 입력 양식을 표시합니다.
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_STATION_NAME): str,
                vol.Required(CONF_API_KEY): str,
            }),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        return HydrogenStationKROptionsFlow(config_entry)

class HydrogenStationKROptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_STATION_NAME, default=self.config_entry.data.get(CONF_STATION_NAME)): str,
                vol.Required(CONF_API_KEY, default=self.config_entry.data.get(CONF_API_KEY)): str,
            }),
        )
