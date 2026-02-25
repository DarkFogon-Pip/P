"""Number platform for Electrolux integration."""

import logging

from electrolux_group_developer_sdk.client.appliances.ap_appliance import APAppliance
from electrolux_group_developer_sdk.client.appliances.appliance_data import (
    ApplianceData,
)
from electrolux_group_developer_sdk.client.appliances.cr_appliance import CRAppliance
from electrolux_group_developer_sdk.client.appliances.hd_appliance import HDAppliance
from electrolux_group_developer_sdk.client.appliances.ov_appliance import OVAppliance
from electrolux_group_developer_sdk.client.appliances.so_appliance import SOAppliance

from homeassistant.components.number import NumberEntity, NumberMode
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
    """Return number entities for an appliance."""
    appliance_id = appliance_data.appliance.applianceId
    coordinator = coordinators.get(appliance_id)
    if coordinator is None:
        return []

    entities: list[ElectroluxBaseEntity] = []

    # Oven target temperature
    if isinstance(appliance_data, SOAppliance):
        # SO uses per-cavity temperature
        try:
            cavities = appliance_data.get_supported_cavities()
            for cavity in cavities:
                entities.append(
                    ElectroluxSOCavityTemperature(appliance_data, coordinator, cavity)
                )
        except Exception:
            pass
    elif isinstance(appliance_data, OVAppliance):
        entities.append(
            ElectroluxOvenTemperature(appliance_data, coordinator)
        )

    # Air purifier fan speed
    if isinstance(appliance_data, APAppliance):
        entities.append(
            ElectroluxAirPurifierFanSpeed(appliance_data, coordinator)
        )

    # Refrigerator per-cavity target temperature
    if isinstance(appliance_data, CRAppliance):
        try:
            cavities = appliance_data.get_supported_cavities()
            for cavity in cavities:
                entities.append(
                    ElectroluxCavityTargetTemperature(
                        appliance_data, coordinator, cavity
                    )
                )
        except Exception:
            pass

    # Hood fan level and light intensity
    if isinstance(appliance_data, HDAppliance):
        entities.append(
            ElectroluxHoodFanLevel(appliance_data, coordinator)
        )
        entities.append(
            ElectroluxHoodLightIntensity(appliance_data, coordinator)
        )

    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElectroluxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up number entities."""
    await async_setup_entities_helper(
        hass, entry, async_add_entities, build_entities_for_appliance
    )


class ElectroluxOvenTemperature(ElectroluxBaseEntity, NumberEntity):
    """Number entity for oven target temperature."""

    _attr_translation_key = "target_temperature"
    _attr_icon = "mdi:thermometer"
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self,
        appliance_data: OVAppliance | SOAppliance,
        coordinator: ElectroluxDataUpdateCoordinator,
    ) -> None:
        """Initialize."""
        super().__init__(appliance_data, coordinator)
        self._ov = appliance_data
        self._attr_unique_id = (
            f"{appliance_data.appliance.applianceId}_target_temperature"
        )
        self._attr_name = "Target temperature"
        self._attr_native_unit_of_measurement = "°C"

        try:
            self._attr_native_min_value = float(
                appliance_data.get_supported_min_temp() or 0
            )
            self._attr_native_max_value = float(
                appliance_data.get_supported_max_temp() or 300
            )
            self._attr_native_step = float(
                appliance_data.get_supported_step_temp() or 5
            )
        except Exception:
            self._attr_native_min_value = 0.0
            self._attr_native_max_value = 300.0
            self._attr_native_step = 5.0

        self._update_attr_state()

    def _update_attr_state(self) -> None:
        """Update target temperature."""
        try:
            temp = self._ov.get_current_target_temperature_c()
            self._attr_native_value = float(temp) if temp is not None else None
        except Exception:
            self._attr_native_value = None

    async def async_set_native_value(self, value: float) -> None:
        """Set target temperature."""
        command = self._ov.get_temperature_c_command(int(value))
        await self.coordinator.client.send_command(self.appliance_id, command)
        await self.coordinator.async_request_refresh()


class ElectroluxSOCavityTemperature(ElectroluxBaseEntity, NumberEntity):
    """Number entity for SO oven per-cavity target temperature."""

    _attr_translation_key = "target_temperature"
    _attr_icon = "mdi:thermometer"
    _attr_mode = NumberMode.SLIDER

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
            f"{appliance_data.appliance.applianceId}_{prefix}_target_temperature"
        )
        self._attr_name = "Target temperature"
        self._attr_native_unit_of_measurement = "°C"

        try:
            self._attr_native_min_value = float(
                appliance_data.get_cavity_supported_min_temp(cavity) or 0
            )
            self._attr_native_max_value = float(
                appliance_data.get_cavity_supported_max_temp(cavity) or 300
            )
            self._attr_native_step = float(
                appliance_data.get_cavity_supported_step_temp(cavity) or 5
            )
        except Exception:
            self._attr_native_min_value = 0.0
            self._attr_native_max_value = 300.0
            self._attr_native_step = 5.0

        self._update_attr_state()

    def _update_attr_state(self) -> None:
        """Update target temperature."""
        try:
            temp = self._so.get_current_cavity_target_temperature_c(self._cavity)
            self._attr_native_value = float(temp) if temp is not None else None
        except Exception:
            self._attr_native_value = None

    async def async_set_native_value(self, value: float) -> None:
        """Set target temperature."""
        command = self._so.get_temperature_c_command(self._cavity, int(value))
        await self.coordinator.client.send_command(self.appliance_id, command)
        await self.coordinator.async_request_refresh()


class ElectroluxAirPurifierFanSpeed(ElectroluxBaseEntity, NumberEntity):
    """Number entity for air purifier fan speed."""

    _attr_translation_key = "fan_speed"
    _attr_icon = "mdi:fan"
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self,
        appliance_data: APAppliance,
        coordinator: ElectroluxDataUpdateCoordinator,
    ) -> None:
        """Initialize."""
        super().__init__(appliance_data, coordinator)
        self._ap = appliance_data
        self._attr_unique_id = (
            f"{appliance_data.appliance.applianceId}_fan_speed"
        )
        self._attr_name = "Fan speed"

        try:
            self._attr_native_min_value = float(
                appliance_data.get_supported_min_fan_speed() or 1
            )
            self._attr_native_max_value = float(
                appliance_data.get_supported_max_fan_speed() or 9
            )
        except Exception:
            self._attr_native_min_value = 1.0
            self._attr_native_max_value = 9.0
        self._attr_native_step = 1.0

        self._update_attr_state()

    def _update_attr_state(self) -> None:
        """Update fan speed."""
        try:
            speed = self._ap.get_current_fan_speed()
            self._attr_native_value = float(speed) if speed is not None else None
        except Exception:
            self._attr_native_value = None

    async def async_set_native_value(self, value: float) -> None:
        """Set fan speed."""
        command = self._ap.get_fan_speed_command(int(value))
        await self.coordinator.client.send_command(self.appliance_id, command)
        await self.coordinator.async_request_refresh()


class ElectroluxCavityTargetTemperature(ElectroluxBaseEntity, NumberEntity):
    """Number entity for refrigerator cavity target temperature."""

    _attr_icon = "mdi:thermometer"
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self,
        appliance_data: CRAppliance,
        coordinator: ElectroluxDataUpdateCoordinator,
        cavity: str,
    ) -> None:
        """Initialize."""
        super().__init__(appliance_data, coordinator)
        self._cr = appliance_data
        self._cavity = cavity
        self._attr_unique_id = (
            f"{appliance_data.appliance.applianceId}_{cavity}_target_temp"
        )
        self._attr_name = f"{cavity.replace('_', ' ').title()} target temperature"
        self._attr_native_unit_of_measurement = "°C"

        try:
            self._attr_native_min_value = float(
                appliance_data.get_supported_min_temperature(cavity) or -25
            )
            self._attr_native_max_value = float(
                appliance_data.get_supported_max_temperature(cavity) or 8
            )
            self._attr_native_step = float(
                appliance_data.get_supported_step_temperature(cavity) or 1
            )
        except Exception:
            self._attr_native_min_value = -25.0
            self._attr_native_max_value = 8.0
            self._attr_native_step = 1.0

        self._update_attr_state()

    def _update_attr_state(self) -> None:
        """Update target temperature."""
        try:
            temp = self._cr.get_current_cavity_target_temperature_c(self._cavity)
            self._attr_native_value = float(temp) if temp is not None else None
        except Exception:
            self._attr_native_value = None

    async def async_set_native_value(self, value: float) -> None:
        """Set target temperature."""
        command = self._cr.get_set_cavity_temperature_c_command(
            self._cavity, int(value)
        )
        await self.coordinator.client.send_command(self.appliance_id, command)
        await self.coordinator.async_request_refresh()


class ElectroluxHoodFanLevel(ElectroluxBaseEntity, NumberEntity):
    """Number entity for hood fan level."""

    _attr_translation_key = "hood_fan_level"
    _attr_icon = "mdi:fan"
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self,
        appliance_data: HDAppliance,
        coordinator: ElectroluxDataUpdateCoordinator,
    ) -> None:
        """Initialize."""
        super().__init__(appliance_data, coordinator)
        self._hd = appliance_data
        self._attr_unique_id = (
            f"{appliance_data.appliance.applianceId}_hood_fan_level"
        )
        self._attr_name = "Fan level"

        try:
            levels = appliance_data.get_supported_hood_fan_level() or []
            if levels:
                self._attr_native_min_value = float(min(levels))
                self._attr_native_max_value = float(max(levels))
            else:
                self._attr_native_min_value = 0.0
                self._attr_native_max_value = 9.0
        except Exception:
            self._attr_native_min_value = 0.0
            self._attr_native_max_value = 9.0
        self._attr_native_step = 1.0

        self._update_attr_state()

    def _update_attr_state(self) -> None:
        """Update fan level."""
        try:
            level = self._hd.get_current_hood_fan_level()
            self._attr_native_value = float(level) if level is not None else None
        except Exception:
            self._attr_native_value = None

    async def async_set_native_value(self, value: float) -> None:
        """Set fan level."""
        command = self._hd.get_set_hood_fan_level_command(int(value))
        await self.coordinator.client.send_command(self.appliance_id, command)
        await self.coordinator.async_request_refresh()


class ElectroluxHoodLightIntensity(ElectroluxBaseEntity, NumberEntity):
    """Number entity for hood light intensity."""

    _attr_translation_key = "light_intensity"
    _attr_icon = "mdi:brightness-6"
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self,
        appliance_data: HDAppliance,
        coordinator: ElectroluxDataUpdateCoordinator,
    ) -> None:
        """Initialize."""
        super().__init__(appliance_data, coordinator)
        self._hd = appliance_data
        self._attr_unique_id = (
            f"{appliance_data.appliance.applianceId}_light_intensity"
        )
        self._attr_name = "Light intensity"
        self._attr_native_unit_of_measurement = "%"

        try:
            self._attr_native_min_value = float(
                appliance_data.get_min_light_intensity() or 0
            )
            self._attr_native_max_value = float(
                appliance_data.get_max_light_intensity() or 100
            )
            self._attr_native_step = float(
                appliance_data.get_step_light_intensity() or 1
            )
        except Exception:
            self._attr_native_min_value = 0.0
            self._attr_native_max_value = 100.0
            self._attr_native_step = 1.0

        self._update_attr_state()

    def _update_attr_state(self) -> None:
        """Update light intensity."""
        try:
            intensity = self._hd.get_current_light_intensity()
            self._attr_native_value = (
                float(intensity) if intensity is not None else None
            )
        except Exception:
            self._attr_native_value = None

    async def async_set_native_value(self, value: float) -> None:
        """Set light intensity."""
        command = self._hd.get_set_light_intensity_command(int(value))
        await self.coordinator.client.send_command(self.appliance_id, command)
        await self.coordinator.async_request_refresh()
