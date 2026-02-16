"""Base entity for Electrolux integration."""

from abc import abstractmethod
import logging

from electrolux_group_developer_sdk.client.appliances.appliance_data import (
    ApplianceData,
)

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ElectroluxDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class ElectroluxBaseEntity(CoordinatorEntity[ElectroluxDataUpdateCoordinator]):
    """Base class for Electrolux entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        appliance_data: ApplianceData,
        coordinator: ElectroluxDataUpdateCoordinator,
    ) -> None:
        """Initialize the base entity."""
        super().__init__(coordinator)
        appliance = appliance_data.appliance
        self._appliance_data = appliance_data
        self._attr_unique_id = appliance.applianceId
        self.appliance_id = appliance.applianceId

        brand = "Electrolux"
        model = None
        serial = None
        if appliance_data.details:
            info = appliance_data.details.applianceInfo
            brand = info.brand or "Electrolux"
            model = info.model
            serial = info.serialNumber

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, appliance.applianceId)},
            name=appliance.applianceName,
            manufacturer=brand,
            model=model,
            serial_number=serial,
        )

    @property
    def reported_state(self) -> dict:
        """Return the reported state from the coordinator."""
        state = self.coordinator.data
        if state and state.properties:
            return state.properties.get("reported", {})
        return {}

    @property
    def connection_state(self) -> str | None:
        """Return the connection state."""
        state = self.coordinator.data
        if state:
            return state.connectionState
        return None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if not super().available:
            return False
        state = self.coordinator.data
        if state and state.connectionState:
            return state.connectionState.lower() == "connected"
        return True

    @abstractmethod
    def _update_attr_state(self) -> None:
        """Update entity-specific attributes."""

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle coordinator update."""
        state = self.coordinator.data
        if not state:
            return

        self._appliance_data.update_state(state)
        self._update_attr_state()
        self.async_write_ha_state()
