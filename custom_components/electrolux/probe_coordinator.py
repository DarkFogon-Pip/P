"""Bluetooth coordinator for standalone Electrolux food probes."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import timedelta
import logging

from bleak import BleakClient
from bleak_retry_connector import (
    BleakClientWithServiceCache,
    close_stale_connections_by_address,
    establish_connection,
    get_device,
)

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_MODEL
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    PROBE_BATTERY_CHAR_UUID,
    PROBE_MANUFACTURER,
    PROBE_NOTIFY_CHAR_UUIDS,
    PROBE_RAW_BLOB_1_CHAR_UUID,
    PROBE_RAW_BLOB_2_CHAR_UUID,
    PROBE_SCAN_INTERVAL_SECONDS,
    PROBE_STATE_CHAR_UUID,
    PROBE_STATUS_CHAR_UUID,
    PROBE_TEMPERATURE_1_CHAR_UUID,
    PROBE_TEMPERATURE_2_CHAR_UUID,
    PROBE_TEMPERATURE_3_CHAR_UUID,
    PROBE_TEMPERATURE_LIMIT_CHAR_UUID,
)
from .probe_decoder import ElectroluxProbeState, build_probe_state

_LOGGER = logging.getLogger(__name__)


type ElectroluxProbeConfigEntry = ConfigEntry[ElectroluxProbeDataUpdateCoordinator]


class ElectroluxProbeDataUpdateCoordinator(
    DataUpdateCoordinator[ElectroluxProbeState]
):
    """Manage polling for a standalone Electrolux probe."""

    config_entry: ElectroluxProbeConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ElectroluxProbeConfigEntry) -> None:
        """Initialize the probe coordinator."""
        self.address = entry.data[CONF_ADDRESS].upper()
        self.model = entry.data.get(CONF_MODEL)
        self._client: BleakClient | None = None
        self._client_lock = asyncio.Lock()
        self._notify_values: dict[str, bytes] = {}
        self._last_polled_values: dict[str, bytes] = {}
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_probe_{self.address}",
            update_interval=timedelta(seconds=PROBE_SCAN_INTERVAL_SECONDS),
        )

    async def _async_setup(self) -> None:
        """Ensure a connectable Bluetooth scanner is available."""
        scanner_count = 0
        for _attempt in range(8):
            scanner_count = bluetooth.async_scanner_count(self.hass, connectable=True)
            if scanner_count:
                break
            await asyncio.sleep(5)

        if scanner_count == 0:
            raise ConfigEntryNotReady("No connectable Bluetooth scanner is available")

        await close_stale_connections_by_address(self.address)

        ble_device = None
        for _attempt in range(3):
            ble_device = await self._async_resolve_ble_device()
            if ble_device:
                break
            await asyncio.sleep(5)

        if not ble_device:
            raise ConfigEntryNotReady(
                f"Could not find Electrolux probe with address {self.address}"
            )

    async def _async_resolve_ble_device(self):
        """Resolve the BLE device from Home Assistant or fallback cache."""
        return bluetooth.async_ble_device_from_address(
            self.hass, self.address, True
        ) or await get_device(self.address)

    async def async_disconnect(self) -> None:
        """Disconnect the live probe session."""
        async with self._client_lock:
            if not self._client:
                return

            for uuid in PROBE_NOTIFY_CHAR_UUIDS.values():
                try:
                    await self._client.stop_notify(uuid)
                except Exception:
                    pass

            try:
                if self._client.is_connected:
                    await self._client.disconnect()
            finally:
                self._client = None

    async def _async_ensure_connected(self) -> BleakClient:
        """Create or reuse a connected Bleak client."""
        async with self._client_lock:
            if self._client and self._client.is_connected:
                return self._client

            ble_device = await self._async_resolve_ble_device()
            if not ble_device:
                raise UpdateFailed(
                    f"Could not find Electrolux probe with address {self.address}"
                )

            await close_stale_connections_by_address(self.address)
            client = await establish_connection(
                BleakClientWithServiceCache,
                ble_device,
                self.config_entry.title,
                max_attempts=3,
                timeout=20.0,
            )
            await self._async_try_pair(client)
            await self._async_start_notifications(client)
            self._client = client
            return client

    async def _async_start_notifications(self, client: BleakClient) -> None:
        """Subscribe to the chars that stream updates while connected."""
        for key, uuid in PROBE_NOTIFY_CHAR_UUIDS.items():
            try:
                await client.start_notify(uuid, self._build_notify_handler(key))
            except Exception as err:
                _LOGGER.debug(
                    "Unable to subscribe to %s on %s: %s", key, self.address, err
                )

    def _build_notify_handler(self, key: str) -> Callable[[int, bytearray], None]:
        """Create a notify handler for a characteristic."""

        def _handler(_: int, data: bytearray) -> None:
            self.hass.loop.call_soon_threadsafe(
                self._handle_notification, key, bytes(data)
            )

        return _handler

    @callback
    def _handle_notification(self, key: str, data: bytes) -> None:
        """Store the latest notify payload and push an updated state."""
        self._notify_values[key] = data
        _LOGGER.debug("Probe %s notify %s=%s", self.address, key, data.hex())
        if not self._last_polled_values:
            return
        self.async_set_updated_data(self._build_state(self._last_polled_values))

    async def _async_update_data(self) -> ElectroluxProbeState:
        """Fetch the current probe data via an active Bluetooth connection."""
        try:
            client = await self._async_ensure_connected()
            polled_values = {
                "battery": await self._async_read_char(client, PROBE_BATTERY_CHAR_UUID),
                "raw_blob_1": await self._async_read_char(
                    client, PROBE_RAW_BLOB_1_CHAR_UUID
                ),
                "raw_blob_2": await self._async_read_char(
                    client, PROBE_RAW_BLOB_2_CHAR_UUID
                ),
                "temperature_channel_1": await self._async_read_char(
                    client, PROBE_TEMPERATURE_1_CHAR_UUID
                ),
                "temperature_channel_2": await self._async_read_char(
                    client, PROBE_TEMPERATURE_2_CHAR_UUID
                ),
                "temperature_channel_3": await self._async_read_char(
                    client, PROBE_TEMPERATURE_3_CHAR_UUID
                ),
                "temperature_limit": await self._async_read_char(
                    client, PROBE_TEMPERATURE_LIMIT_CHAR_UUID
                ),
                "status": await self._async_read_char(client, PROBE_STATUS_CHAR_UUID),
                "state": await self._async_read_char(client, PROBE_STATE_CHAR_UUID),
            }
        except Exception as err:
            await self.async_disconnect()
            raise UpdateFailed(
                f"Failed to poll Electrolux probe {self.address}"
            ) from err

        self._last_polled_values = {
            key: value
            for key, value in polled_values.items()
            if value is not None
        }
        state = self._build_state(self._last_polled_values)
        _LOGGER.debug(
            "Probe %s poll raw=%s decoded=%s",
            self.address,
            {key: value.hex() for key, value in self._last_polled_values.items()},
            {
                "battery_level": state.battery_level,
                "ambient_temperature": state.ambient_temperature,
                "probe_temperature": state.probe_temperature,
                "secondary_temperature": state.secondary_temperature,
                "temperature_limit": state.temperature_limit,
                "raw_blob_1_float": state.raw_blob_1_float,
                "raw_blob_2_float": state.raw_blob_2_float,
                "status": state.status,
                "state": state.state,
            },
        )
        return state

    def _build_state(
        self, polled_values: dict[str, bytes | None]
    ) -> ElectroluxProbeState:
        """Build the current state from polled and notify values."""
        return build_probe_state(polled_values, self._notify_values)

    async def _async_try_pair(self, client: BleakClient) -> None:
        """Attempt to pair, but tolerate platforms that do not support it."""
        try:
            await client.pair(protection_level=1)
        except TypeError:
            try:
                await client.pair()
            except Exception as err:  # pragma: no cover - platform-dependent
                _LOGGER.debug(
                    "Pairing attempt failed for %s: %s", self.address, err
                )
        except Exception as err:  # pragma: no cover - platform-dependent
            _LOGGER.debug("Pairing attempt failed for %s: %s", self.address, err)

    async def _async_read_char(
        self, client: BleakClient, char_uuid: str
    ) -> bytes | None:
        """Read a characteristic and return its raw bytes."""
        try:
            return bytes(await client.read_gatt_char(char_uuid))
        except Exception as err:
            _LOGGER.debug(
                "Unable to read %s from %s %s: %s",
                char_uuid,
                PROBE_MANUFACTURER,
                self.address,
                err,
            )
            return None
