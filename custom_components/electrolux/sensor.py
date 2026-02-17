"""Sensor platform for Electrolux integration."""

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from electrolux_group_developer_sdk.client.appliances.ac_appliance import ACAppliance
from electrolux_group_developer_sdk.client.appliances.ap_appliance import APAppliance
from electrolux_group_developer_sdk.client.appliances.appliance_data import (
    ApplianceData,
)
from electrolux_group_developer_sdk.client.appliances.cr_appliance import CRAppliance
from electrolux_group_developer_sdk.client.appliances.dam_ac_appliance import (
    DAMACAppliance,
)
from electrolux_group_developer_sdk.client.appliances.dh_appliance import DHAppliance
from electrolux_group_developer_sdk.client.appliances.dw_appliance import DWAppliance
from electrolux_group_developer_sdk.client.appliances.hb_appliance import HBAppliance
from electrolux_group_developer_sdk.client.appliances.hd_appliance import HDAppliance
from electrolux_group_developer_sdk.client.appliances.ov_appliance import OVAppliance
from electrolux_group_developer_sdk.client.appliances.rvc_appliance import RVCAppliance
from electrolux_group_developer_sdk.client.appliances.so_appliance import SOAppliance
from electrolux_group_developer_sdk.client.appliances.td_appliance import TDAppliance
from electrolux_group_developer_sdk.client.appliances.wd_appliance import WDAppliance
from electrolux_group_developer_sdk.client.appliances.wm_appliance import WMAppliance

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    StateType,
)
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    EntityCategory,
    PERCENTAGE,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ElectroluxConfigEntry, ElectroluxDataUpdateCoordinator
from .entity import ElectroluxBaseEntity
from .entity_helper import async_setup_entities_helper

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class ElectroluxSensorDescription(SensorEntityDescription):
    """Sensor description for Electrolux sensors."""

    value_fn: Callable[..., StateType]
    is_supported_fn: Callable[..., bool] = lambda *_: True


# --- Oven sensors ---
OVEN_SENSORS: tuple[ElectroluxSensorDescription, ...] = (
    ElectroluxSensorDescription(
        key="ov_appliance_state",
        translation_key="appliance_state",
        icon="mdi:information-outline",
        value_fn=lambda a: a.get_current_appliance_state(),
    ),
    ElectroluxSensorDescription(
        key="ov_display_temperature",
        translation_key="display_temperature",
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda a: a.get_current_display_temperature_c(),
    ),
    ElectroluxSensorDescription(
        key="ov_food_probe_temperature",
        translation_key="food_probe_temperature",
        icon="mdi:thermometer-probe",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda a: a.get_current_display_food_probe_temperature_c(),
    ),
    ElectroluxSensorDescription(
        key="ov_time_to_end",
        translation_key="time_to_end",
        icon="mdi:timer-outline",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda a: a.get_current_time_to_end(),
    ),
    ElectroluxSensorDescription(
        key="ov_current_program",
        translation_key="current_program",
        icon="mdi:chef-hat",
        value_fn=lambda a: a.get_current_program(),
    ),
    ElectroluxSensorDescription(
        key="ov_running_time",
        translation_key="running_time",
        icon="mdi:timer",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda a: a.get_current_running_time(),
    ),
    ElectroluxSensorDescription(
        key="ov_remote_control",
        translation_key="remote_control",
        icon="mdi:remote",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda a: a.get_current_remote_control(),
    ),
)

# --- AC sensors ---
AC_SENSORS: tuple[ElectroluxSensorDescription, ...] = (
    ElectroluxSensorDescription(
        key="ac_ambient_temperature",
        translation_key="ambient_temperature",
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda a: a.get_current_ambient_temperature_c(),
    ),
    ElectroluxSensorDescription(
        key="ac_appliance_state",
        translation_key="appliance_state",
        icon="mdi:air-conditioner",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda a: a.get_current_appliance_state(),
    ),
)

# --- Air purifier sensors ---
AP_SENSORS: tuple[ElectroluxSensorDescription, ...] = (
    ElectroluxSensorDescription(
        key="ap_pm25",
        translation_key="pm25",
        icon="mdi:blur",
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        value_fn=lambda a: a.get_current_air_quality("PM2_5"),
        is_supported_fn=lambda a: _ap_supports_air_quality(a, "PM2_5"),
    ),
    ElectroluxSensorDescription(
        key="ap_pm10",
        translation_key="pm10",
        icon="mdi:blur-linear",
        device_class=SensorDeviceClass.PM10,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        value_fn=lambda a: a.get_current_air_quality("PM10"),
        is_supported_fn=lambda a: _ap_supports_air_quality(a, "PM10"),
    ),
    ElectroluxSensorDescription(
        key="ap_pm1",
        translation_key="pm1",
        icon="mdi:blur-radial",
        device_class=SensorDeviceClass.PM1,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        value_fn=lambda a: a.get_current_air_quality("PM1"),
        is_supported_fn=lambda a: _ap_supports_air_quality(a, "PM1"),
    ),
    ElectroluxSensorDescription(
        key="ap_tvoc",
        translation_key="tvoc",
        icon="mdi:air-filter",
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        value_fn=lambda a: a.get_current_air_quality("TVOC"),
        is_supported_fn=lambda a: _ap_supports_air_quality(a, "TVOC"),
    ),
)

# --- Dehumidifier sensors ---
DH_SENSORS: tuple[ElectroluxSensorDescription, ...] = (
    ElectroluxSensorDescription(
        key="dh_current_humidity",
        translation_key="current_humidity",
        icon="mdi:water-percent",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda a: a.get_current_sensor_humidity(),
    ),
)

# --- Washing machine / washer-dryer / dryer sensors ---
LAUNDRY_SENSORS: tuple[ElectroluxSensorDescription, ...] = (
    ElectroluxSensorDescription(
        key="laundry_appliance_state",
        translation_key="appliance_state",
        icon="mdi:washing-machine",
        value_fn=lambda a: a.get_current_appliance_state(),
    ),
    ElectroluxSensorDescription(
        key="laundry_cycle_phase",
        translation_key="cycle_phase",
        icon="mdi:progress-clock",
        value_fn=lambda a: a.get_current_cycle_phase(),
    ),
    ElectroluxSensorDescription(
        key="laundry_time_to_end",
        translation_key="time_to_end",
        icon="mdi:timer-outline",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda a: a.get_current_time_to_end(),
    ),
    ElectroluxSensorDescription(
        key="laundry_current_program",
        translation_key="current_program",
        icon="mdi:format-list-bulleted",
        value_fn=lambda a: a.get_current_program(),
    ),
    ElectroluxSensorDescription(
        key="laundry_remote_control",
        translation_key="remote_control",
        icon="mdi:remote",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda a: a.get_current_remote_control(),
    ),
)

# --- Dishwasher sensors ---
DISHWASHER_SENSORS: tuple[ElectroluxSensorDescription, ...] = (
    ElectroluxSensorDescription(
        key="dw_appliance_state",
        translation_key="appliance_state",
        icon="mdi:dishwasher",
        value_fn=lambda a: a.get_current_appliance_state(),
    ),
    ElectroluxSensorDescription(
        key="dw_cycle_phase",
        translation_key="cycle_phase",
        icon="mdi:progress-clock",
        value_fn=lambda a: a.get_current_cycle_phase(),
    ),
    ElectroluxSensorDescription(
        key="dw_time_to_end",
        translation_key="time_to_end",
        icon="mdi:timer-outline",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda a: a.get_current_time_to_end(),
    ),
    ElectroluxSensorDescription(
        key="dw_current_program",
        translation_key="current_program",
        icon="mdi:format-list-bulleted",
        value_fn=lambda a: a.get_current_program(),
    ),
)

# --- Robot vacuum sensors ---
RVC_SENSORS: tuple[ElectroluxSensorDescription, ...] = (
    ElectroluxSensorDescription(
        key="rvc_battery",
        translation_key="battery",
        icon="mdi:battery",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda a: a.get_battery_percentage(),
    ),
    ElectroluxSensorDescription(
        key="rvc_state",
        translation_key="appliance_state",
        icon="mdi:robot-vacuum",
        value_fn=lambda a: a.get_current_state(),
    ),
)

# --- Refrigerator sensors ---
CR_SENSORS: tuple[ElectroluxSensorDescription, ...] = (
    ElectroluxSensorDescription(
        key="cr_ui_lock",
        translation_key="ui_lock_mode",
        icon="mdi:lock-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda a: a.get_current_ui_lock_mode(),
    ),
)

# --- Hood sensors ---
HD_SENSORS: tuple[ElectroluxSensorDescription, ...] = (
    ElectroluxSensorDescription(
        key="hd_appliance_state",
        translation_key="appliance_state",
        icon="mdi:information-outline",
        value_fn=lambda a: a.get_current_appliance_state(),
    ),
    ElectroluxSensorDescription(
        key="hd_grease_filter_time",
        translation_key="grease_filter_time",
        icon="mdi:air-filter",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda a: a.get_current_hood_grease_filter_time(),
    ),
)


def _ap_supports_air_quality(appliance: APAppliance, quality: str) -> bool:
    """Check if an air purifier supports a specific air quality measurement."""
    try:
        aq_map = appliance.get_air_quality_map()
        return quality in aq_map
    except Exception:
        return False


def build_entities_for_appliance(
    appliance_data: ApplianceData,
    coordinators: dict[str, ElectroluxDataUpdateCoordinator],
) -> list[ElectroluxBaseEntity]:
    """Return sensor entities for an appliance."""
    appliance_id = appliance_data.appliance.applianceId
    coordinator = coordinators.get(appliance_id)
    if coordinator is None:
        return []

    entities: list[ElectroluxBaseEntity] = []

    if isinstance(appliance_data, (OVAppliance, SOAppliance)):
        entities.extend(
            ElectroluxSensor(appliance_data, coordinator, desc)
            for desc in OVEN_SENSORS
        )
    elif isinstance(appliance_data, (ACAppliance, DAMACAppliance)):
        entities.extend(
            ElectroluxSensor(appliance_data, coordinator, desc)
            for desc in AC_SENSORS
        )
    elif isinstance(appliance_data, APAppliance):
        entities.extend(
            ElectroluxSensor(appliance_data, coordinator, desc)
            for desc in AP_SENSORS
            if desc.is_supported_fn(appliance_data)
        )
    elif isinstance(appliance_data, DHAppliance):
        entities.extend(
            ElectroluxSensor(appliance_data, coordinator, desc)
            for desc in DH_SENSORS
        )
    elif isinstance(appliance_data, (WMAppliance, WDAppliance, TDAppliance)):
        entities.extend(
            ElectroluxSensor(appliance_data, coordinator, desc)
            for desc in LAUNDRY_SENSORS
        )
    elif isinstance(appliance_data, DWAppliance):
        entities.extend(
            ElectroluxSensor(appliance_data, coordinator, desc)
            for desc in DISHWASHER_SENSORS
        )
    elif isinstance(appliance_data, RVCAppliance):
        entities.extend(
            ElectroluxSensor(appliance_data, coordinator, desc)
            for desc in RVC_SENSORS
        )
    elif isinstance(appliance_data, CRAppliance):
        entities.extend(
            ElectroluxSensor(appliance_data, coordinator, desc)
            for desc in CR_SENSORS
        )
        try:
            cavities = appliance_data.get_supported_cavities()
            for cavity in cavities:
                entities.append(
                    ElectroluxCavityTempSensor(appliance_data, coordinator, cavity)
                )
        except Exception:
            pass
    elif isinstance(appliance_data, HDAppliance):
        entities.extend(
            ElectroluxSensor(appliance_data, coordinator, desc)
            for desc in HD_SENSORS
        )
    elif isinstance(appliance_data, HBAppliance):
        entities.append(
            ElectroluxSensor(
                appliance_data,
                coordinator,
                ElectroluxSensorDescription(
                    key="hb_appliance_state",
                    translation_key="appliance_state",
                    icon="mdi:stove",
                    value_fn=lambda a: a.get_current_appliance_state(),
                ),
            )
        )

    # Alert sensor for all appliances that support alerts
    if hasattr(appliance_data, "get_current_alerts"):
        entities.append(
            ElectroluxAlertSensor(appliance_data, coordinator)
        )

    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElectroluxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensor entities."""
    await async_setup_entities_helper(
        hass, entry, async_add_entities, build_entities_for_appliance
    )


class ElectroluxSensor(ElectroluxBaseEntity, SensorEntity):
    """Generic sensor for Electrolux appliances."""

    entity_description: ElectroluxSensorDescription

    def __init__(
        self,
        appliance_data: ApplianceData,
        coordinator: ElectroluxDataUpdateCoordinator,
        description: ElectroluxSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(appliance_data, coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{appliance_data.appliance.applianceId}_{description.key}"
        )
        self._cached_value: StateType = None
        self._update_attr_state()

    def _update_attr_state(self) -> None:
        """Update sensor value with caching."""
        try:
            value = self.entity_description.value_fn(self._appliance_data)
            if value is not None:
                self._cached_value = value
                self._attr_native_value = value
            else:
                # Return cached value to avoid flashing "unavailable"
                self._attr_native_value = self._cached_value
        except Exception:
            self._attr_native_value = self._cached_value


class ElectroluxCavityTempSensor(ElectroluxBaseEntity, SensorEntity):
    """Temperature sensor for a specific refrigerator cavity."""

    def __init__(
        self,
        appliance_data: CRAppliance,
        coordinator: ElectroluxDataUpdateCoordinator,
        cavity: str,
    ) -> None:
        """Initialize the cavity temperature sensor."""
        super().__init__(appliance_data, coordinator)
        self._cr = appliance_data
        self._cavity = cavity
        self._attr_unique_id = (
            f"{appliance_data.appliance.applianceId}_{cavity}_temperature"
        )
        self._attr_icon = "mdi:thermometer"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_name = f"{cavity.replace('_', ' ').title()} temperature"
        self._cached_value: StateType = None
        self._update_attr_state()

    def _update_attr_state(self) -> None:
        """Update cavity temperature with caching."""
        try:
            value = self._cr.get_current_cavity_target_temperature_c(self._cavity)
            if value is not None:
                self._cached_value = value
                self._attr_native_value = value
            else:
                self._attr_native_value = self._cached_value
        except Exception:
            self._attr_native_value = self._cached_value


class ElectroluxAlertSensor(ElectroluxBaseEntity, SensorEntity):
    """Alert sensor that exposes active alerts as state attributes."""

    _attr_icon = "mdi:alert-circle-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        appliance_data: ApplianceData,
        coordinator: ElectroluxDataUpdateCoordinator,
    ) -> None:
        """Initialize alert sensor."""
        super().__init__(appliance_data, coordinator)
        self._attr_unique_id = (
            f"{appliance_data.appliance.applianceId}_alerts"
        )
        self._attr_translation_key = "alerts"
        self._attr_name = "Alerts"
        self._update_attr_state()

    def _update_attr_state(self) -> None:
        """Update alert count and details."""
        try:
            alerts = self._appliance_data.get_current_alerts()
            if alerts and isinstance(alerts, (list, dict)):
                if isinstance(alerts, list):
                    self._attr_native_value = len(alerts)
                    self._attr_extra_state_attributes = {"alerts": alerts}
                elif isinstance(alerts, dict):
                    active = {k: v for k, v in alerts.items() if v}
                    self._attr_native_value = len(active)
                    self._attr_extra_state_attributes = {"alerts": active}
            else:
                self._attr_native_value = 0
                self._attr_extra_state_attributes = {"alerts": {}}
        except Exception:
            self._attr_native_value = 0
            self._attr_extra_state_attributes = {"alerts": {}}
