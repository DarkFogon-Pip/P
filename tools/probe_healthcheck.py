#!/usr/bin/env python3
"""Quick health check for the standalone Electrolux / AEG probe path.

Examples:
  python tools/probe_healthcheck.py --ha-url http://homeassistant.local:8123 --ha-token TOKEN --probe-prefix electrolux_probe_aa_bb_cc_dd_ee_ff
  PROBE_PREFIX=electrolux_probe_aa_bb_cc_dd_ee_ff PROBE_RELAY_HOST=192.168.1.50 python tools/probe_healthcheck.py --ha-env-file .env
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import socket
from typing import Any
from urllib import error, request


@dataclass(slots=True)
class CheckResult:
    """Represent one health-check outcome."""

    status: str
    name: str
    message: str


def load_env_file(path: Path) -> dict[str, str]:
    """Parse a simple .env file into a dictionary."""
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def build_entity_ids(prefix: str) -> dict[str, str]:
    """Return the core entity IDs for a probe."""
    return {
        "battery": f"sensor.{prefix}_battery",
        "ambient": f"sensor.{prefix}_ambient_temperature",
        "food": f"sensor.{prefix}_food_probe_temperature",
    }


def parse_timestamp(value: str | None) -> datetime | None:
    """Parse a Home Assistant ISO timestamp."""
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def evaluate_sensor_payload(
    role: str,
    payload: dict[str, Any],
    *,
    stale_after_seconds: int,
    now: datetime,
) -> list[CheckResult]:
    """Evaluate one HA state payload."""
    entity_id = payload.get("entity_id", role)
    state = payload.get("state")
    attrs = payload.get("attributes", {})
    last_updated = parse_timestamp(payload.get("last_updated"))

    if state in {None, "unknown", "unavailable"}:
        return [CheckResult("warn", entity_id, "state is unavailable")]

    results: list[CheckResult] = []
    message = f"state={state}"
    if role == "battery":
        message = f"battery={state}%"
    elif role == "ambient":
        message = f"ambient={state} C"
    elif role == "food":
        source = attrs.get("temperature_source")
        if source == "raw_blob_1_float":
            message = f"food={state} C via {source}"
        elif source:
            results.append(
                CheckResult(
                    "warn",
                    entity_id,
                    f"unexpected temperature source {source}",
                )
            )
            message = f"food={state} C via {source}"
        else:
            results.append(
                CheckResult(
                    "warn",
                    entity_id,
                    "missing temperature_source attribute",
                )
            )
            message = f"food={state} C"

    status = "ok"
    if last_updated is None:
        status = "warn"
        message = f"{message}; missing last_updated"
    else:
        age = (now - last_updated.astimezone(UTC)).total_seconds()
        effective_stale_after = stale_after_seconds
        if role == "battery":
            effective_stale_after = max(stale_after_seconds, 1800)
        if age > effective_stale_after:
            status = "warn"
            message = f"{message}; stale for {int(age)}s"
        else:
            message = f"{message}; updated {int(age)}s ago"

    results.insert(0, CheckResult(status, entity_id, message))

    if role == "battery":
        try:
            battery_percent = float(state)
        except (TypeError, ValueError):
            results.append(CheckResult("warn", entity_id, "battery state is not numeric"))
        else:
            if battery_percent <= 20:
                results.append(
                    CheckResult(
                        "warn",
                        entity_id,
                        f"low battery at {battery_percent:.0f}%",
                    )
                )

    return results


def fetch_state(ha_url: str, ha_token: str, entity_id: str) -> dict[str, Any]:
    """Fetch one HA state object."""
    req = request.Request(
        f"{ha_url.rstrip('/')}/api/states/{entity_id}",
        headers={"Authorization": f"Bearer {ha_token}"},
    )
    with request.urlopen(req, timeout=15) as response:
        payload = json.loads(response.read().decode())
    return payload


def check_tcp(label: str, host: str, port: int, timeout: float) -> CheckResult:
    """Check a TCP target."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return CheckResult("ok", label, f"{host}:{port} reachable")
    except OSError as err:
        return CheckResult("error", label, f"{host}:{port} unreachable ({err})")


def resolve_ha_credentials(args: argparse.Namespace) -> tuple[str, str]:
    """Resolve HA URL and token from args, env, or an env file."""
    env_values: dict[str, str] = {}
    if args.ha_env_file:
        env_values = load_env_file(Path(args.ha_env_file))

    ha_url = args.ha_url or os.environ.get("HA_URL") or env_values.get("HA_URL")
    ha_token = args.ha_token or os.environ.get("HA_TOKEN") or env_values.get("HA_TOKEN")

    if not ha_url or not ha_token:
        raise SystemExit(
            "Need HA credentials via --ha-url/--ha-token, HA_URL/HA_TOKEN, or --ha-env-file."
        )

    return ha_url, ha_token


def resolve_runtime_config(
    args: argparse.Namespace,
) -> tuple[str, str | None]:
    """Resolve probe-specific config from args, env, or an env file."""
    env_values: dict[str, str] = {}
    if args.ha_env_file:
        env_values = load_env_file(Path(args.ha_env_file))

    probe_prefix = (
        args.probe_prefix
        or os.environ.get("PROBE_PREFIX")
        or env_values.get("PROBE_PREFIX")
    )
    if not probe_prefix:
        raise SystemExit(
            "Need the probe entity prefix via --probe-prefix or PROBE_PREFIX."
        )
    relay_host = (
        args.relay_host
        or os.environ.get("PROBE_RELAY_HOST")
        or env_values.get("PROBE_RELAY_HOST")
    )
    return probe_prefix, relay_host


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ha-url", help="Home Assistant base URL")
    parser.add_argument("--ha-token", help="Home Assistant long-lived access token")
    parser.add_argument("--ha-env-file", help="Path to a .env file with HA_URL and HA_TOKEN")
    parser.add_argument(
        "--probe-prefix",
        help="Entity ID prefix without the leading 'sensor.'",
    )
    parser.add_argument(
        "--relay-host",
        help="Optional ESPHome relay host to test",
    )
    parser.add_argument("--relay-port", type=int, default=16053, help="ESPHome relay port")
    parser.add_argument("--esphome-host", help="Optional direct ESPHome host to test")
    parser.add_argument(
        "--esphome-port", type=int, default=6053, help="Direct ESPHome API port"
    )
    parser.add_argument(
        "--stale-seconds",
        type=int,
        default=120,
        help="Warn if a sensor has not updated within this many seconds",
    )
    parser.add_argument(
        "--timeout", type=float, default=5.0, help="TCP connect timeout in seconds"
    )
    parser.add_argument("--json", action="store_true", help="Print JSON instead of text")
    return parser


def main() -> int:
    """Run the health check."""
    args = build_parser().parse_args()
    ha_url, ha_token = resolve_ha_credentials(args)
    probe_prefix, relay_host = resolve_runtime_config(args)
    entity_ids = build_entity_ids(probe_prefix)
    results: list[CheckResult] = []
    now = datetime.now(UTC)

    for role, entity_id in entity_ids.items():
        try:
            payload = fetch_state(ha_url, ha_token, entity_id)
        except error.HTTPError as err:
            results.append(
                CheckResult("error", entity_id, f"HA returned HTTP {err.code}")
            )
            continue
        except error.URLError as err:
            results.append(CheckResult("error", entity_id, f"HA unreachable ({err.reason})"))
            continue
        results.extend(
            evaluate_sensor_payload(
                role,
                payload,
                stale_after_seconds=args.stale_seconds,
                now=now,
            )
        )

    if relay_host:
        results.append(check_tcp("relay", relay_host, args.relay_port, args.timeout))
    if args.esphome_host:
        results.append(
            check_tcp("esphome", args.esphome_host, args.esphome_port, args.timeout)
        )

    if args.json:
        print(json.dumps([asdict(result) for result in results], indent=2))
    else:
        for result in results:
            print(f"[{result.status.upper()}] {result.name}: {result.message}")

    if any(result.status == "error" for result in results):
        return 2
    if any(result.status == "warn" for result in results):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
