"""Config flow for Electrolux integration."""

import dataclasses
import logging
import re
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

from homeassistant.components import bluetooth
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_ADDRESS, CONF_API_KEY, CONF_MODEL
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow

from .const import (
    CONF_ENTRY_TYPE,
    CONF_REFRESH_TOKEN,
    DOMAIN,
    ENTRY_TYPE_CLOUD,
    ENTRY_TYPE_PROBE,
    PROBE_LOCAL_NAME_PREFIX,
    PROBE_MANUFACTURER_ID,
    USER_AGENT,
)

_LOGGER: logging.Logger = logging.getLogger(__name__)
_MAC_ADDRESS_RE = re.compile(r"^(?:[0-9A-F]{2}:){5}[0-9A-F]{2}$")

TOKEN_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
        vol.Required(CONF_ACCESS_TOKEN): str,
        vol.Required(CONF_REFRESH_TOKEN): str,
    }
)


@dataclasses.dataclass(frozen=True)
class ProbeDiscovery:
    """Represent a discovered standalone Electrolux probe."""

    title: str
    discovery_info: bluetooth.BluetoothServiceInfoBleak


def _probe_name(service_info: bluetooth.BluetoothServiceInfoBleak) -> str:
    """Return the best available probe name."""
    return service_info.name or service_info.device.name or "Electrolux probe"


def _probe_title(service_info: bluetooth.BluetoothServiceInfoBleak) -> str:
    """Return a user-facing title for a discovered probe."""
    return f"{_probe_name(service_info)} {service_info.address.upper()}"


def _probe_unique_id(address: str) -> str:
    """Build a unique id for a standalone probe entry."""
    return f"{ENTRY_TYPE_PROBE}:{address.upper()}"


def _normalize_probe_address(address: str) -> str:
    """Normalize a probe MAC address for storage."""
    return address.strip().replace("-", ":").upper()


def _is_probe_service_info(
    service_info: bluetooth.BluetoothServiceInfoBleak,
) -> bool:
    """Return True if the discovery looks like an Electrolux standalone probe."""
    manufacturer_data = getattr(service_info, "manufacturer_data", None)
    if manufacturer_data is None:
        manufacturer_data = service_info.advertisement.manufacturer_data

    return bool(
        _probe_name(service_info).startswith(PROBE_LOCAL_NAME_PREFIX)
        and PROBE_MANUFACTURER_ID in manufacturer_data
    )


class ElectroluxConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the Electrolux integration."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._discovered_probes: dict[str, ProbeDiscovery] = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow handler."""
        return ElectroluxOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user choose between account and standalone probe setup."""
        return self.async_show_menu(
            step_id="user", menu_options=["cloud_account", "probe"]
        )

    async def async_step_cloud_account(
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
                    title="Electrolux",
                    data={CONF_ENTRY_TYPE: ENTRY_TYPE_CLOUD, **user_input},
                )

        return self.async_show_form(
            step_id="cloud_account",
            data_schema=TOKEN_SCHEMA,
            errors=errors,
            description_placeholders={
                "portal_link": "https://developer.electrolux.one/generateToken"
            },
        )

    async def async_step_bluetooth(
        self, discovery_info: bluetooth.BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle bluetooth discovery for standalone probes."""
        if not _is_probe_service_info(discovery_info):
            return self.async_abort(reason="not_supported")

        address = discovery_info.address.upper()
        await self.async_set_unique_id(_probe_unique_id(address))
        self._abort_if_unique_id_configured()

        self._discovered_probes[address] = ProbeDiscovery(
            _probe_title(discovery_info), discovery_info
        )
        self.context["title_placeholders"] = {
            "name": self._discovered_probes[address].title
        }

        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm bluetooth discovery."""
        if user_input is not None:
            assert self.unique_id
            discovery = self._discovered_probes[self.unique_id.split(":", 1)[1]]
            return self.async_create_entry(
                title=discovery.title,
                data={
                    CONF_ENTRY_TYPE: ENTRY_TYPE_PROBE,
                    CONF_ADDRESS: discovery.discovery_info.address.upper(),
                    CONF_MODEL: _probe_name(discovery.discovery_info),
                },
            )

        assert self.unique_id
        address = self.unique_id.split(":", 1)[1]
        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={
                "name": self._discovered_probes[address].title
            },
        )

    async def async_step_probe(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manually add a nearby standalone probe."""
        configured_probe_addresses = {
            entry.data.get(CONF_ADDRESS, "").upper()
            for entry in self._async_current_entries()
            if entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_PROBE
        }

        if user_input is not None:
            address = _normalize_probe_address(user_input[CONF_ADDRESS])
            if not _MAC_ADDRESS_RE.match(address):
                return self.async_show_form(
                    step_id="probe",
                    data_schema=vol.Schema({vol.Required(CONF_ADDRESS): str}),
                    errors={"base": "invalid_address"},
                )

            await self.async_set_unique_id(_probe_unique_id(address))
            self._abort_if_unique_id_configured()
            discovery = self._discovered_probes.get(address)
            return self.async_create_entry(
                title=discovery.title if discovery else f"Electrolux probe {address}",
                data={
                    CONF_ENTRY_TYPE: ENTRY_TYPE_PROBE,
                    CONF_ADDRESS: address,
                    CONF_MODEL: (
                        _probe_name(discovery.discovery_info)
                        if discovery
                        else "Electrolux probe"
                    ),
                },
            )

        for discovery_info in bluetooth.async_discovered_service_info(self.hass):
            if not _is_probe_service_info(discovery_info):
                continue

            address = discovery_info.address.upper()
            if (
                address in configured_probe_addresses
                or address in self._discovered_probes
            ):
                continue

            self._discovered_probes[address] = ProbeDiscovery(
                _probe_title(discovery_info), discovery_info
            )

        if not self._discovered_probes:
            return self.async_show_form(
                step_id="probe",
                data_schema=vol.Schema({vol.Required(CONF_ADDRESS): str}),
                description_placeholders={"mode": "enter the probe MAC address"},
            )

        titles = {
            address: discovery.title
            for address, discovery in self._discovered_probes.items()
        }
        return self.async_show_form(
            step_id="probe",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): vol.In(titles)}),
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
