"""Electrolux coordinator class."""

from __future__ import annotations

from asyncio import Task
from dataclasses import dataclass
import logging

from electrolux_group_developer_sdk.client.appliances.appliance_data import (
    ApplianceData,
)
from electrolux_group_developer_sdk.client.client_exception import (
    ApplianceClientException,
)
from electrolux_group_developer_sdk.client.dto.appliance_state import ApplianceState

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ElectroluxApiClient
from .const import DOMAIN

_LOGGER: logging.Logger = logging.getLogger(__name__)

# Delay to re-poll after time_to_end reaches 0 (Electrolux API bug workaround)
END_OF_CYCLE_REFRESH_DELAY = 70


@dataclass(kw_only=True, slots=True)
class ElectroluxData:
    """Electrolux runtime data."""

    client: ElectroluxApiClient
    appliances: list[ApplianceData]
    coordinators: dict[str, ElectroluxDataUpdateCoordinator]
    sse_task: Task


type ElectroluxConfigEntry = ConfigEntry[ElectroluxData]


class ElectroluxDataUpdateCoordinator(DataUpdateCoordinator[ApplianceState]):
    """Coordinator for fetching appliance data from the API."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ElectroluxConfigEntry,
        client: ElectroluxApiClient,
        appliance_id: str,
    ) -> None:
        """Initialize."""
        self.client = client
        self._appliance_id = appliance_id
        self._deferred_refresh_unsub = None
        self._last_time_to_end: int | None = None
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{config_entry.entry_id}_{appliance_id}",
            update_interval=None,
        )

    @property
    def appliance_id(self) -> str:
        """Return the appliance ID."""
        return self._appliance_id

    async def _async_update_data(self) -> ApplianceState:
        """Return the current appliance state."""
        try:
            return await self.client.fetch_appliance_state(self._appliance_id)
        except (ValueError, ApplianceClientException) as exception:
            raise UpdateFailed(exception) from exception

    def remove_listeners(self) -> None:
        """Remove all SSE listeners and cancel deferred refresh."""
        self.client.remove_all_listeners_by_appliance_id(self._appliance_id)
        if self._deferred_refresh_unsub:
            self._deferred_refresh_unsub()
            self._deferred_refresh_unsub = None

    def callback_handle_event(self, event: dict) -> None:
        """Handle an incoming SSE event."""
        current_state = self.data
        if not current_state:
            return

        updated_state = self._apply_sse_update(current_state, event)

        _LOGGER.debug(
            "SSE update for %s: %s = %s",
            self._appliance_id,
            event.get("property"),
            event.get("value"),
        )

        self.async_set_updated_data(updated_state)

        # Deferred end-of-cycle refresh workaround:
        # Electrolux does not send updated state after a cycle ends.
        # When timeToEnd drops to 0, schedule a full refresh after a delay.
        prop = event.get("property", "")
        if "timeToEnd" in prop or "TimeToEnd" in prop:
            value = event.get("value")
            try:
                time_val = int(value) if value is not None else None
            except (TypeError, ValueError):
                time_val = None

            prev = self._last_time_to_end
            if (
                time_val is not None
                and time_val <= 0
                and prev is not None
                and prev > 0
            ):
                self._schedule_deferred_refresh()
            self._last_time_to_end = time_val

    def _schedule_deferred_refresh(self) -> None:
        """Schedule a deferred full state refresh after end of cycle."""
        if self._deferred_refresh_unsub:
            self._deferred_refresh_unsub()

        async def _do_refresh(_now) -> None:
            _LOGGER.debug(
                "Deferred end-of-cycle refresh for %s", self._appliance_id
            )
            await self.async_request_refresh()

        self._deferred_refresh_unsub = async_call_later(
            self.hass, END_OF_CYCLE_REFRESH_DELAY, _do_refresh
        )

    def _apply_sse_update(
        self, state: ApplianceState, event: dict
    ) -> ApplianceState:
        """Apply an SSE property update into the appliance state."""
        state_dict = state.model_dump()

        prop = event.get("property")
        value = event.get("value")

        if prop is None:
            _LOGGER.warning("Received SSE event without 'property': %s", event)
            return state

        if prop in ("connectionState", "connectivityState"):
            state_dict["connectionState"] = value
        else:
            reported = state_dict.setdefault("properties", {}).setdefault(
                "reported", {}
            )
            path = prop.split("/")
            target = reported
            for key in path[:-1]:
                target = target.setdefault(key, {})
            target[path[-1]] = value

        return ApplianceState.model_validate(state_dict)
