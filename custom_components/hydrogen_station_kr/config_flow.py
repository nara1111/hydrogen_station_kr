# config_flow.py (최종 효율화 버전)

import logging
from typing import Any
import asyncio
import aiohttp

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    CONF_STATION_NAME,
    CONF_API_KEY,
    CONF_ID_TYPE,
    CONF_SEARCH_KEYWORD,
    CONF_STATION_MNO,
    ID_TYPE_KEYWORD,
    ID_TYPE_MNO,
)
from .api import HydrogenStationAPI

_LOGGER = logging.getLogger(__name__)


class HydrogenStationKRConfigFlow(ConfigFlow, domain=DOMAIN):
    """Hydrogen Station KR config flow."""

    VERSION = 1
    
    def __init__(self):
        """Initialize the config flow."""
        self.api_key: str | None = None
        self.found_stations: dict[str, str] = {} # {이름: 관리번호}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1: Ask the user to choose the registration method."""
        if user_input is not None:
            id_type = user_input[CONF_ID_TYPE]
            if id_type == ID_TYPE_KEYWORD:
                return await self.async_step_search()
            elif id_type == ID_TYPE_MNO:
                return await self.async_step_mno()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_ID_TYPE, default=ID_TYPE_KEYWORD): vol.In({
                    ID_TYPE_KEYWORD: "키워드로 검색하여 등록",
                    ID_TYPE_MNO: "관리번호로 직접 등록"
                })
            }),
        )

    async def async_step_search(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the flow for searching by keyword."""
        errors: dict[str, str] = {}
        if user_input is not None:
            keyword = user_input[CONF_SEARCH_KEYWORD]
            self.api_key = user_input[CONF_API_KEY]
            
            try:
                session = async_get_clientsession(self.hass)
                api = HydrogenStationAPI(station_name="", api_key=self.api_key)
                all_stations = await api._fetch_api_data(session, "operationinfo")
                if not all_stations:
                    raise ConnectionError("Failed to fetch station list.")

                self.found_stations = {
                    s["chrstn_nm"]: s["chrstn_mno"]
                    for s in all_stations if keyword in s.get("chrstn_nm", "")
                }
                
                if not self.found_stations:
                    errors["base"] = "no_stations_found"
                elif len(self.found_stations) == 1:
                    station_name = list(self.found_stations.keys())[0]
                    station_mno = self.found_stations[station_name]
                    return await self._create_entry(station_name, station_mно, self.api_key)
                else:
                    return await self.async_step_select()

            except (aiohttp.ClientError, asyncio.TimeoutError, ConnectionError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="search",
            data_schema=vol.Schema({
                vol.Required(CONF_SEARCH_KEYWORD): str,
                vol.Required(CONF_API_KEY): str,
            }),
            errors=errors,
        )

    async def async_step_select(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the flow for selecting from multiple search results."""
        if user_input is not None:
            station_name = user_input[CONF_STATION_NAME]
            station_mno = self.found_stations[station_name]
            return await self._create_entry(station_name, station_mno, self.api_key)
            
        return self.async_show_form(
            step_id="select",
            data_schema=vol.Schema(
                {vol.Required(CONF_STATION_NAME): vol.In(list(self.found_stations.keys()))}
            ),
        )

    async def async_step_mno(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the flow for direct registration by MNO."""
        errors: dict[str, str] = {}
        if user_input is not None:
            mno = user_input[CONF_STATION_MNO]
            api_key = user_input[CONF_API_KEY]
            try:
                session = async_get_clientsession(self.hass)
                api = HydrogenStationAPI(station_name="", api_key=api_key)
                station_data = await api.async_find_station_by_identifier(session, "mno", mno)

                if not station_data:
                    raise ValueError("Station not found")
                
                station_name = station_data["chrstn_nm"]
                return await self._create_entry(station_name, mno, api_key)
                
            except (aiohttp.ClientError, asyncio.TimeoutError):
                errors["base"] = "cannot_connect"
            except ValueError:
                errors["base"] = "invalid_station"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="mno",
            data_schema=vol.Schema({
                vol.Required(CONF_STATION_MNO): str,
                vol.Required(CONF_API_KEY): str,
            }),
            errors=errors,
        )

    # --- 수정된 부분: 불필요한 API 재호출 제거 ---
    async def _create_entry(self, station_name: str, station_mno: str, api_key: str) -> ConfigFlowResult:
        """Create the config entry after validation."""
        await self.async_set_unique_id(station_mno)
        self._abort_if_unique_id_configured()
        
        return self.async_create_entry(
            title=station_name,
            data={CONF_STATION_NAME: station_name, CONF_API_KEY: api_key},
        )
    # --- 수정 끝 ---