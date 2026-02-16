"""Electrolux API Client."""

from collections.abc import Callable
import logging

from electrolux_group_developer_sdk.client.appliance_client import ApplianceClient
from electrolux_group_developer_sdk.client.appliances.appliance_data import (
    ApplianceData,
)
from electrolux_group_developer_sdk.client.client_exception import (
    ApplianceClientException,
)
from electrolux_group_developer_sdk.client.dto.appliance_state import ApplianceState

_LOGGER: logging.Logger = logging.getLogger(__name__)


class ElectroluxApiClient:
    """API Client to fetch appliance data."""

    def __init__(self, client: ApplianceClient) -> None:
        """Initialize Electrolux API Client."""
        self._client = client

    async def fetch_appliance_data(self) -> list[ApplianceData]:
        """Retrieve all appliances data from the Electrolux APIs."""
        try:
            appliances = await self._client.get_appliance_data()
        except ApplianceClientException as e:
            appliances = []
            _LOGGER.warning("Failed to get appliances: %s", e)

        return [
            appliance
            for appliance in appliances
            if appliance.details is not None and appliance.state is not None
        ]

    async def fetch_appliance_state(self, appliance_id: str) -> ApplianceState:
        """Retrieve the appliance state by appliance_id."""
        return await self._client.get_appliance_state(appliance_id)

    async def send_command(self, appliance_id: str, commands: dict) -> None:
        """Send a command to an appliance."""
        try:
            await self._client.send_command(appliance_id, commands)
        except ApplianceClientException as e:
            _LOGGER.error("Failed to send command to %s: %s", appliance_id, e)
            raise

    def add_listener(
        self, appliance_id: str, callback: Callable[[dict], None]
    ) -> None:
        """Register a callback for a specific appliance."""
        self._client.add_listener(appliance_id, callback)

    def remove_all_listeners_by_appliance_id(self, appliance_id: str) -> None:
        """Remove all SSE listeners for a specific appliance."""
        self._client.remove_all_listeners_by_appliance_id(appliance_id)
