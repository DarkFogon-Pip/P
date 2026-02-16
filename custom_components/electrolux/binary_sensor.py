"""Binary sensor platform for Electrolux integration."""

from collections.abc import Callable
from dataclasses import dataclass
import logging

from electrolux_group_developer_sdk.client.appliances.appliance_data import (
    ApplianceData,
)
from electrolux_group_developer_sdk.client.appliances.cr_appliance import CRAppliance
from electrolux_group_developer_sdk.client.appliances.dw_appliance import DWAppliance
from electrolux_group_developer_sdk.client.appliances.hb_appliance import HBAppliance
from electrolux_group_developer_sdk.client.appliances.ov_appliance import OVAppliance
from electrolux_group_developer_sdk.client.appliances.rvc_appliance import RVCAppliance
from electrolux_group_developer_sdk.client.appliances.so_appliance import SOAppliance
from electrolux_group_developer_sdk.client.appliances.td_appliance import TDAppliance
from electrolux_group_developer_sdk.client.appliances.wd_appliance import WDAppliance
from electrolux_group_developer_sdk.client.appliances.wm_appliance import WMAppliance

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ElectroluxConfigEntry, ElectroluxDataUpdateCoordinator
from .entity import ElectroluxBaseEntity
from .entity_helper import async_setup_entities_helper

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class ElectroluxBinarySensorDescription(BinarySensorEntityDescription):
    """Binary sensor description for Electrolux."""

    is_on_fn: Callable[..., bool | None]


# --- Appliances with door states ---
DOOR_SENSOR = ElectroluxBinarySensorDescription(
    key="door",
    translation_key="door",
    icon="mdi:door",
    device_class=BinarySensorDeviceClass.DOOR,
    is_on_fn=lambda a: _is_door_open(a),
)

CONNECTION_SENSOR = ElectroluxBinarySensorDescription(
    key="connection",
    translation_key="connection",
    icon="mdi:wifi",
    device_class=BinarySensorDeviceClass.CONNECTIVITY,
    is_on_fn=lambda _a, state: state and state.lower() == "connected",
)

RVC_DOCKED_SENSOR = ElectroluxBinarySensorDescription(
    key="docked",
    translation_key="docked",
    icon="mdi:home",
    device_class=BinarySensorDeviceClass.PLUG,
    is_on_fn=lambda a: a.is_docked(),
)

# Appliance types that have door state
DOOR_APPLIANCE_TYPES = (
    OVAppliance,
    SOAppliance,
    DWAppliance,
    WMAppliance,
    WDAppliance,
    TDAppliance,
    HBAppliance,
)


def _is_door_open(appliance: ApplianceData) -> bool | None:
    """Check if the door is open for various appliance types."""
    try:
        door_state = appliance.get_current_door_state()
        if door_state is None:
            return None
        return door_state.upper() == "OPEN"
    except Exception:
        return None


def build_entities_for_appliance(
    appliance_data: ApplianceData,
    coordinators: dict[str, ElectroluxDataUpdateCoordinator],
) -> list[ElectroluxBaseEntity]:
    """Return binary sensor entities for an appliance."""
    appliance_id = appliance_data.appliance.applianceId
    coordinator = coordinators.get(appliance_id)
    if coordinator is None:
        return []

    entities: list[ElectroluxBaseEntity] = []

    # Connection sensor for all appliances
    entities.append(
        ElectroluxConnectionBinarySensor(appliance_data, coordinator)
    )

    # Door sensor for applicable types
    if isinstance(appliance_data, DOOR_APPLIANCE_TYPES):
        entities.append(
            ElectroluxBinarySensor(appliance_data, coordinator, DOOR_SENSOR)
        )

    # Docked sensor for robot vacuums
    if isinstance(appliance_data, RVCAppliance):
        entities.append(
            ElectroluxBinarySensor(appliance_data, coordinator, RVC_DOCKED_SENSOR)
        )

    # Per-cavity door sensors for refrigerators
    if isinstance(appliance_data, CRAppliance):
        try:
            cavities = appliance_data.get_supported_cavities()
            for cavity in cavities:
                entities.append(
                    ElectroluxCavityDoorSensor(
                        appliance_data, coordinator, cavity
                    )
                )
        except Exception:
            pass

    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElectroluxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensor entities."""
    await async_setup_entities_helper(
        hass, entry, async_add_entities, build_entities_for_appliance
    )


class ElectroluxBinarySensor(ElectroluxBaseEntity, BinarySensorEntity):
    """Binary sensor for Electrolux appliances."""

    entity_description: ElectroluxBinarySensorDescription

    def __init__(
        self,
        appliance_data: ApplianceData,
        coordinator: ElectroluxDataUpdateCoordinator,
        description: ElectroluxBinarySensorDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(appliance_data, coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{appliance_data.appliance.applianceId}_{description.key}"
        )
        self._update_attr_state()

    def _update_attr_state(self) -> None:
        """Update binary sensor value."""
        try:
            self._attr_is_on = self.entity_description.is_on_fn(
                self._appliance_data
            )
        except Exception:
            self._attr_is_on = None


class ElectroluxConnectionBinarySensor(ElectroluxBaseEntity, BinarySensorEntity):
    """Connection status binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_translation_key = "connection"
    _attr_icon = "mdi:wifi"

    def __init__(
        self,
        appliance_data: ApplianceData,
        coordinator: ElectroluxDataUpdateCoordinator,
    ) -> None:
        """Initialize."""
        super().__init__(appliance_data, coordinator)
        self._attr_unique_id = (
            f"{appliance_data.appliance.applianceId}_connection"
        )
        self._update_attr_state()

    @property
    def available(self) -> bool:
        """Connection sensor is always available if coordinator is."""
        return self.coordinator.last_update_success

    def _update_attr_state(self) -> None:
        """Update connection state."""
        conn = self.connection_state
        self._attr_is_on = conn is not None and conn.lower() == "connected"


class ElectroluxCavityDoorSensor(ElectroluxBaseEntity, BinarySensorEntity):
    """Door sensor for a specific refrigerator cavity."""

    _attr_device_class = BinarySensorDeviceClass.DOOR
    _attr_icon = "mdi:door"

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
            f"{appliance_data.appliance.applianceId}_{cavity}_door"
        )
        self._attr_name = f"{cavity.replace('_', ' ').title()} door"
        self._update_attr_state()

    def _update_attr_state(self) -> None:
        """Update cavity door state."""
        try:
            door_state = self._cr.get_current_cavity_door_state(self._cavity)
            self._attr_is_on = (
                door_state is not None and door_state.upper() == "OPEN"
            )
        except Exception:
            self._attr_is_on = None
