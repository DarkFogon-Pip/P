#!/usr/bin/env python3
"""Compact summary wrapper for the standalone Electrolux probe health check.

Examples:
  PROBE_PREFIX=electrolux_probe_aa_bb_cc_dd_ee_ff python tools/probe_status_summary.py --ha-url http://homeassistant.local:8123 --ha-token TOKEN
  PROBE_PREFIX=electrolux_probe_aa_bb_cc_dd_ee_ff PROBE_RELAY_HOST=192.168.1.50 python tools/probe_status_summary.py --ha-env-file .env
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import sys


@dataclass(slots=True)
class Summary:
    """Hold the final health summary."""

    color: str
    message: str
    exit_code: int


def parse_results(raw_json: str) -> list[dict[str, str]]:
    """Parse the health-check JSON output."""
    payload = json.loads(raw_json)
    if not isinstance(payload, list):
        raise ValueError("Expected a list of health-check results")
    return payload


def summarize_results(results: list[dict[str, str]]) -> Summary:
    """Convert detailed results into a single status line."""
    color = "GREEN"
    exit_code = 0
    parts: list[str] = []

    for result in results:
        status = result["status"]
        name = result["name"]
        message = result["message"]
        if status == "error":
            color = "RED"
            exit_code = 2
        elif status == "warn" and color != "RED":
            color = "YELLOW"
            exit_code = 1

        if "food_probe_temperature" in name or name.endswith("_food"):
            parts.append(message)
        elif "ambient_temperature" in name or name.endswith("_ambient"):
            parts.append(message)
        elif "battery" in name:
            parts.append(message)
        elif name == "relay":
            parts.append(message)
        elif status != "ok":
            parts.append(f"{name}: {message}")

    if not parts:
        parts.append("no probe data returned")

    return Summary(color=color, message=" | ".join(parts), exit_code=exit_code)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ha-url", help="Home Assistant base URL")
    parser.add_argument("--ha-token", help="Home Assistant long-lived access token")
    parser.add_argument("--ha-env-file", help="Path to a .env file with HA_URL and HA_TOKEN")
    parser.add_argument("--probe-prefix", help="Entity ID prefix without the leading 'sensor.'")
    parser.add_argument("--relay-host", help="Optional ESPHome relay host to test")
    parser.add_argument("--relay-port", type=int, default=16053)
    parser.add_argument("--stale-seconds", type=int, default=180)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument(
        "--healthcheck-path",
        help="Path to probe_healthcheck.py; defaults to the sibling file",
    )
    parser.add_argument("--json", action="store_true", help="Print raw JSON too")
    return parser


def main() -> int:
    """Run the summary wrapper."""
    args = build_parser().parse_args()
    healthcheck_path = (
        Path(args.healthcheck_path)
        if args.healthcheck_path
        else Path(__file__).with_name("probe_healthcheck.py")
    )

    cmd = [
        sys.executable,
        str(healthcheck_path),
        "--json",
        "--stale-seconds",
        str(args.stale_seconds),
        "--timeout",
        str(args.timeout),
    ]
    if args.ha_url:
        cmd.extend(["--ha-url", args.ha_url])
    if args.ha_token:
        cmd.extend(["--ha-token", args.ha_token])
    if args.ha_env_file:
        cmd.extend(["--ha-env-file", args.ha_env_file])
    if args.probe_prefix:
        cmd.extend(["--probe-prefix", args.probe_prefix])
    if args.relay_host:
        cmd.extend(["--relay-host", args.relay_host])
    if args.relay_port:
        cmd.extend(["--relay-port", str(args.relay_port)])

    completed = subprocess.run(cmd, capture_output=True, text=True)

    if completed.returncode == 2 and not completed.stdout.strip():
        print(f"RED healthcheck invocation failed: {completed.stderr.strip()}")
        return 2

    try:
        results = parse_results(completed.stdout)
    except Exception as err:
        print(f"RED unable to parse healthcheck output: {err}")
        if completed.stdout.strip():
            print(completed.stdout.strip())
        if completed.stderr.strip():
            print(completed.stderr.strip())
        return 2

    summary = summarize_results(results)
    print(f"{summary.color} {summary.message}")
    if args.json:
        print(json.dumps(results, indent=2))
    return max(summary.exit_code, completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
