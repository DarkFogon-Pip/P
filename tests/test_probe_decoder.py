"""Regression tests for standalone Electrolux probe decoding."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import struct
import sys
import unittest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "electrolux"
    / "probe_decoder.py"
)


def _load_probe_decoder():
    spec = importlib.util.spec_from_file_location("electrolux_probe_decoder", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load probe decoder from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


probe_decoder = _load_probe_decoder()


def _probe_blob(value: float) -> bytes:
    """Build a realistic 6-byte probe float payload."""
    return bytes([0x04]) + struct.pack("<f", value) + bytes([0xFA])


class ProbeDecoderTests(unittest.TestCase):
    """Lock in the reverse-engineered standalone probe mapping."""

    def test_decode_blob_float_matches_captured_samples(self) -> None:
        """Known blob payloads from the trace decode to stable temperatures."""
        self.assertEqual(
            probe_decoder.decode_blob_float(bytes.fromhex("043333b341fa")), 22.4
        )
        self.assertEqual(
            probe_decoder.decode_blob_float(bytes.fromhex("0466660642fa")), 33.6
        )
        self.assertEqual(
            probe_decoder.decode_blob_float(bytes.fromhex("049a990542fa")), 33.4
        )

    def test_build_probe_state_prefers_tip_blob_over_legacy_channel(self) -> None:
        """The main food temperature should come from raw_blob_1 when present."""
        state = probe_decoder.build_probe_state(
            {
                "battery": bytes.fromhex("51"),
                "raw_blob_1": _probe_blob(56.2),
                "raw_blob_2": _probe_blob(30.348),
                "temperature_channel_1": bytes.fromhex("d3"),
                "temperature_channel_2": bytes.fromhex("8500"),
                "temperature_channel_3": bytes.fromhex("3d01"),
                "temperature_limit": bytes.fromhex("d007"),
                "status": bytes.fromhex("00"),
                "state": bytes.fromhex("2b"),
            }
        )

        self.assertEqual(state.battery_level, 81)
        self.assertEqual(state.ambient_temperature, 21.1)
        self.assertEqual(state.probe_temperature, 56.2)
        self.assertEqual(state.legacy_probe_temperature, 13.3)
        self.assertEqual(state.secondary_temperature, 31.7)
        self.assertEqual(state.temperature_limit, 200.0)
        self.assertEqual(state.raw_blob_1_float, 56.2)
        self.assertEqual(state.raw_blob_2_float, 30.348)
        self.assertEqual(state.status, 0)
        self.assertEqual(state.state, 43)
        self.assertEqual(state.raw_values["raw_blob_1"], _probe_blob(56.2).hex())

    def test_build_probe_state_falls_back_to_legacy_channel(self) -> None:
        """The old channel-2 decode remains as a fallback when no blob is present."""
        state = probe_decoder.build_probe_state(
            {
                "temperature_channel_1": bytes.fromhex("d8"),
                "temperature_channel_2": bytes.fromhex("2601"),
                "temperature_channel_3": bytes.fromhex("3d01"),
            }
        )

        self.assertEqual(state.ambient_temperature, 21.6)
        self.assertEqual(state.probe_temperature, 29.4)
        self.assertEqual(state.legacy_probe_temperature, 29.4)
        self.assertEqual(state.secondary_temperature, 31.7)
        self.assertIsNone(state.raw_blob_1_float)

    def test_notify_values_override_stale_polled_values(self) -> None:
        """Notifications should win over older polled data when rebuilding state."""
        state = probe_decoder.build_probe_state(
            {
                "raw_blob_1": bytes.fromhex("0466660642fa"),
                "temperature_channel_1": bytes.fromhex("da"),
            },
            {
                "raw_blob_1": _probe_blob(74.2),
                "temperature_channel_1": bytes.fromhex("d9"),
            },
        )

        self.assertEqual(state.probe_temperature, 74.2)
        self.assertEqual(state.raw_blob_1_float, 74.2)
        self.assertEqual(state.ambient_temperature, 21.7)
        self.assertEqual(state.raw_values["raw_blob_1"], _probe_blob(74.2).hex())


if __name__ == "__main__":
    unittest.main()
