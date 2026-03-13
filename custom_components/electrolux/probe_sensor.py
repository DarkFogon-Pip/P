"""Sensor entities for standalone Electrolux food probes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    StateType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, PROBE_MANUFACTURER
from .probe_coordinator import ElectroluxProbeDataUpdateCoordinator
from .probe_decoder import ElectroluxProbeState


@dataclass(kw_only=True, frozen=True)
class ElectroluxProbeSensorDescription(SensorEntityDescription):
    """Describe a standalone probe sensor."""

    value_fn: Callable[[ElectroluxProbeState], StateType]
    include_raw_values: bool = False


SENSOR_DESCRIPTIONS: tuple[ElectroluxProbeSensorDescription, ...] = (
    ElectroluxProbeSensorDescription(
        key="battery",
        translation_key="battery",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda state: state.battery_level,
    ),
    ElectroluxProbeSensorDescription(
        key="ambient_temperature",
        translation_key="ambient_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda state: state.ambient_temperature,
    ),
    ElectroluxProbeSensorDescription(
        key="probe_temperature",
        translation_key="food_probe_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda state: state.probe_temperature,
        include_raw_values=True,
    ),
    ElectroluxProbeSensorDescription(
        key="secondary_temperature",
        name="Internal temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.secondary_temperature,
    ),
    ElectroluxProbeSensorDescription(
        key="temperature_limit",
        name="Probe temperature limit",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.temperature_limit,
    ),
    ElectroluxProbeSensorDescription(
        key="raw_blob_1_float",
        name="Tip temperature source",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.raw_blob_1_float,
    ),
    ElectroluxProbeSensorDescription(
        key="raw_blob_2_float",
        name="Auxiliary temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.raw_blob_2_float,
    ),
    ElectroluxProbeSensorDescription(
        key="status",
        name="Status",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.status,
        include_raw_values=True,
    ),
    ElectroluxProbeSensorDescription(
        key="state",
        name="State",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda state: state.state,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up standalone probe sensor entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        ElectroluxProbeSensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    )


class ElectroluxProbeSensor(
    CoordinatorEntity[ElectroluxProbeDataUpdateCoordinator], SensorEntity
):
    """Represent a standalone Electrolux probe sensor."""

    _attr_has_entity_name = True
    entity_description: ElectroluxProbeSensorDescription

    def __init__(
        self,
        coordinator: ElectroluxProbeDataUpdateCoordinator,
        description: ElectroluxProbeSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        mac = format_mac(coordinator.address)
        self._attr_unique_id = f"{mac}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"probe_{mac}")},
            connections={(CONNECTION_BLUETOOTH, mac)},
            name=coordinator.config_entry.title,
            manufacturer=PROBE_MANUFACTURER,
            model=coordinator.model,
        )

    @property
    def native_value(self) -> StateType:
        """Return the state value."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, StateType | str] | None:
        """Expose decoded probe details alongside raw values for diagnostics."""
        if (
            self.coordinator.data is None
            or not self.entity_description.include_raw_values
        ):
            return None
        state = self.coordinator.data
        attributes: dict[str, StateType] = {
            "temperature_source": "raw_blob_1_float",
            "legacy_temperature_source": "temperature_channel_2",
            "decoded_ambient_temperature": state.ambient_temperature,
            "decoded_probe_temperature": state.probe_temperature,
            "decoded_tip_temperature_source": state.raw_blob_1_float,
            "decoded_legacy_probe_temperature": state.legacy_probe_temperature,
            "decoded_internal_temperature": state.secondary_temperature,
            "decoded_temperature_limit": state.temperature_limit,
            "decoded_auxiliary_temperature": state.raw_blob_2_float,
            "decoded_raw_float_1": state.raw_blob_1_float,
            "decoded_raw_float_2": state.raw_blob_2_float,
            "decoded_status": state.status,
            "decoded_state": state.state,
        }
        attributes.update(state.raw_values)
        return attributes
