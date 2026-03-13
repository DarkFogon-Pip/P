# Electrolux Home Assistant Integration

[![HACS Badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub Release](https://img.shields.io/github/v/release/DarkFogon-Pip/P)](https://github.com/DarkFogon-Pip/P/releases)
[![License](https://img.shields.io/github/license/DarkFogon-Pip/P)](LICENSE)
[![GitHub Issues](https://img.shields.io/github/issues/DarkFogon-Pip/P)](https://github.com/DarkFogon-Pip/P/issues)

A feature-complete Home Assistant integration for **Electrolux**, **AEG**, **Frigidaire**, and all Electrolux Group brands — built on the [official Electrolux Group Developer SDK](https://github.com/electrolux-oss/electrolux-group-developer-sdk).

## Why this integration?

| Feature | This integration | albaintor/electrolux_status | Official (unreleased) |
|---|---|---|---|
| Native `climate` entity for AC | ✅ | ❌ (sensors only) | ❌ |
| Native `fan` entity for purifiers | ✅ | ❌ | ❌ |
| Official Electrolux SDK | ✅ | ❌ (reverse-engineered) | ✅ |
| No plaintext password stored | ✅ | ❌ | ✅ |
| Real-time push (SSE) | ✅ | ✅ (WebSocket) | ✅ |
| Reauthentication flow | ✅ | ✅ | ✅ |
| Diagnostics | ✅ | ✅ | ✅ |
| Appliance types supported | 14 | 14 | 1 (oven) |
| HACS installable | ✅ | ✅ | ❌ |
| End-of-cycle refresh fix | ✅ | ✅ | ❌ |
| Value caching (no flashing) | ✅ | ✅ | ❌ |

## Supported appliances

| Type | Models | Entities |
|---|---|---|
| **Air conditioner** | AC, CA, Azul, Bogong, Panther, Telica | Climate (temp/HVAC/fan), ambient temp sensor |
| **DAM Air conditioner** | DAM_AC | Climate (temp/HVAC/fan), ambient temp sensor |
| **Air purifier** | Fuji, Muju, PUREA9, Verbier, WELLA5, WELLA7 | Fan (speed %/presets), PM1/PM2.5/PM10/TVOC sensors, power switch |
| **Dehumidifier** | DH, Husky | Climate (humidity/fan control), humidity sensor |
| **Oven** | OV | Temp sensors, program select, target temp, cavity light, start/stop buttons |
| **Standalone food probe** | FS_2.0 family | Battery, ambient temp, food probe temp |
| **Structured oven** | SO | Same as oven, per-cavity |
| **Refrigerator** | CR | Per-cavity temp sensors & controls, door sensors, vacation mode |
| **Hob (cooktop)** | HB | State sensor, child lock switch |
| **Hood** | HD | Fan level, light intensity, grease filter sensor |
| **Dishwasher** | DW | State/phase/time sensors, program select, start/stop/pause/resume |
| **Washing machine** | WM | State/phase/time sensors, program select, start/stop/pause/resume |
| **Washer-dryer** | WD | Same as washing machine |
| **Tumble dryer** | TD | State/phase/time sensors, program select, start/stop/pause/resume |
| **Robot vacuum** | PUREi9, Gordias, Cybele, 700series | Battery, state sensors, docked binary sensor, start/stop/pause/dock buttons |

## Prerequisites

Before installing, you need credentials from the **Electrolux Developer Portal**:

1. Go to [developer.electrolux.one](https://developer.electrolux.one)
2. Sign up or log in with your **Electrolux / AEG app account**
3. Navigate to **Generate Token**
4. Copy your **API key**, **Access token**, and **Refresh token**

> **Note:** Tokens expire but are refreshed automatically. If refresh fails, Home Assistant will prompt you to re-enter new tokens.

## Installation

### Via HACS (recommended)

1. Open **HACS** in Home Assistant
2. Go to **Integrations** → **⋮** → **Custom repositories**
3. Add URL: `https://github.com/DarkFogon-Pip/P`  — Category: **Integration**
4. Search for **Electrolux** and install
5. Restart Home Assistant

### Manual

1. Download the [latest release](https://github.com/DarkFogon-Pip/P/releases/latest)
2. Extract and copy `custom_components/electrolux/` into your HA `config/custom_components/` directory
3. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for **Electrolux**
3. Choose either your Electrolux account or a standalone BLE probe
4. For cloud appliances, enter your API key, access token, and refresh token
5. Your supported devices will be discovered and added automatically

### Updating credentials

Go to **Settings** → **Devices & Services** → **Electrolux** → **Configure** to update tokens without removing and re-adding the integration.

### Standalone BLE food probe

The integration can also add a standalone Electrolux / AEG food probe over
Bluetooth. This path is separate from the Electrolux cloud API.

Requirements:

- A connectable Home Assistant Bluetooth scanner, such as an ESPHome BLE proxy
- The probe must be close enough to connect
- The probe must be physically woken before Home Assistant can attach

Enabled sensors:

- Food probe temperature
- Ambient temperature
- Battery

Diagnostic sensors remain available but are disabled by default.

For wake behavior, recovery steps, and development notes, see
[docs/standalone_probe.md](docs/standalone_probe.md).
For the short operator flow, see
[docs/probe_operator_cheatsheet.md](docs/probe_operator_cheatsheet.md).
For a one-command status check, copy `tools/probe_tools.env.example` to a local
`.env` and run `python tools/probe_healthcheck.py --ha-env-file .env`.
For a compact green/yellow/red summary, use
`python tools/probe_status_summary.py --ha-env-file .env`.

## Entities per appliance

### Air conditioner

| Entity | Type | Notes |
|---|---|---|
| Air conditioner | `climate` | HVAC modes, fan modes, target temperature |
| Ambient temperature | `sensor` | Current room temperature from the unit |
| State | `sensor` | Diagnostic — disabled by default |
| Alerts | `sensor` | Diagnostic — disabled by default |
| Connection | `binary_sensor` | Diagnostic |

### Air purifier

| Entity | Type | Notes |
|---|---|---|
| Air purifier | `fan` | Speed % (maps to fan speed 1–9) and preset modes |
| Power | `switch` | Turn on/off |
| Mode | `select` | Auto / Manual / etc. |
| PM2.5 / PM10 / PM1 | `sensor` | Only shown if supported by model |
| TVOC | `sensor` | Only shown if supported by model |
| Alerts | `sensor` | Diagnostic — disabled by default |
| Connection | `binary_sensor` | Diagnostic |

### Washing machine / Washer-dryer / Tumble dryer

| Entity | Type | Notes |
|---|---|---|
| State | `sensor` | OFF / RUNNING / PAUSED / END_OF_CYCLE / etc. |
| Cycle phase | `sensor` | Current wash phase |
| Time remaining | `sensor` | Diagnostic — seconds until cycle end |
| Program | `sensor` | Currently running program |
| Program | `select` | Choose program before starting |
| Start / Stop / Pause / Resume | `button` | Cycle control |
| Door | `binary_sensor` | Open / Closed |
| Alerts | `sensor` | Diagnostic — disabled by default |
| Remote control | `sensor` | Diagnostic — disabled by default |
| Connection | `binary_sensor` | Diagnostic |

### Oven

| Entity | Type | Notes |
|---|---|---|
| State | `sensor` | IDLE / RUNNING / etc. |
| Temperature | `sensor` | Current cavity temperature |
| Food probe temperature | `sensor` | If food probe is inserted |
| Target temperature | `number` | Set oven temperature |
| Program | `select` | Choose cooking program |
| Time remaining | `sensor` | Diagnostic |
| Running time | `sensor` | Diagnostic — disabled by default |
| Remote control | `sensor` | Diagnostic — disabled by default |
| Cavity light | `switch` | Turn cavity light on/off |
| Start / Stop | `button` | Oven control |
| Door | `binary_sensor` | Open / Closed |
| Alerts | `sensor` | Diagnostic — disabled by default |
| Connection | `binary_sensor` | Diagnostic |

### Refrigerator

| Entity | Type | Notes |
|---|---|---|
| {cavity} temperature | `sensor` | Per cavity (fridge, freezer, etc.) |
| {cavity} target temperature | `number` | Per cavity temperature control |
| {cavity} door | `binary_sensor` | Per cavity door state |
| Vacation mode | `switch` | Enable/disable vacation/holiday mode |
| UI lock | `sensor` | Diagnostic — disabled by default |
| Alerts | `sensor` | Diagnostic — disabled by default |
| Connection | `binary_sensor` | Diagnostic |

### Robot vacuum

| Entity | Type | Notes |
|---|---|---|
| State | `sensor` | Current vacuum state |
| Battery | `sensor` | Battery percentage |
| Docked | `binary_sensor` | Whether the vacuum is on its dock |
| Start / Stop / Pause / Dock | `button` | Control commands |
| Alerts | `sensor` | Diagnostic — disabled by default |
| Connection | `binary_sensor` | Diagnostic |

## Technical details

- **Protocol:** Server-Sent Events (SSE) for real-time cloud push — no polling
- **Update model:** Per-appliance `DataUpdateCoordinator`, updated via SSE events
- **End-of-cycle fix:** Automatically schedules a full state refresh 70 seconds after `timeToEnd` reaches 0, working around a known Electrolux API issue
- **Token management:** Tokens are automatically refreshed before expiry; new tokens are persisted back to the config entry
- **Dynamic discovery:** New appliances added to your Electrolux account are detected when the SSE stream reconnects

## Troubleshooting

### "Authentication failed" during setup
- Tokens expire — go to [developer.electrolux.one/generateToken](https://developer.electrolux.one/generateToken) and generate fresh ones
- Make sure you logged into the developer portal with the **same account** as your Electrolux app

### Appliance shows as unavailable
- Check your appliance is connected to Wi-Fi and visible in the Electrolux app
- The `Connection` binary sensor will show the actual connectivity state

### Entities missing for my appliance
- Open an issue with your appliance type/model — we can add support
- Enable diagnostics (**Settings** → **Devices & Services** → **Electrolux** → your device → **Download diagnostics**) and attach the output

### Getting diagnostic data
Go to **Settings** → **Devices & Services** → find your Electrolux device → **Download diagnostics**. Sensitive data (tokens, serial numbers, appliance IDs) is automatically redacted.

## Contributing

Pull requests are welcome! Please open an issue first to discuss what you'd like to change.

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup instructions.

## License

MIT — see [LICENSE](LICENSE) for details.
