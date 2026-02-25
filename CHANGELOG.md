# Changelog

## [0.2.0] - 2026-02-25

### Major: SO Oven Cavity-Aware Architecture

The integration now properly supports **SO (Steam Oven)** appliances using per-cavity SDK methods,
fixing all sensors that previously showed "unknown" on SO devices. OV (standard oven) appliances
continue to work as before.

### New Entities

**Sensors** (OV + SO ovens):
- **Door state** — Open/Closed (human-readable)
- **Food probe** — Inserted/Not inserted
- **Process phase** — Heating, Cooking, Preheating, Cooling down
- **Water tank** — OK, Empty, Full
- **Water tray** — Inserted/Not inserted

**Binary sensors** (OV + SO ovens):
- **Food probe inserted** — on/off
- **Water tank empty** — on/off

**Binary sensors** (SO ovens only):
- **Cleaning reminder** — on when cleaning needed
- **Descaling reminder** — on when descaling needed

**Switches:**
- **Child lock** for SO ovens (read/write via raw `childLock` API property)

### SO Oven Fixes

SO ovens use cavity-based methods (`get_current_cavity_*`) rather than top-level methods.
Previously, all SO sensors returned "unknown" because the code called OV-style methods.
Now properly creates per-cavity entities for:
- State, program, temperature, time remaining, running time
- Door state, food probe, food probe temperature
- Cavity light (switch), target temperature (number), program (select)
- Start/Stop buttons

### Human-Readable Values

All enum values are now mapped to readable text:

| Raw Value | Display |
|-----------|---------|
| `READY_TO_START` | Ready to start |
| `TRUE_FAN` | True fan |
| `CONVENTIONAL_COOKING` | Conventional |
| `NOT_SAFETY_RELEVANT_ENABLED` | Enabled (limited) |
| `PRE_HEATING` | Preheating |
| `STEAM_TANK_FULL` | Full |

Applies to: appliance state, program, remote control, process phase, door state,
food probe insertion, water tank level.

The **Program select** entity now displays human-readable names while sending
raw enum values as commands.

### Entity Count Comparison

| Device | v0.1.0 | v0.2.0 |
|--------|--------|--------|
| Oven (SO) | 12 | **21** |
| STHoven (SO) | 12 | **21** |
| Piekarnik (OV) | 12 | **19** |
| Hob (HB) | 4 | 4 |
| Cooktop (HB) | 4 | 4 |
| **Total** | **44** | **69** |

### Files Changed

- `sensor.py` — Value maps, `_map_value()` helper, SO cavity sensors, `_build_so_cavity_sensors()`
- `binary_sensor.py` — Food probe inserted, water tank empty, cleaning/descaling reminders
- `switch.py` — SO cavity light, SO child lock
- `select.py` — Human-readable program names, SO per-cavity program select
- `number.py` — SO per-cavity target temperature
- `button.py` — SO per-cavity start/stop
- `strings.json` + `translations/en.json` — New entity translation keys
- `manifest.json` — Version bump to 0.2.0

## [0.1.0] - 2026-02-24

### Initial Release

- Full Electrolux Developer SDK integration for Home Assistant
- Support for OV, SO, AC, AP, DH, WM, WD, TD, DW, RVC, CR, HD, HB appliances
- SSE push updates with deferred end-of-cycle refresh
- Config flow with token-based authentication and auto-refresh
- Diagnostics support
