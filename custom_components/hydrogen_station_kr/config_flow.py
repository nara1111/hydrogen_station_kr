import logging
from typing import Any
import asyncio
import aiohttp
import unicodedata

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    CONF_STATION_NAME,
    CONF_ID_TYPE,
    ID_TYPE_NAME,
    ID_TYPE_MNO,
)
from .api import HydrogenStationAPI

_LOGGER = logging.getLogger(__name__)


class HydrogenStationKRConfigFlow(ConfigFlow, domain=DOMAIN):
    """Hydrogen Station KR config flow."""

    VERSION = 1
    _id_type: str

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._id_type = user_input[CONF_ID_TYPE]
            if self._id_type == ID_TYPE_NAME:
                return await self.async_step_by_name()
            return await self.async_step_by_mno()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_ID_TYPE, default=ID_TYPE_NAME): vol.In([ID_TYPE_NAME, ID_TYPE_MNO])}
            ),
        )

    async def async_step_by_name(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return await self._validate_and_create_entry(
                ID_TYPE_NAME, user_input[CONF_STATION_NAME], user_input[CONF_API_KEY]
            )
        return self.async_show_form(
            step_id="by_name",
            data_schema=vol.Schema({vol.Required(CONF_STATION_NAME): str, vol.Required(CONF_API_KEY): str}),
        )

    async def async_step_by_mno(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return await self._validate_and_create_entry(
                ID_TYPE_MNO, user_input["station_mno"], user_input[CONF_API_KEY]
            )
        return self.async_show_form(
            step_id="by_mno",
            data_schema=vol.Schema({vol.Required("station_mno"): str, vol.Required(CONF_API_KEY): str}),
        )

    async def _validate_and_create_entry(
        self, id_type: str, identifier: str, api_key: str
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        try:
            session = async_get_clientsession(self.hass)
            api = HydrogenStationAPI(station_name="", api_key=api_key)
            
            # 유니코드 정규화를 적용하여 충전소 데이터 검색
            station_data = await api.async_find_station_by_identifier(session, id_type, identifier)

            if not station_data:
                raise ValueError("Station not found")

            final_station_name = station_data["chrstn_nm"]
            final_station_mno = station_data["chrstn_mno"]

            await self.async_set_unique_id(final_station_mno)
            self._abort_if_unique_id_configured()
            
            return self.async_create_entry(
                title=final_station_name,
                data={CONF_STATION_NAME: final_station_name, CONF_API_KEY: api_key},
            )
        
        except (aiohttp.ClientError, asyncio.TimeoutError):
            errors["base"] = "cannot_connect"
        except ValueError:
            errors["base"] = "invalid_station"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        
        step_id_to_retry = "by_name" if id_type == ID_TYPE_NAME else "by_mno"
        
        if id_type == ID_TYPE_NAME:
            schema = vol.Schema({
                vol.Required(CONF_STATION_NAME, default=identifier): str,
                vol.Required(CONF_API_KEY, default=api_key): str,
            })
        else:
            schema = vol.Schema({
                vol.Required("station_mno", default=identifier): str,
                vol.Required(CONF_API_KEY, default=api_key): str,
            })
            
        return self.async_show_form(
            step_id=step_id_to_retry, data_schema=schema, errors=errors
        )