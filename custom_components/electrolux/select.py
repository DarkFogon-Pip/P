"""Select platform for Electrolux integration."""

import logging

from electrolux_group_developer_sdk.client.appliances.ap_appliance import APAppliance
from electrolux_group_developer_sdk.client.appliances.appliance_data import (
    ApplianceData,
)
from electrolux_group_developer_sdk.client.appliances.dw_appliance import DWAppliance
from electrolux_group_developer_sdk.client.appliances.ov_appliance import OVAppliance
from electrolux_group_developer_sdk.client.appliances.so_appliance import SOAppliance
from electrolux_group_developer_sdk.client.appliances.td_appliance import TDAppliance
from electrolux_group_developer_sdk.client.appliances.wd_appliance import WDAppliance
from electrolux_group_developer_sdk.client.appliances.wm_appliance import WMAppliance

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ElectroluxConfigEntry, ElectroluxDataUpdateCoordinator
from .entity import ElectroluxBaseEntity
from .entity_helper import async_setup_entities_helper
from .sensor import PROGRAM_MAP

_LOGGER = logging.getLogger(__name__)

# Appliance types that support program selection
PROGRAM_APPLIANCE_TYPES = (
    OVAppliance, SOAppliance, DWAppliance, WMAppliance, WDAppliance, TDAppliance,
)


def build_entities_for_appliance(
    appliance_data: ApplianceData,
    coordinators: dict[str, ElectroluxDataUpdateCoordinator],
) -> list[ElectroluxBaseEntity]:
    """Return select entities for an appliance."""
    appliance_id = appliance_data.appliance.applianceId
    coordinator = coordinators.get(appliance_id)
    if coordinator is None:
        return []

    entities: list[ElectroluxBaseEntity] = []

    if isinstance(appliance_data, SOAppliance):
        # SO ovens use per-cavity programs
        try:
            cavities = appliance_data.get_supported_cavities()
            for cavity in cavities:
                entities.append(
                    ElectroluxSOProgramSelect(appliance_data, coordinator, cavity)
                )
        except Exception:
            pass
    elif isinstance(appliance_data, PROGRAM_APPLIANCE_TYPES):
        entities.append(
            ElectroluxProgramSelect(appliance_data, coordinator)
        )

    if isinstance(appliance_data, APAppliance):
        entities.append(
            ElectroluxAirPurifierModeSelect(appliance_data, coordinator)
        )

    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElectroluxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up select entities."""
    await async_setup_entities_helper(
        hass, entry, async_add_entities, build_entities_for_appliance
    )


class ElectroluxProgramSelect(ElectroluxBaseEntity, SelectEntity):
    """Select entity for choosing appliance program."""

    _attr_translation_key = "program"
    _attr_icon = "mdi:format-list-bulleted"

    def __init__(
        self,
        appliance_data: ApplianceData,
        coordinator: ElectroluxDataUpdateCoordinator,
    ) -> None:
        """Initialize."""
        super().__init__(appliance_data, coordinator)
        self._attr_unique_id = (
            f"{appliance_data.appliance.applianceId}_program"
        )
        self._attr_name = "Program"

        try:
            programs = appliance_data.get_supported_programs() or []
            self._raw_programs = [str(p) for p in programs]
            # Build display→raw and raw→display mappings
            self._display_to_raw = {}
            self._raw_to_display = {}
            for raw in self._raw_programs:
                display = PROGRAM_MAP.get(raw, raw.replace("_", " ").title())
                self._display_to_raw[display] = raw
                self._raw_to_display[raw] = display
            self._attr_options = list(self._display_to_raw.keys())
        except Exception:
            self._raw_programs = []
            self._display_to_raw = {}
            self._raw_to_display = {}
            self._attr_options = []

        self._update_attr_state()

    def _update_attr_state(self) -> None:
        """Update current program."""
        try:
            current = self._appliance_data.get_current_program()
            if current:
                self._attr_current_option = self._raw_to_display.get(
                    str(current), str(current).replace("_", " ").title()
                )
            else:
                self._attr_current_option = None
        except Exception:
            self._attr_current_option = None

    async def async_select_option(self, option: str) -> None:
        """Select a program."""
        # Map display name back to raw enum value
        raw_option = self._display_to_raw.get(option, option)

        if isinstance(self._appliance_data, OVAppliance):
            command = self._appliance_data.get_program_command(raw_option)
        elif isinstance(self._appliance_data, (DWAppliance, WMAppliance, WDAppliance, TDAppliance)):
            command = self._appliance_data.get_set_program_command(raw_option)
        else:
            _LOGGER.warning("Program selection not supported for this appliance type")
            return

        await self.coordinator.client.send_command(self.appliance_id, command)
        await self.coordinator.async_request_refresh()


class ElectroluxAirPurifierModeSelect(ElectroluxBaseEntity, SelectEntity):
    """Select entity for air purifier mode."""

    _attr_translation_key = "mode"
    _attr_icon = "mdi:air-purifier"

    def __init__(
        self,
        appliance_data: APAppliance,
        coordinator: ElectroluxDataUpdateCoordinator,
    ) -> None:
        """Initialize."""
        super().__init__(appliance_data, coordinator)
        self._ap = appliance_data
        self._attr_unique_id = (
            f"{appliance_data.appliance.applianceId}_mode"
        )
        self._attr_name = "Mode"

        try:
            modes = appliance_data.get_supported_modes() or []
            self._attr_options = [str(m) for m in modes]
        except Exception:
            self._attr_options = []

        self._update_attr_state()

    def _update_attr_state(self) -> None:
        """Update current mode."""
        try:
            current = self._ap.get_current_mode()
            self._attr_current_option = str(current) if current else None
        except Exception:
            self._attr_current_option = None

    async def async_select_option(self, option: str) -> None:
        """Select a mode."""
        command = self._ap.get_mode_command(option)
        await self.coordinator.client.send_command(self.appliance_id, command)
        await self.coordinator.async_request_refresh()


class ElectroluxSOProgramSelect(ElectroluxBaseEntity, SelectEntity):
    """Select entity for SO oven per-cavity program."""

    _attr_translation_key = "program"
    _attr_icon = "mdi:chef-hat"

    def __init__(
        self,
        appliance_data: SOAppliance,
        coordinator: ElectroluxDataUpdateCoordinator,
        cavity: str,
    ) -> None:
        """Initialize."""
        super().__init__(appliance_data, coordinator)
        self._so = appliance_data
        self._cavity = cavity
        prefix = cavity.lower().replace(" ", "_")
        self._attr_unique_id = (
            f"{appliance_data.appliance.applianceId}_{prefix}_program"
        )
        self._attr_name = "Program"

        try:
            programs = appliance_data.get_cavity_supported_programs(cavity) or []
            self._raw_programs = [str(p) for p in programs]
            self._display_to_raw = {}
            self._raw_to_display = {}
            for raw in self._raw_programs:
                display = PROGRAM_MAP.get(raw, raw.replace("_", " ").title())
                self._display_to_raw[display] = raw
                self._raw_to_display[raw] = display
            self._attr_options = list(self._display_to_raw.keys())
        except Exception:
            self._raw_programs = []
            self._display_to_raw = {}
            self._raw_to_display = {}
            self._attr_options = []

        self._update_attr_state()

    def _update_attr_state(self) -> None:
        """Update current program."""
        try:
            current = self._so.get_current_cavity_program(self._cavity)
            if current:
                self._attr_current_option = self._raw_to_display.get(
                    str(current), str(current).replace("_", " ").title()
                )
            else:
                self._attr_current_option = None
        except Exception:
            self._attr_current_option = None

    async def async_select_option(self, option: str) -> None:
        """Select a program."""
        raw_option = self._display_to_raw.get(option, option)
        command = self._so.get_program_command(self._cavity, raw_option)
        await self.coordinator.client.send_command(self.appliance_id, command)
        await self.coordinator.async_request_refresh()
