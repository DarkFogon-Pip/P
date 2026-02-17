"""Diagnostics support for Electrolux integration."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import ElectroluxConfigEntry

REDACT_KEYS = {
    "access_token",
    "refresh_token",
    "api_key",
    "serialNumber",
    "applianceId",
    "userId",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ElectroluxConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = entry.runtime_data

    appliance_diagnostics = []
    for appliance_data in data.appliances:
        appliance = appliance_data.appliance
        appliance_id = appliance.applianceId
        coordinator = data.coordinators.get(appliance_id)

        diag: dict[str, Any] = {
            "appliance_id": appliance.applianceId,
            "appliance_name": appliance.applianceName,
            "appliance_type": appliance.applianceType,
            "created": str(appliance.created),
        }

        if appliance_data.details:
            info = appliance_data.details.applianceInfo
            diag["details"] = {
                "brand": info.brand,
                "model": info.model,
                "serial_number": info.serialNumber,
                "pnc": info.pnc,
                "device_type": info.deviceType,
                "variant": info.variant,
                "colour": info.colour,
            }
            diag["capabilities_keys"] = list(
                appliance_data.details.capabilities.keys()
            )

        if coordinator and coordinator.data:
            state = coordinator.data
            diag["connection_state"] = state.connectionState
            diag["status"] = state.status
            diag["reported_properties_keys"] = list(
                state.properties.get("reported", {}).keys()
            )

        appliance_diagnostics.append(diag)

    return async_redact_data(
        {
            "config_entry": {
                "entry_id": entry.entry_id,
                "title": entry.title,
                "data": dict(entry.data),
            },
            "appliances": appliance_diagnostics,
        },
        REDACT_KEYS,
    )
