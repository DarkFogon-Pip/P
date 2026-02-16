"""Switch platform for Electrolux integration."""

import logging
from typing import Any

from electrolux_group_developer_sdk.client.appliances.ap_appliance import APAppliance
from electrolux_group_developer_sdk.client.appliances.appliance_data import (
    ApplianceData,
)
from electrolux_group_developer_sdk.client.appliances.cr_appliance import CRAppliance
from electrolux_group_developer_sdk.client.appliances.hb_appliance import HBAppliance
from electrolux_group_developer_sdk.client.appliances.ov_appliance import OVAppliance
from electrolux_group_developer_sdk.client.appliances.so_appliance import SOAppliance

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ElectroluxConfigEntry, ElectroluxDataUpdateCoordinator
from .entity import ElectroluxBaseEntity
from .entity_helper import async_setup_entities_helper

_LOGGER = logging.getLogger(__name__)


def build_entities_for_appliance(
    appliance_data: ApplianceData,
    coordinators: dict[str, ElectroluxDataUpdateCoordinator],
) -> list[ElectroluxBaseEntity]:
    """Return switch entities for an appliance."""
    appliance_id = appliance_data.appliance.applianceId
    coordinator = coordinators.get(appliance_id)
    if coordinator is None:
        return []

    entities: list[ElectroluxBaseEntity] = []

    # Oven cavity light
    if isinstance(appliance_data, (OVAppliance, SOAppliance)):
        entities.append(
            ElectroluxCavityLightSwitch(appliance_data, coordinator)
        )

    # Air purifier power
    if isinstance(appliance_data, APAppliance):
        entities.append(
            ElectroluxAirPurifierPowerSwitch(appliance_data, coordinator)
        )

    # Hob child lock
    if isinstance(appliance_data, HBAppliance):
        entities.append(
            ElectroluxChildLockSwitch(appliance_data, coordinator)
        )

    # Refrigerator vacation mode
    if isinstance(appliance_data, CRAppliance):
        entities.append(
            ElectroluxVacationModeSwitch(appliance_data, coordinator)
        )

    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElectroluxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switch entities."""
    await async_setup_entities_helper(
        hass, entry, async_add_entities, build_entities_for_appliance
    )


class ElectroluxCavityLightSwitch(ElectroluxBaseEntity, SwitchEntity):
    """Switch for oven cavity light."""

    _attr_translation_key = "cavity_light"
    _attr_icon = "mdi:lightbulb"

    def __init__(
        self,
        appliance_data: OVAppliance | SOAppliance,
        coordinator: ElectroluxDataUpdateCoordinator,
    ) -> None:
        """Initialize."""
        super().__init__(appliance_data, coordinator)
        self._ov = appliance_data
        self._attr_unique_id = (
            f"{appliance_data.appliance.applianceId}_cavity_light"
        )
        self._attr_name = "Cavity light"
        self._update_attr_state()

    def _update_attr_state(self) -> None:
        """Update state."""
        try:
            light = self._ov.get_current_cavity_light()
            self._attr_is_on = light is not None and str(light).upper() in (
                "ON", "TRUE", "1",
            )
        except Exception:
            self._attr_is_on = None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on cavity light."""
        command = self._ov.get_cavity_light_command(True)
        await self.coordinator.client.send_command(self.appliance_id, command)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off cavity light."""
        command = self._ov.get_cavity_light_command(False)
        await self.coordinator.client.send_command(self.appliance_id, command)
        await self.coordinator.async_request_refresh()


class ElectroluxAirPurifierPowerSwitch(ElectroluxBaseEntity, SwitchEntity):
    """Power switch for air purifier."""

    _attr_translation_key = "power"
    _attr_icon = "mdi:power"

    def __init__(
        self,
        appliance_data: APAppliance,
        coordinator: ElectroluxDataUpdateCoordinator,
    ) -> None:
        """Initialize."""
        super().__init__(appliance_data, coordinator)
        self._ap = appliance_data
        self._attr_unique_id = (
            f"{appliance_data.appliance.applianceId}_power"
        )
        self._attr_name = "Power"
        self._update_attr_state()

    def _update_attr_state(self) -> None:
        """Update state."""
        try:
            self._attr_is_on = self._ap.is_appliance_on()
        except Exception:
            self._attr_is_on = None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on."""
        command = self._ap.get_turn_on_command()
        await self.coordinator.client.send_command(self.appliance_id, command)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off."""
        command = self._ap.get_turn_off_command()
        await self.coordinator.client.send_command(self.appliance_id, command)
        await self.coordinator.async_request_refresh()


class ElectroluxChildLockSwitch(ElectroluxBaseEntity, SwitchEntity):
    """Switch for hob child lock."""

    _attr_translation_key = "child_lock"
    _attr_icon = "mdi:lock"

    def __init__(
        self,
        appliance_data: HBAppliance,
        coordinator: ElectroluxDataUpdateCoordinator,
    ) -> None:
        """Initialize."""
        super().__init__(appliance_data, coordinator)
        self._hb = appliance_data
        self._attr_unique_id = (
            f"{appliance_data.appliance.applianceId}_child_lock"
        )
        self._attr_name = "Child lock"
        self._update_attr_state()

    def _update_attr_state(self) -> None:
        """Update state."""
        try:
            lock = self._hb.get_current_child_lock()
            self._attr_is_on = lock is not None and str(lock).upper() in (
                "ON", "TRUE", "1", "ENABLED",
            )
        except Exception:
            self._attr_is_on = None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable child lock."""
        command = self._hb.get_enable_child_lock_command()
        await self.coordinator.client.send_command(self.appliance_id, command)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable child lock - not supported by SDK, only enable."""
        _LOGGER.warning("Child lock can only be enabled remotely")


class ElectroluxVacationModeSwitch(ElectroluxBaseEntity, SwitchEntity):
    """Switch for refrigerator vacation/holiday mode."""

    _attr_translation_key = "vacation_mode"
    _attr_icon = "mdi:palm-tree"

    def __init__(
        self,
        appliance_data: CRAppliance,
        coordinator: ElectroluxDataUpdateCoordinator,
    ) -> None:
        """Initialize."""
        super().__init__(appliance_data, coordinator)
        self._cr = appliance_data
        self._attr_unique_id = (
            f"{appliance_data.appliance.applianceId}_vacation_mode"
        )
        self._attr_name = "Vacation mode"
        self._update_attr_state()

    def _update_attr_state(self) -> None:
        """Update state."""
        try:
            mode = self._cr.get_current_vacation_holiday_mode()
            self._attr_is_on = mode is not None and str(mode).upper() in (
                "ON", "TRUE", "1", "ENABLED",
            )
        except Exception:
            self._attr_is_on = None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable vacation mode."""
        command = self._cr.get_set_vacation_holiday_mode_command(True)
        await self.coordinator.client.send_command(self.appliance_id, command)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable vacation mode."""
        command = self._cr.get_set_vacation_holiday_mode_command(False)
        await self.coordinator.client.send_command(self.appliance_id, command)
        await self.coordinator.async_request_refresh()
