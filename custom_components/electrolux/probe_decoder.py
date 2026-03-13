"""Pure decoding helpers for standalone Electrolux food probes."""

from __future__ import annotations

from dataclasses import dataclass, field
import struct
from typing import Mapping


@dataclass(slots=True)
class ElectroluxProbeState:
    """Decoded state for a standalone Electrolux probe."""

    battery_level: int | None = None
    ambient_temperature: float | None = None
    probe_temperature: float | None = None
    legacy_probe_temperature: float | None = None
    secondary_temperature: float | None = None
    temperature_limit: float | None = None
    raw_blob_1_float: float | None = None
    raw_blob_2_float: float | None = None
    status: int | None = None
    state: int | None = None
    raw_values: dict[str, str] = field(default_factory=dict)


def build_probe_state(
    polled_values: Mapping[str, bytes | None],
    notify_values: Mapping[str, bytes] | None = None,
) -> ElectroluxProbeState:
    """Build the current probe state from polled and notify values."""
    raw_map: dict[str, bytes | None] = {
        **polled_values,
        **(notify_values or {}),
    }
    raw_values = {
        key: value.hex() for key, value in raw_map.items() if value is not None
    }
    raw_blob_1_float = decode_blob_float(raw_map.get("raw_blob_1"))
    raw_blob_2_float = decode_blob_float(raw_map.get("raw_blob_2"))
    legacy_probe_temperature = decode_tenths(raw_map.get("temperature_channel_2"))

    return ElectroluxProbeState(
        battery_level=decode_unsigned_int(raw_map.get("battery")),
        ambient_temperature=decode_tenths(raw_map.get("temperature_channel_1")),
        probe_temperature=raw_blob_1_float or legacy_probe_temperature,
        legacy_probe_temperature=legacy_probe_temperature,
        secondary_temperature=decode_tenths(raw_map.get("temperature_channel_3")),
        temperature_limit=decode_tenths(raw_map.get("temperature_limit")),
        raw_blob_1_float=raw_blob_1_float,
        raw_blob_2_float=raw_blob_2_float,
        status=decode_unsigned_int(raw_map.get("status")),
        state=decode_unsigned_int(raw_map.get("state")),
        raw_values=raw_values,
    )


def decode_tenths(raw_value: bytes | None) -> float | None:
    """Decode a little-endian value scaled by 0.1."""
    if not raw_value:
        return None
    return round(int.from_bytes(raw_value, "little", signed=False) / 10, 1)


def decode_unsigned_int(raw_value: bytes | None) -> int | None:
    """Decode a little-endian unsigned integer."""
    if not raw_value:
        return None
    return int.from_bytes(raw_value, "little", signed=False)


def decode_blob_float(raw_value: bytes | None) -> float | None:
    """Decode the embedded float32 from a 6-byte Electrolux blob."""
    if not raw_value or len(raw_value) != 6:
        return None
    try:
        return round(struct.unpack("<f", raw_value[1:5])[0], 3)
    except struct.error:
        return None
