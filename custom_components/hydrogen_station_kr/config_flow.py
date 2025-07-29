# custom_components/hydrogen_station_kr/config_flow.py

import logging
from typing import Any
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigEntry, OptionsFlow
from homeassistant.core import callback
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, CONF_STATION_MNO, KEY_CHRSTN_MNO, KEY_CHRSTN_NM
from .api import HydrogenStationAPI

_LOGGER = logging.getLogger(__name__)

class HydrogenStationKRConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> dict[str, Any]:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            return self.async_create_entry(title="수소 충전소", data=user_input)
        return self.async_show_form(
            step_id="user", data_schema=vol.Schema({vol.Required(CONF_API_KEY): str})
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return HydrogenStationKROptionsFlow(config_entry)

class HydrogenStationKROptionsFlow(OptionsFlow):
    def __init__(self, config_entry: ConfigEntry):
        self.config_entry = config_entry
        self.found_stations: dict[str, str] = {}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> dict[str, Any]:
        station_list_str = "\n".join([f"- {s['name']}" for s in self.config_entry.options.get("stations", {}).values()])
        return self.async_show_menu(
            step_id="init",
            menu_options=["add_station", "remove_station"],
            description_placeholders={"stations": station_list_str or "없음"},
        )

    async def async_step_add_station(self, user_input: dict[str, Any] | None = None) -> dict[str, Any]:
        errors: dict[str, str] = {}
        if user_input is not None:
            keyword = user_input["keyword"]
            api_key = self.config_entry.data[CONF_API_KEY]
            try:
                session = async_get_clientsession(self.hass)
                api = HydrogenStationAPI(api_key=api_key)
                all_stations = await api._fetch_api_data(session, "operationinfo")
                
                current_mno_list = [s["mno"] for s in self.config_entry.options.get("stations", {}).values()]
                self.found_stations = {
                    s[KEY_CHRSTN_MNO]: s[KEY_CHRSTN_NM]
                    for s in all_stations
                    if keyword in s.get(KEY_CHRSTN_NM, "") and s[KEY_CHRSTN_MNO] not in current_mno_list
                }
                if not self.found_stations:
                    errors["base"] = "no_stations_found"
                else:
                    return await self.async_step_select_station()
            except Exception:
                _LOGGER.exception("Failed to find stations")
                errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="add_station", data_schema=vol.Schema({vol.Required("keyword"): str}), errors=errors
        )

    async def async_step_select_station(self, user_input: dict[str, Any] | None = None) -> dict[str, Any]:
        if user_input is not None:
            mno = user_input[CONF_STATION_MNO]
            name = self.found_stations[mno]
            
            new_options = self.config_entry.options.copy()
            stations = new_options.get("stations", {}).copy()
            stations[mno] = {"mno": mno, "name": name}
            new_options["stations"] = stations
            
            return self.async_create_entry(title="", data=new_options)

        return self.async_show_form(
            step_id="select_station",
            data_schema=vol.Schema({vol.Required(CONF_STATION_MNO): vol.In(self.found_stations)}),
        )

    async def async_step_remove_station(self, user_input: dict[str, Any] | None = None) -> dict[str, Any]:
        current_stations = self.config_entry.options.get("stations", {})
        if not current_stations:
            return self.async_abort(reason="no_stations_to_remove")
        
        if user_input is not None:
            mno_to_remove = user_input["station_to_remove"]
            
            new_options = self.config_entry.options.copy()
            stations = new_options.get("stations", {}).copy()
            if mno_to_remove in stations:
                del stations[mno_to_remove]
                new_options["stations"] = stations
            
            return self.async_create_entry(title="", data=new_options)
        
        station_choices = {mno: f"{s['name']} ({mno})" for mno, s in current_stations.items()}
        return self.async_show_form(
            step_id="remove_station",
            data_schema=vol.Schema({vol.Required("station_to_remove"): vol.In(station_choices)}),
        )