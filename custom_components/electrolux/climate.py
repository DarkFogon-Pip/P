"""Climate platform for Electrolux integration."""

import logging
from typing import Any

from electrolux_group_developer_sdk.client.appliances.ac_appliance import ACAppliance
from electrolux_group_developer_sdk.client.appliances.appliance_data import (
    ApplianceData,
)
from electrolux_group_developer_sdk.client.appliances.dam_ac_appliance import (
    DAMACAppliance,
)
from electrolux_group_developer_sdk.client.appliances.dh_appliance import DHAppliance

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ElectroluxConfigEntry, ElectroluxDataUpdateCoordinator
from .entity import ElectroluxBaseEntity
from .entity_helper import async_setup_entities_helper

_LOGGER = logging.getLogger(__name__)

# Electrolux mode -> HA HVAC mode mapping
ELECTROLUX_TO_HA_HVAC: dict[str, HVACMode] = {
    "OFF": HVACMode.OFF,
    "COOL": HVACMode.COOL,
    "HEAT": HVACMode.HEAT,
    "AUTO": HVACMode.AUTO,
    "DRY": HVACMode.DRY,
    "FAN": HVACMode.FAN_ONLY,
    "FANONLY": HVACMode.FAN_ONLY,
    "FAN_ONLY": HVACMode.FAN_ONLY,
}

HA_TO_ELECTROLUX_HVAC: dict[HVACMode, str] = {
    HVACMode.OFF: "OFF",
    HVACMode.COOL: "COOL",
    HVACMode.HEAT: "HEAT",
    HVACMode.AUTO: "AUTO",
    HVACMode.DRY: "DRY",
    HVACMode.FAN_ONLY: "FANONLY",
}

# Electrolux fan speed -> HA fan mode mapping
ELECTROLUX_TO_HA_FAN: dict[str, str] = {
    "AUTO": "auto",
    "LOW": "low",
    "MIDDLE": "medium",
    "HIGH": "high",
}

HA_TO_ELECTROLUX_FAN: dict[str, str] = {
    "auto": "AUTO",
    "low": "LOW",
    "medium": "MIDDLE",
    "high": "HIGH",
}


def build_entities_for_appliance(
    appliance_data: ApplianceData,
    coordinators: dict[str, ElectroluxDataUpdateCoordinator],
) -> list[ElectroluxBaseEntity]:
    """Return climate entities for an appliance."""
    appliance_id = appliance_data.appliance.applianceId
    coordinator = coordinators.get(appliance_id)
    if coordinator is None:
        return []

    entities: list[ElectroluxBaseEntity] = []

    if isinstance(appliance_data, (ACAppliance, DAMACAppliance)):
        entities.append(
            ElectroluxACClimate(appliance_data, coordinator)
        )
    elif isinstance(appliance_data, DHAppliance):
        entities.append(
            ElectroluxDehumidifierClimate(appliance_data, coordinator)
        )

    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElectroluxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up climate entities."""
    await async_setup_entities_helper(
        hass, entry, async_add_entities, build_entities_for_appliance
    )


class ElectroluxACClimate(ElectroluxBaseEntity, ClimateEntity):
    """Climate entity for Electrolux air conditioners."""

    _attr_translation_key = "air_conditioner"
    _enable_turn_on_off_backwards_compat = False

    def __init__(
        self,
        appliance_data: ACAppliance | DAMACAppliance,
        coordinator: ElectroluxDataUpdateCoordinator,
    ) -> None:
        """Initialize AC climate entity."""
        super().__init__(appliance_data, coordinator)
        self._ac = appliance_data
        self._attr_unique_id = f"{appliance_data.appliance.applianceId}_climate"

        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )

        # Determine temperature unit
        temp_unit = self._ac.get_current_temperature_unit()
        if temp_unit and temp_unit.upper() == "FAHRENHEIT":
            self._attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
        else:
            self._attr_temperature_unit = UnitOfTemperature.CELSIUS

        # Temperature range
        self._attr_min_temp = self._ac.get_supported_min_temp() or 16
        self._attr_max_temp = self._ac.get_supported_max_temp() or 32
        self._attr_target_temperature_step = (
            self._ac.get_supported_step_temp() or 1
        )

        # HVAC modes
        supported_modes = self._ac.get_supported_modes() or []
        self._attr_hvac_modes = [HVACMode.OFF]
        for mode in supported_modes:
            ha_mode = ELECTROLUX_TO_HA_HVAC.get(mode.upper())
            if ha_mode and ha_mode not in self._attr_hvac_modes:
                self._attr_hvac_modes.append(ha_mode)

        # Fan modes
        supported_fans = self._ac.get_supported_fan_speeds() or []
        self._attr_fan_modes = []
        for fan in supported_fans:
            ha_fan = ELECTROLUX_TO_HA_FAN.get(fan.upper(), fan.lower())
            if ha_fan not in self._attr_fan_modes:
                self._attr_fan_modes.append(ha_fan)

        self._update_attr_state()

    def _update_attr_state(self) -> None:
        """Update climate attributes from appliance state."""
        # HVAC mode
        current_mode = self._ac.get_current_mode()
        appliance_state = self._ac.get_current_appliance_state()

        if appliance_state and appliance_state.upper() == "OFF":
            self._attr_hvac_mode = HVACMode.OFF
        elif current_mode:
            self._attr_hvac_mode = ELECTROLUX_TO_HA_HVAC.get(
                current_mode.upper(), HVACMode.AUTO
            )
        else:
            self._attr_hvac_mode = HVACMode.OFF

        # Target temperature
        if self._attr_temperature_unit == UnitOfTemperature.FAHRENHEIT:
            self._attr_target_temperature = (
                self._ac.get_current_target_temperature_f()
            )
        else:
            self._attr_target_temperature = (
                self._ac.get_current_target_temperature_c()
            )

        # Current temperature (ambient)
        if self._attr_temperature_unit == UnitOfTemperature.FAHRENHEIT:
            self._attr_current_temperature = (
                self._ac.get_current_ambient_temperature_f()
            )
        else:
            self._attr_current_temperature = (
                self._ac.get_current_ambient_temperature_c()
            )

        # Fan mode
        current_fan = self._ac.get_current_fan_speed()
        if current_fan:
            self._attr_fan_mode = ELECTROLUX_TO_HA_FAN.get(
                current_fan.upper(), current_fan.lower()
            )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        if hvac_mode == HVACMode.OFF:
            command = self._ac.get_turn_off_command()
        else:
            elx_mode = HA_TO_ELECTROLUX_HVAC.get(hvac_mode)
            if elx_mode is None:
                _LOGGER.warning("Unsupported HVAC mode: %s", hvac_mode)
                return
            command = self._ac.get_mode_command(elx_mode)

        await self.coordinator.client.send_command(self.appliance_id, command)
        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        if self._attr_temperature_unit == UnitOfTemperature.FAHRENHEIT:
            command = self._ac.get_temperature_f_command(int(temperature))
        else:
            command = self._ac.get_temperature_c_command(int(temperature))

        await self.coordinator.client.send_command(self.appliance_id, command)
        await self.coordinator.async_request_refresh()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode."""
        elx_fan = HA_TO_ELECTROLUX_FAN.get(fan_mode, fan_mode.upper())
        command = self._ac.get_fan_speed_command(elx_fan)
        await self.coordinator.client.send_command(self.appliance_id, command)
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        """Turn the AC on."""
        command = self._ac.get_turn_on_command()
        await self.coordinator.client.send_command(self.appliance_id, command)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        """Turn the AC off."""
        command = self._ac.get_turn_off_command()
        await self.coordinator.client.send_command(self.appliance_id, command)
        await self.coordinator.async_request_refresh()


class ElectroluxDehumidifierClimate(ElectroluxBaseEntity, ClimateEntity):
    """Climate entity for Electrolux dehumidifiers."""

    _attr_translation_key = "dehumidifier"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _enable_turn_on_off_backwards_compat = False

    def __init__(
        self,
        appliance_data: DHAppliance,
        coordinator: ElectroluxDataUpdateCoordinator,
    ) -> None:
        """Initialize dehumidifier climate entity."""
        super().__init__(appliance_data, coordinator)
        self._dh = appliance_data
        self._attr_unique_id = f"{appliance_data.appliance.applianceId}_climate"

        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_HUMIDITY
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )

        self._attr_hvac_modes = [HVACMode.OFF, HVACMode.DRY]

        # Humidity range
        self._attr_min_humidity = self._dh.get_supported_min_humidity() or 30
        self._attr_max_humidity = self._dh.get_supported_max_humidity() or 80

        # Fan modes
        supported_fans = self._dh.get_supported_fan_speeds() or []
        self._attr_fan_modes = [f.lower() for f in supported_fans]

        self._update_attr_state()

    def _update_attr_state(self) -> None:
        """Update climate attributes from appliance state."""
        if self._dh.is_appliance_on():
            self._attr_hvac_mode = HVACMode.DRY
        else:
            self._attr_hvac_mode = HVACMode.OFF

        self._attr_target_humidity = self._dh.get_current_target_humidity()
        self._attr_current_humidity = self._dh.get_current_sensor_humidity()

        current_fan = self._dh.get_current_fan_speed()
        if current_fan:
            self._attr_fan_mode = current_fan.lower()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        if hvac_mode == HVACMode.OFF:
            command = self._dh.get_turn_off_command()
        else:
            command = self._dh.get_turn_on_command()

        await self.coordinator.client.send_command(self.appliance_id, command)
        await self.coordinator.async_request_refresh()

    async def async_set_humidity(self, humidity: int) -> None:
        """Set target humidity."""
        command = self._dh.get_humidity_command(humidity)
        await self.coordinator.client.send_command(self.appliance_id, command)
        await self.coordinator.async_request_refresh()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode."""
        command = self._dh.get_fan_speed_command(fan_mode.upper())
        await self.coordinator.client.send_command(self.appliance_id, command)
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        """Turn on."""
        command = self._dh.get_turn_on_command()
        await self.coordinator.client.send_command(self.appliance_id, command)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        """Turn off."""
        command = self._dh.get_turn_off_command()
        await self.coordinator.client.send_command(self.appliance_id, command)
        await self.coordinator.async_request_refresh()
