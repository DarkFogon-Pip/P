#!/usr/bin/env python3
"""Reverse-engineering helper for standalone Electrolux BLE food probes.

This tool scans for nearby `FS_*` probe devices, connects with Bleak, reads
interesting characteristics, and prints both raw and heuristic-decoded values.

Examples:
  python tools/electrolux_probe_dump.py --scan
  python tools/electrolux_probe_dump.py --address AA:BB:CC:DD:EE:FF --dump-services
  python tools/electrolux_probe_dump.py --address AA:BB:CC:DD:EE:FF --count 30 --interval 2
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Iterable

from bleak import BleakClient, BleakScanner

PROBE_NAME_PREFIX = "FS_"
PROBE_MANUFACTURER_ID = 1797

STANDARD_CHARS = {
    "device_name": "00002a00-0000-1000-8000-00805f9b34fb",
    "manufacturer_name": "00002a29-0000-1000-8000-00805f9b34fb",
    "hardware_revision": "00002a27-0000-1000-8000-00805f9b34fb",
    "firmware_revision": "00002a26-0000-1000-8000-00805f9b34fb",
    "software_revision": "00002a28-0000-1000-8000-00805f9b34fb",
    "battery_level": "00002a19-0000-1000-8000-00805f9b34fb",
}

PROBE_CHARS = {
    "raw_blob_1": "e1ae9001-e1ae-9e1a-e9e1-a110ea570001",
    "raw_blob_2": "e1ae9004-e1ae-9e1a-e9e1-a110ea570001",
    "temperature_limit": "e1ae9005-e1ae-9e1a-e9e1-a110ea570001",
    "temperature_channel_1": "e1ae9011-e1ae-9e1a-e9e1-a110ea570001",
    "status": "e1ae9012-e1ae-9e1a-e9e1-a110ea570001",
    "temperature_channel_2": "e1ae9013-e1ae-9e1a-e9e1-a110ea570001",
    "temperature_channel_3": "e1ae9014-e1ae-9e1a-e9e1-a110ea570001",
    "state": "e1ae9015-e1ae-9e1a-e9e1-a110ea570001",
    "rw_state": "e1ae9021-e1ae-9e1a-e9e1-a110ea570001",
}

ALL_TARGET_CHARS = {**STANDARD_CHARS, **PROBE_CHARS}


@dataclass
class ProbeCandidate:
    """Summarize a scanned BLE probe candidate."""

    address: str
    name: str
    rssi: int | None
    manufacturer_hex: str


def _now() -> str:
    """Return an ISO-ish UTC timestamp for logs."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _now_iso() -> str:
    """Return a machine-friendly UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def _format_bytes(data: bytes | None) -> str:
    """Return a compact hex representation."""
    return "" if data is None else data.hex()


def _decode_ascii(data: bytes | None) -> str | None:
    """Best-effort ASCII/UTF-8 decode."""
    if not data:
        return None
    try:
        text = data.decode("utf-8").strip("\x00").strip()
    except UnicodeDecodeError:
        return None
    return text or None


def _decode_uint(data: bytes | None) -> int | None:
    """Decode little-endian unsigned integer."""
    if not data:
        return None
    return int.from_bytes(data, byteorder="little", signed=False)


def _decode_int(data: bytes | None) -> int | None:
    """Decode little-endian signed integer."""
    if not data:
        return None
    return int.from_bytes(data, byteorder="little", signed=True)


def _decode_tenths(data: bytes | None) -> float | None:
    """Decode little-endian integer scaled by 0.1."""
    value = _decode_uint(data)
    if value is None:
        return None
    return round(value / 10, 1)


def _decode_hints(name: str, data: bytes | None) -> dict[str, object]:
    """Build a few heuristic decodes for a characteristic."""
    hints: dict[str, object] = {}
    ascii_text = _decode_ascii(data)
    uint_value = _decode_uint(data)
    int_value = _decode_int(data)
    tenths_value = _decode_tenths(data)

    if ascii_text is not None:
        hints["ascii"] = ascii_text
    if uint_value is not None:
        hints["uint"] = uint_value
    if int_value is not None and int_value != uint_value:
        hints["int"] = int_value

    if name == "battery_level" and uint_value is not None:
        hints["battery_percent"] = uint_value
    elif name.startswith("temperature") and tenths_value is not None:
        hints["celsius_tenths"] = tenths_value
    elif len(data or b"") == 1 and tenths_value is not None:
        hints["tenths_guess"] = tenths_value

    return hints


def _format_hints(hints: dict[str, object]) -> str:
    """Render hint values consistently."""
    if not hints:
        return ""
    return ", ".join(f"{key}={value}" for key, value in hints.items())


def _write_jsonl(path: Path | None, payload: dict[str, object]) -> None:
    """Append an event to a JSONL file when requested."""
    if path is None:
        return
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


async def _scan_for_probes(timeout: float) -> list[ProbeCandidate]:
    """Return nearby Electrolux probe candidates."""
    devices = await BleakScanner.discover(timeout=timeout, return_adv=True)
    candidates: list[ProbeCandidate] = []
    for address, (device, advertisement) in devices.items():
        name = advertisement.local_name or device.name or ""
        manufacturer_data = advertisement.manufacturer_data or {}
        if not name.startswith(PROBE_NAME_PREFIX):
            continue
        if PROBE_MANUFACTURER_ID not in manufacturer_data:
            continue
        candidates.append(
            ProbeCandidate(
                address=address,
                name=name,
                rssi=advertisement.rssi,
                manufacturer_hex=manufacturer_data[PROBE_MANUFACTURER_ID].hex(),
            )
        )
    return sorted(
        candidates,
        key=lambda candidate: candidate.rssi if candidate.rssi is not None else -999,
        reverse=True,
    )


async def _resolve_address(address: str | None, scan_timeout: float) -> str:
    """Resolve the target probe address."""
    if address:
        return address.upper()

    candidates = await _scan_for_probes(scan_timeout)
    if not candidates:
        raise RuntimeError(
            "No Electrolux FS_* probe found. Try powering it on and rerun with --scan."
        )
    return candidates[0].address.upper()


async def _dump_services(client: BleakClient) -> None:
    """Print full service/characteristic metadata."""
    print(f"[{_now()}] Services and characteristics:")
    for service in client.services:
        print(f"SERVICE {service.uuid} {service.description}")
        for char in service.characteristics:
            props = ",".join(char.properties)
            print(f"  CHAR {char.uuid} props={props} handle={char.handle}")
            for desc in char.descriptors:
                print(f"    DESC {desc.uuid} handle={desc.handle}")


async def _try_pair(client: BleakClient) -> None:
    """Attempt pairing but tolerate unsupported platforms."""
    try:
        paired = await client.pair(protection_level=1)
        print(f"[{_now()}] Pair result: {paired}")
    except TypeError:
        try:
            paired = await client.pair()
            print(f"[{_now()}] Pair result: {paired}")
        except Exception as err:
            print(f"[{_now()}] Pair skipped/failed: {err!r}")
    except Exception as err:
        print(f"[{_now()}] Pair skipped/failed: {err!r}")


async def _read_char(client: BleakClient, name: str, uuid: str) -> tuple[bytes | None, str | None]:
    """Read a characteristic and capture failures."""
    try:
        value = bytes(await client.read_gatt_char(uuid))
    except Exception as err:
        return None, repr(err)
    return value, None


async def _subscribe_notifications(
    client: BleakClient, uuids: Iterable[tuple[str, str]], jsonl_path: Path | None
) -> list[str]:
    """Subscribe to notify-capable chars and return active UUIDs."""
    active: list[str] = []

    async def _start(name: str, uuid: str) -> None:
        def _handler(_: int, data: bytearray) -> None:
            raw = bytes(data)
            hint_values = _decode_hints(name, raw)
            hints = _format_hints(hint_values)
            _write_jsonl(
                jsonl_path,
                {
                    "ts": _now_iso(),
                    "event": "notify",
                    "name": name,
                    "raw_hex": _format_bytes(raw),
                    "hints": hint_values,
                },
            )
            print(
                f"[{_now()}] NOTIFY {name:<22} {_format_bytes(raw):<20} {hints}".rstrip()
            )

        try:
            await client.start_notify(uuid, _handler)
        except Exception:
            return
        active.append(uuid)

    for name, uuid in uuids:
        await _start(name, uuid)

    return active


async def _poll_probe(
    address: str,
    interval: float,
    count: int,
    dump_services: bool,
    enable_notify: bool,
    jsonl_path: Path | None,
) -> None:
    """Connect to the probe and print characteristic values."""
    print(f"[{_now()}] Connecting to {address}")
    async with BleakClient(address, timeout=20.0) as client:
        print(f"[{_now()}] Connected: {client.is_connected}")
        await _try_pair(client)

        if dump_services:
            await _dump_services(client)

        notify_targets: list[tuple[str, str]] = []
        if enable_notify:
            for service in client.services:
                for char in service.characteristics:
                    if "notify" in char.properties:
                        name = next(
                            (
                                label
                                for label, candidate_uuid in ALL_TARGET_CHARS.items()
                                if candidate_uuid.lower() == char.uuid.lower()
                            ),
                            char.uuid,
                        )
                        notify_targets.append((name, char.uuid))
        active_notifications = []
        if notify_targets:
            active_notifications = await _subscribe_notifications(
                client, notify_targets, jsonl_path
            )
            if active_notifications:
                print(
                    f"[{_now()}] Subscribed to {len(active_notifications)} notification characteristic(s)"
                )

        for index in range(count):
            if index:
                await asyncio.sleep(interval)
            print(f"[{_now()}] Poll {index + 1}/{count}")
            snapshot: dict[str, object] = {
                "ts": _now_iso(),
                "event": "poll",
                "poll_index": index + 1,
                "values": {},
            }
            for name, uuid in ALL_TARGET_CHARS.items():
                raw, error = await _read_char(client, name, uuid)
                if error:
                    snapshot["values"][name] = {"error": error}
                    print(f"  {name:<22} ERROR {error}")
                    continue
                hint_values = _decode_hints(name, raw)
                snapshot["values"][name] = {
                    "raw_hex": _format_bytes(raw),
                    "hints": hint_values,
                }
                hints = _format_hints(hint_values)
                print(f"  {name:<22} {_format_bytes(raw):<20} {hints}".rstrip())
            _write_jsonl(jsonl_path, snapshot)

        for uuid in active_notifications:
            try:
                await client.stop_notify(uuid)
            except Exception:
                pass


async def _async_main(args: argparse.Namespace) -> int:
    """Run the selected mode."""
    if args.scan:
        candidates = await _scan_for_probes(args.scan_timeout)
        if not candidates:
            print(f"[{_now()}] No Electrolux FS_* probes found nearby.")
            return 1
        print(f"[{_now()}] Found {len(candidates)} Electrolux probe candidate(s):")
        for candidate in candidates:
            print(
                f"  {candidate.address}  name={candidate.name}  rssi={candidate.rssi}  mfg={candidate.manufacturer_hex}"
            )
        return 0

    address = await _resolve_address(args.address, args.scan_timeout)
    await _poll_probe(
        address=address,
        interval=args.interval,
        count=args.count,
        dump_services=args.dump_services,
        enable_notify=args.notify,
        jsonl_path=Path(args.jsonl) if args.jsonl else None,
    )
    return 0


def _build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--address", help="Probe BLE address to connect to")
    parser.add_argument(
        "--scan",
        action="store_true",
        help="Only scan for nearby Electrolux FS_* probes and print matches",
    )
    parser.add_argument(
        "--scan-timeout",
        type=float,
        default=15.0,
        help="Seconds to spend scanning when resolving a target",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="Seconds between polls after connecting",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=5,
        help="How many poll cycles to run after connecting",
    )
    parser.add_argument(
        "--dump-services",
        action="store_true",
        help="Print the full service and characteristic table after connecting",
    )
    parser.add_argument(
        "--notify",
        action="store_true",
        help="Subscribe to any notify-capable characteristics while polling",
    )
    parser.add_argument(
        "--jsonl",
        help="Optional path to append poll/notify events as JSONL",
    )
    return parser


def main() -> int:
    """CLI entrypoint."""
    args = _build_parser().parse_args()
    return asyncio.run(_async_main(args))


if __name__ == "__main__":
    raise SystemExit(main())
