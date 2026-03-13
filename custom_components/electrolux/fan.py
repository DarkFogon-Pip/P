"""Fan platform for Electrolux integration."""

import logging
from typing import Any

from electrolux_group_developer_sdk.client.appliances.ap_appliance import APAppliance
from electrolux_group_developer_sdk.client.appliances.appliance_data import (
    ApplianceData,
)

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .coordinator import ElectroluxConfigEntry, ElectroluxDataUpdateCoordinator
from .entity import ElectroluxBaseEntity
from .entity_helper import async_setup_entities_helper

_LOGGER = logging.getLogger(__name__)


def build_entities_for_appliance(
    appliance_data: ApplianceData,
    coordinators: dict[str, ElectroluxDataUpdateCoordinator],
) -> list[ElectroluxBaseEntity]:
    """Return fan entities for an appliance."""
    appliance_id = appliance_data.appliance.applianceId
    coordinator = coordinators.get(appliance_id)
    if coordinator is None:
        return []

    entities: list[ElectroluxBaseEntity] = []

    if isinstance(appliance_data, APAppliance):
        entities.append(
            ElectroluxAirPurifierFan(appliance_data, coordinator)
        )

    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElectroluxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up fan entities."""
    await async_setup_entities_helper(
        hass, entry, async_add_entities, build_entities_for_appliance
    )


class ElectroluxAirPurifierFan(ElectroluxBaseEntity, FanEntity):
    """Fan entity for Electrolux air purifiers."""

    _attr_translation_key = "air_purifier"
    _enable_turn_on_off_backwards_compat = False

    def __init__(
        self,
        appliance_data: APAppliance,
        coordinator: ElectroluxDataUpdateCoordinator,
    ) -> None:
        """Initialize the air purifier fan."""
        super().__init__(appliance_data, coordinator)
        self._ap = appliance_data
        self._attr_unique_id = (
            f"{appliance_data.appliance.applianceId}_fan"
        )

        self._attr_supported_features = (
            FanEntityFeature.SET_SPEED
            | FanEntityFeature.PRESET_MODE
            | FanEntityFeature.TURN_ON
            | FanEntityFeature.TURN_OFF
        )

        # Build speed list from min to max
        try:
            min_speed = int(appliance_data.get_supported_min_fan_speed() or 1)
            max_speed = int(appliance_data.get_supported_max_fan_speed() or 9)
        except (TypeError, ValueError):
            min_speed = 1
            max_speed = 9
        self._speed_list = [str(s) for s in range(min_speed, max_speed + 1)]
        self._attr_speed_count = len(self._speed_list)

        # Preset modes from supported modes
        try:
            modes = appliance_data.get_supported_modes() or []
            self._attr_preset_modes = [str(m) for m in modes]
        except Exception:
            self._attr_preset_modes = []

        self._update_attr_state()

    def _update_attr_state(self) -> None:
        """Update fan state."""
        try:
            self._attr_is_on = self._ap.is_appliance_on()
        except Exception:
            self._attr_is_on = None

        try:
            current_speed = self._ap.get_current_fan_speed()
            if current_speed is not None and str(current_speed) in self._speed_list:
                self._attr_percentage = ordered_list_item_to_percentage(
                    self._speed_list, str(current_speed)
                )
            else:
                self._attr_percentage = None
        except Exception:
            self._attr_percentage = None

        try:
            current_mode = self._ap.get_current_mode()
            self._attr_preset_mode = str(current_mode) if current_mode else None
        except Exception:
            self._attr_preset_mode = None

    async def async_set_percentage(self, percentage: int) -> None:
        """Set fan speed percentage."""
        if percentage == 0:
            await self.async_turn_off()
            return

        speed = percentage_to_ordered_list_item(self._speed_list, percentage)
        command = self._ap.get_fan_speed_command(int(speed))
        await self.coordinator.client.send_command(self.appliance_id, command)
        await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode."""
        command = self._ap.get_mode_command(preset_mode)
        await self.coordinator.client.send_command(self.appliance_id, command)
        await self.coordinator.async_request_refresh()

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        if preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)
        elif percentage is not None:
            await self.async_set_percentage(percentage)
        else:
            command = self._ap.get_turn_on_command()
            await self.coordinator.client.send_command(
                self.appliance_id, command
            )
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        command = self._ap.get_turn_off_command()
        await self.coordinator.client.send_command(self.appliance_id, command)
        await self.coordinator.async_request_refresh()
