"""Config flow for Electrolux integration."""

import logging
from collections.abc import Mapping
from typing import Any

from electrolux_group_developer_sdk.auth.invalid_credentials_exception import (
    InvalidCredentialsException,
)
from electrolux_group_developer_sdk.auth.token_manager import TokenManager
from electrolux_group_developer_sdk.client.appliance_client import ApplianceClient
from electrolux_group_developer_sdk.client.failed_connection_exception import (
    FailedConnectionException,
)
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_API_KEY
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow

from .const import CONF_REFRESH_TOKEN, DOMAIN, USER_AGENT

_LOGGER: logging.Logger = logging.getLogger(__name__)

TOKEN_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
        vol.Required(CONF_ACCESS_TOKEN): str,
        vol.Required(CONF_REFRESH_TOKEN): str,
    }
)


class ElectroluxConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the Electrolux integration."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow handler."""
        return ElectroluxOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                token_manager = await self._authenticate_user(user_input)
            except AbortFlow:
                raise
            except InvalidCredentialsException:
                errors["base"] = "invalid_auth"
            except FailedConnectionException:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during authentication")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(token_manager.get_user_id())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Electrolux", data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=TOKEN_SCHEMA,
            errors=errors,
            description_placeholders={
                "portal_link": "https://developer.electrolux.one/generateToken"
            },
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication when tokens expire."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthentication confirmation."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await self._authenticate_user(user_input)
            except InvalidCredentialsException:
                errors["base"] = "invalid_auth"
            except FailedConnectionException:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during reauthentication")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates=user_input,
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=TOKEN_SCHEMA,
            errors=errors,
            description_placeholders={
                "portal_link": "https://developer.electrolux.one/generateToken"
            },
        )

    async def _authenticate_user(
        self, user_input: dict[str, Any]
    ) -> TokenManager:
        """Validate credentials by testing the connection."""
        token_manager = TokenManager(
            access_token=user_input[CONF_ACCESS_TOKEN],
            refresh_token=user_input[CONF_REFRESH_TOKEN],
            api_key=user_input[CONF_API_KEY],
        )
        token_manager.ensure_credentials()

        client = ApplianceClient(
            token_manager=token_manager, external_user_agent=USER_AGENT
        )
        await client.test_connection()

        return token_manager


class ElectroluxOptionsFlow(OptionsFlow):
    """Options flow for updating Electrolux credentials."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options flow."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                token_manager = TokenManager(
                    access_token=user_input[CONF_ACCESS_TOKEN],
                    refresh_token=user_input[CONF_REFRESH_TOKEN],
                    api_key=user_input[CONF_API_KEY],
                )
                token_manager.ensure_credentials()
                client = ApplianceClient(
                    token_manager=token_manager, external_user_agent=USER_AGENT
                )
                await client.test_connection()
            except (InvalidCredentialsException, FailedConnectionException):
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected error updating credentials")
                errors["base"] = "unknown"
            else:
                self.hass.config_entries.async_update_entry(
                    self._config_entry,
                    data={**self._config_entry.data, **user_input},
                )
                return self.async_create_entry(data={})

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_API_KEY,
                        default=self._config_entry.data.get(CONF_API_KEY, ""),
                    ): str,
                    vol.Required(CONF_ACCESS_TOKEN): str,
                    vol.Required(CONF_REFRESH_TOKEN): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "portal_link": "https://developer.electrolux.one/generateToken"
            },
        )
