# Changelog

## 0.5.0

- Detect model family from SNMP and update Home Assistant device information.
- Show detection during setup with an optional display-name override.
- Report unknown codes without guessing; keep manual printing available offline.
- Include detected model and raw model code in status responses and sensor attributes.

## 0.4.0

- Breaking: rename the domain and actions from `brother_label` to
  `brother_label_printer`, and the sensor to `sensor.brother_label_printer_tape_width`.
- Rename the repository to `ha-brother-label-printer`.
- See README upgrade steps; existing entries must be recreated under the new domain.

## 0.3.1

- First public HACS package, requiring Home Assistant 2026.11 or later.
- UI setup, local text printing and automatic installed-cassette sensor.
- Fresh cassette checks with optional width verification before submission.
- Fix print-lock handling when a caller cancels an in-flight submission.
- Add HACS/hassfest validation, original icon, MIT license and security policy.

## 0.3.0

- SNMP tape-width detection and pre-print cassette verification.

## 0.2.0

- Per-action tape-width selection.
