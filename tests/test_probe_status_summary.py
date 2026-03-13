"""Tests for the compact standalone probe status wrapper."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "probe_status_summary.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("probe_status_summary", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


probe_status_summary = _load_module()


class ProbeStatusSummaryTests(unittest.TestCase):
    """Lock in the summary classification and output shape."""

    def test_summarize_green_results(self) -> None:
        """Healthy output should compress into one useful green line."""
        summary = probe_status_summary.summarize_results(
            [
                {
                    "status": "ok",
                    "name": "sensor.some_probe_battery",
                    "message": "battery=73%; updated 305s ago",
                },
                {
                    "status": "ok",
                    "name": "sensor.some_probe_ambient_temperature",
                    "message": "ambient=19.6 C; updated 1s ago",
                },
                {
                    "status": "ok",
                    "name": "sensor.some_probe_food_probe_temperature",
                    "message": "food=28.9 C via raw_blob_1_float; updated 1s ago",
                },
                {
                    "status": "ok",
                    "name": "relay",
                    "message": "192.168.1.50:16053 reachable",
                },
            ]
        )

        self.assertEqual(summary.color, "GREEN")
        self.assertEqual(summary.exit_code, 0)
        self.assertIn("food=28.9 C via raw_blob_1_float", summary.message)
        self.assertIn("192.168.1.50:16053 reachable", summary.message)

    def test_summarize_warn_results(self) -> None:
        """Warnings should degrade to yellow without pretending everything is fine."""
        summary = probe_status_summary.summarize_results(
            [
                {
                    "status": "warn",
                    "name": "sensor.some_probe_food_probe_temperature",
                    "message": "missing temperature_source attribute",
                }
            ]
        )

        self.assertEqual(summary.color, "YELLOW")
        self.assertEqual(summary.exit_code, 1)
        self.assertIn("missing temperature_source attribute", summary.message)

    def test_summarize_error_results(self) -> None:
        """Hard failures should surface as red."""
        summary = probe_status_summary.summarize_results(
            [
                {
                    "status": "error",
                    "name": "relay",
                    "message": "192.168.1.50:16053 unreachable (timed out)",
                }
            ]
        )

        self.assertEqual(summary.color, "RED")
        self.assertEqual(summary.exit_code, 2)
        self.assertIn("unreachable", summary.message)


if __name__ == "__main__":
    unittest.main()
