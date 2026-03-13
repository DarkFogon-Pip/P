"""Tests for the standalone probe health-check helper."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest
from datetime import UTC, datetime


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "probe_healthcheck.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("probe_healthcheck", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


probe_healthcheck = _load_module()


class ProbeHealthcheckTests(unittest.TestCase):
    """Cover the pure helper logic used by the health-check CLI."""

    def test_load_env_file_parses_key_values(self) -> None:
        """Simple dotenv parsing should ignore comments and blank lines."""
        tmp = Path(self.id().replace(".", "_") + ".env")
        try:
            tmp.write_text(
                "# comment\nHA_URL=http://ha.local:8123\nHA_TOKEN=abc123\n\n",
                encoding="utf-8",
            )
            values = probe_healthcheck.load_env_file(tmp)
        finally:
            if tmp.exists():
                tmp.unlink()

        self.assertEqual(values["HA_URL"], "http://ha.local:8123")
        self.assertEqual(values["HA_TOKEN"], "abc123")

    def test_food_sensor_reports_expected_source(self) -> None:
        """The main food sensor should validate the remapped blob source."""
        now = datetime(2026, 3, 13, 9, 30, 15, tzinfo=UTC)
        payload = {
            "entity_id": "sensor.test_food",
            "state": "35.8",
            "last_updated": "2026-03-13T09:30:10+00:00",
            "attributes": {"temperature_source": "raw_blob_1_float"},
        }

        results = probe_healthcheck.evaluate_sensor_payload(
            "food",
            payload,
            stale_after_seconds=120,
            now=now,
        )

        self.assertEqual(results[0].status, "ok")
        self.assertIn("via raw_blob_1_float", results[0].message)
        self.assertEqual(len(results), 1)

    def test_food_sensor_warns_on_old_mapping(self) -> None:
        """Unexpected temperature sources should stand out immediately."""
        now = datetime(2026, 3, 13, 9, 30, 15, tzinfo=UTC)
        payload = {
            "entity_id": "sensor.test_food",
            "state": "29.4",
            "last_updated": "2026-03-13T09:30:10+00:00",
            "attributes": {"temperature_source": "temperature_channel_2"},
        }

        results = probe_healthcheck.evaluate_sensor_payload(
            "food",
            payload,
            stale_after_seconds=120,
            now=now,
        )

        self.assertEqual(results[0].status, "ok")
        self.assertEqual(results[1].status, "warn")
        self.assertIn("unexpected temperature source", results[1].message)

    def test_unavailable_state_warns(self) -> None:
        """Unavailable probe states should not be treated as healthy."""
        now = datetime(2026, 3, 13, 9, 30, 15, tzinfo=UTC)
        results = probe_healthcheck.evaluate_sensor_payload(
            "ambient",
            {
                "entity_id": "sensor.test_ambient",
                "state": "unavailable",
                "last_updated": "2026-03-13T09:30:10+00:00",
                "attributes": {},
            },
            stale_after_seconds=120,
            now=now,
        )

        self.assertEqual(results[0].status, "warn")
        self.assertIn("unavailable", results[0].message)

    def test_battery_uses_more_relaxed_staleness_window(self) -> None:
        """Battery should not warn just because it updates less often than temperature."""
        now = datetime(2026, 3, 13, 9, 30, 15, tzinfo=UTC)
        payload = {
            "entity_id": "sensor.test_battery",
            "state": "73",
            "last_updated": "2026-03-13T09:26:00+00:00",
            "attributes": {},
        }

        results = probe_healthcheck.evaluate_sensor_payload(
            "battery",
            payload,
            stale_after_seconds=180,
            now=now,
        )

        self.assertEqual(results[0].status, "ok")
        self.assertIn("battery=73%", results[0].message)


if __name__ == "__main__":
    unittest.main()
