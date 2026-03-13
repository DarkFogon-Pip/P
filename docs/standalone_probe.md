# Standalone BLE probe

This integration can add a standalone Electrolux / AEG food probe as its own
Home Assistant device, without going through the Electrolux cloud oven path.

The implementation is based on live BLE captures from an `FS_2.0` probe and is
intended for setups that already have a connectable Home Assistant Bluetooth
scanner such as an ESPHome BLE proxy.

For the short operational version, see `docs/probe_operator_cheatsheet.md`.

## What works

- Add the probe from the Electrolux config flow as `Standalone BLE probe`
- Read `Food probe temperature`, `Ambient temperature`, and `Battery`
- Keep the probe awake while an active BLE session is held open
- Expose extra diagnostic fields for reverse-engineering when needed

## Requirements

- Home Assistant must have at least one connectable Bluetooth scanner
- The probe must be close enough to that scanner to connect reliably
- The probe must be physically woken before Home Assistant can attach

## Wake and sleep behavior

The probe still behaves like a low-power accessory:

- It may stop advertising after a short idle period
- Home Assistant can keep it awake once connected
- There is currently no proven remote wake over BLE alone

In practice that means:

1. Wake the probe physically
2. Keep it near the Bluetooth proxy or host adapter
3. Let Home Assistant connect and hold the BLE session

## Official SensePro guidance

Official AEG SensePro documentation and support articles add a few useful rules
that matched our live testing:

- For liquids, immerse the probe 2-5 cm above the minimum level mark.
- For solid food, insert it through the thickest part up to at least the
  minimum level mark.
- On the left side of the hob, place the probe around the 1-3 o'clock position.
- On the right side, place it around the 9-11 o'clock position.
- If connection is weak, move the probe along the rim of the cookware.
- The hob refreshes sensor connection state about every 3 seconds.
- Keep large metal objects, cutlery, or nearby pots away from the signal path.
- For calibration, use a 180 mm pot with 1-1.5 litres of cold water on the
  left front zone and do not add salt.
- Recalibrate after moving the hob to a different altitude or replacing the
  sensor.
- Replacement sensors are paired to the hob using the five-digit code engraved
  on the sensor, then calibrated again.

Important nuance:

- The latest official TH85IH50IB manual explicitly says the Food sensor uses
  Bluetooth, is rechargeable, should be charged only with the bundled charger,
  and that one minute of charging provides up to 8 hours of operation.
- That same manual documents the LED meanings:
  - red: charging
  - red blinking: alarm / low battery
  - green: fully charged
  - blue: connecting
- It also confirms the current sensor transport specs:
  - frequency: 2400 - 2483.5 MHz
  - temperature range: 0 - 200 C
  - measurement cycle: 2 seconds
- Some other official SensePro materials still describe the sensor as
  batteryless.

Best interpretation:

- Placement, calibration, and signal-strength guidance transfers well across
  SensePro documentation.
- The latest TH85IH50IB manual is the best hardware match for the observed
  `FS_2.0` probe.
- Older "batteryless" SensePro material should be treated as partially
  compatible guidance, not the authoritative description of this exact probe.

## Entity model

Enabled by default:

- `Food probe temperature`
- `Ambient temperature`
- `Battery`

Disabled by default:

- `Internal temperature`
- `Probe temperature limit`
- `Tip temperature source`
- `Auxiliary temperature`
- `Status`
- `State`

The main `Food probe temperature` sensor is sourced from the decoded
`raw_blob_1` float payload. The older `temperature_channel_2` decode is kept
only as a fallback and diagnostic attribute.

## Recovery

If the probe shows as unavailable:

1. Wake the probe again
2. Move it close to the Bluetooth proxy
3. Confirm the Bluetooth proxy itself is online and connectable
4. Reload the Electrolux probe config entry if Home Assistant does not reattach

If the Bluetooth proxy is unavailable, fix that first. The probe integration
cannot connect until Home Assistant sees a connectable scanner again.

Calibration note:

- Calibration belongs to the hob workflow, not to the standalone BLE
  integration.
- Home Assistant can read the calibrated sensor values, but it does not trigger
  or replace SensePro calibration.
- If temperatures look systematically wrong, recalibrate on the hob first.

## Development notes

- Pure decode logic lives in `custom_components/electrolux/probe_decoder.py`
- Regression coverage for captured payloads lives in `tests/test_probe_decoder.py`
- The live reverse-engineering helper remains in `tools/electrolux_probe_dump.py`
- `tools/probe_healthcheck.py` checks the HA sensor states and optional relay /
  ESPHome TCP reachability in one command
- `tools/probe_status_summary.py` wraps the health check into a single
  GREEN / YELLOW / RED line
- `tools/electrolux_probe_status.sh` is a shell wrapper around the summary tool
  for setups that prefer exported environment variables
