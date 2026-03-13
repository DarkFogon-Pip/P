# Probe operator cheat sheet

This is the short, practical version of the standalone FS_2.0 / SensePro probe
workflow.

Use it when the probe is sleepy, flaky, or you just want the fastest path from
"where is it?" to "I have a temperature".

## Fast start

1. Charge the probe briefly if it has been idle for a while.
2. Wake it by shaking or double-tapping it until the light starts blinking.
3. Keep it close to the Bluetooth proxy or Home Assistant host.
4. Wait for Home Assistant to attach and keep the BLE session open.

## LED meanings

- red: charging
- red blinking: alarm or low battery
- green: fully charged
- blue: connecting

## Battery rule

- One minute of charging gives up to 8 hours of operation.
- If the probe looks flaky, charge it first.
- Treat low battery as a real cause of poor connectability.

## Placement rules

- Insert the probe at least to the minimum mark.
- For liquids, immerse it 2-5 cm above the minimum level mark.
- For solid food, push it through the thickest part.
- On the left side of the hob, place it around 1-3 o'clock.
- On the right side, place it around 9-11 o'clock.
- If connection is weak, move the probe along the rim of the cookware.
- Keep other metal cookware, lids, or cutlery away from the signal path.

## Calibration rules

Recalibrate:

- on first use
- after replacing the sensor
- after moving the hob to a different altitude

Calibration setup:

- use a 180 mm pot
- fill it with 1-1.5 litres of cold water
- place it on the front-left zone
- do not add salt

Important:

- Calibration is started from the hob workflow, not from Home Assistant.
- The BLE integration reads the result, but it does not perform calibration.

## What to expect in Home Assistant

- Battery should appear as a normal percentage sensor.
- Ambient temperature should move slowly.
- Food probe temperature should update roughly every 2 seconds while connected.
- Once connected, the active BLE session helps keep the probe awake.

## When the probe is unavailable

1. Charge it for a minute.
2. Wake it again by shaking or double-tapping.
3. Keep it next to the Bluetooth proxy.
4. Confirm the proxy itself is online.
5. Reload the Electrolux probe config entry if Home Assistant does not reattach.

If you have repo access, run:

- copy `tools/probe_tools.env.example` to your own local `.env`
- `python tools/probe_healthcheck.py --ha-env-file .env`
- `python tools/probe_status_summary.py --ha-env-file .env`
- `HA_URL=http://ha.local:8123 HA_TOKEN=... PROBE_PREFIX=electrolux_probe_aa_bb_cc_dd_ee_ff tools/electrolux_probe_status.sh`

## Known truths for this project

- The current TH85IH50IB manual is the best match for the observed probe.
- The probe is Bluetooth-based and rechargeable.
- Older batteryless SensePro docs are not the authoritative hardware match for
  this FS_2.0 setup.
