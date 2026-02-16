"""Button platform for Electrolux integration."""

import logging

from electrolux_group_developer_sdk.client.appliances.appliance_data import (
    ApplianceData,
)
from electrolux_group_developer_sdk.client.appliances.dw_appliance import DWAppliance
from electrolux_group_developer_sdk.client.appliances.ov_appliance import OVAppliance
from electrolux_group_developer_sdk.client.appliances.rvc_appliance import RVCAppliance
from electrolux_group_developer_sdk.client.appliances.so_appliance import SOAppliance
from electrolux_group_developer_sdk.client.appliances.td_appliance import TDAppliance
from electrolux_group_developer_sdk.client.appliances.wd_appliance import WDAppliance
from electrolux_group_developer_sdk.client.appliances.wm_appliance import WMAppliance

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ElectroluxConfigEntry, ElectroluxDataUpdateCoordinator
from .entity import ElectroluxBaseEntity
from .entity_helper import async_setup_entities_helper

_LOGGER = logging.getLogger(__name__)

# Appliance types that support start/stop/pause/resume
CYCLE_APPLIANCE_TYPES = (
    OVAppliance, SOAppliance, DWAppliance, WMAppliance, WDAppliance, TDAppliance,
)


def build_entities_for_appliance(
    appliance_data: ApplianceData,
    coordinators: dict[str, ElectroluxDataUpdateCoordinator],
) -> list[ElectroluxBaseEntity]:
    """Return button entities for an appliance."""
    appliance_id = appliance_data.appliance.applianceId
    coordinator = coordinators.get(appliance_id)
    if coordinator is None:
        return []

    entities: list[ElectroluxBaseEntity] = []

    if isinstance(appliance_data, CYCLE_APPLIANCE_TYPES):
        entities.extend([
            ElectroluxCommandButton(
                appliance_data, coordinator, "start", "mdi:play",
                lambda a: a.get_start_command(),
            ),
            ElectroluxCommandButton(
                appliance_data, coordinator, "stop", "mdi:stop",
                lambda a: a.get_stop_command(),
            ),
        ])
        if isinstance(appliance_data, (DWAppliance, WMAppliance, WDAppliance, TDAppliance)):
            entities.extend([
                ElectroluxCommandButton(
                    appliance_data, coordinator, "pause", "mdi:pause",
                    lambda a: a.get_pause_command(),
                ),
                ElectroluxCommandButton(
                    appliance_data, coordinator, "resume", "mdi:play-pause",
                    lambda a: a.get_resume_command(),
                ),
            ])

    if isinstance(appliance_data, RVCAppliance):
        entities.extend([
            ElectroluxCommandButton(
                appliance_data, coordinator, "start", "mdi:play",
                lambda a: a.get_start_command(),
            ),
            ElectroluxCommandButton(
                appliance_data, coordinator, "stop", "mdi:stop",
                lambda a: a.get_stop_command(),
            ),
            ElectroluxCommandButton(
                appliance_data, coordinator, "pause", "mdi:pause",
                lambda a: a.get_pause_command(),
            ),
            ElectroluxCommandButton(
                appliance_data, coordinator, "dock", "mdi:home",
                lambda a: a.get_dock_command(),
            ),
        ])

    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElectroluxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up button entities."""
    await async_setup_entities_helper(
        hass, entry, async_add_entities, build_entities_for_appliance
    )


class ElectroluxCommandButton(ElectroluxBaseEntity, ButtonEntity):
    """Button entity that sends a command to an Electrolux appliance."""

    def __init__(
        self,
        appliance_data: ApplianceData,
        coordinator: ElectroluxDataUpdateCoordinator,
        command_name: str,
        icon: str,
        command_fn,
    ) -> None:
        """Initialize the button."""
        super().__init__(appliance_data, coordinator)
        self._command_fn = command_fn
        self._attr_unique_id = (
            f"{appliance_data.appliance.applianceId}_{command_name}"
        )
        self._attr_translation_key = command_name
        self._attr_icon = icon
        self._attr_name = command_name.replace("_", " ").title()

    def _update_attr_state(self) -> None:
        """No state to update for buttons."""

    async def async_press(self) -> None:
        """Handle button press."""
        command = self._command_fn(self._appliance_data)
        await self.coordinator.client.send_command(self.appliance_id, command)
        await self.coordinator.async_request_refresh()
