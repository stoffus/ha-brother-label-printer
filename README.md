# Brother Label Printer

![Brother Label Printer icon](custom_components/brother_label_printer/brand/icon.png)

Print text labels locally from Home Assistant on a Brother **PT-P900W / PT-P900Wc**
over Wi-Fi or Ethernet. Tested with a PT-P900Wc. Text is rendered at 360 dpi;
no Brother driver, cloud account, print server, or USB connection is needed.
This is an independent community integration, not an official Brother product.

## Install with HACS

Requires **Home Assistant 2026.11.0 or later** and HACS.

1. Open HACS → menu → **Custom repositories**.
2. Add `https://github.com/stoffus/ha-brother-label-printer`, category **Integration**.
3. Find **Brother Label Printer**, download it, and restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration → Brother Label Printer**.
5. Enter the printer hostname/IP, TCP port (normally 9100), and default TZe tape width.

Setup checks TCP connectivity without printing. One printer is supported.
To change its address or default width, remove and re-add the integration.
### Upgrade from 0.3.x

Version 0.4.0 changes the integration domain from `brother_label` to
`brother_label_printer`. This is a breaking change; an existing entry cannot
be renamed in place. Record your printer address, port and default width first.

1. Install 0.4.0 and restart Home Assistant.
2. Add **Brother Label Printer** again with the same printer settings.
3. Update actions to `brother_label_printer.print_label` and
   `brother_label_printer.get_status`, and sensor references to
   `sensor.brother_label_printer_tape_width`.
4. Verify the new tape-width sensor and your scripts, then delete the old
   integration entry under Devices & services. Remove the old
   `custom_components/brother_label` folder if it remains, and restart.

Only the renamed integration is shipped in 0.4.0. The old actions have no aliases.
The new sensor has a new entity/unique ID; its history does not migrate. Existing
fridge helpers can stay as they are. The repository is now
`stoffus/ha-brother-label-printer`; update your HACS custom repository URL.

For manual installation, copy `custom_components/brother_label_printer` into your Home
Assistant `custom_components` folder and restart. `HA_SSH_HOST=your-host ./install.sh`
is an optional installer for SSH hosts running a Docker container named
`homeassistant`; it backs up and checks configuration without restarting.

Allow Home Assistant to reach the printer on **TCP 9100** (printing) and
**UDP 161** (cassette detection). SNMPv1 with community `public` must be enabled
for automatic detection. Read [Security](SECURITY.md) before network deployment.

The default width can be overridden in each print action. HACS manages the
integration only; dashboards and date helpers are configured separately.
After upgrades, restart Home Assistant to load updated Python code.

## Printing

Call this action from Developer Tools, a script, an automation, or a dashboard:

```yaml
action: brother_label_printer.print_label
data:
  text: "Köttfärs\n{{ now().strftime('%Y-%m-%d') }}"
  font_size: 64
  copies: 1
  auto_cut: true
  half_cut: false
```

Text supports Latin-1 characters, including å/ä/ö, and up to four lines.
Font size is in pixels; 64 pixels at 360 dpi is about 13 points. Oversized text
is rejected instead of clipped. Maximum image length is 300 mm and maximum
copies is 10. Supported TZe widths are 6, 9, 12, 18, 24, and 36 mm. Other tape
types, including heat-shrink tubing, are not supported. The printer validates
the configured media width. Half cut requires automatic cut. Short labels may
use extra tape because of the cutter position; feed margins are 1 mm.

An optional action response returns `status: submitted`. This means bytes were
sent, **not** that a physical label was successfully printed. This printer did
not return status to TCP queries; no paper/cover/error sensors are exposed.
Transmission failures are never automatically retried because a label could
already have reached the printer. Overlapping submissions are rejected.

## Validation

```sh
python3 -m pip install -r requirements-dev.txt
python3 -m unittest discover -s tests -v
```

Tests reconstruct the raster bitmap, check width/cut/copy framing, and exercise
TCP delivery against a local listener. They do not print physical labels.
Home Assistant integration tests run separately inside its container with a
temporary configuration. Check orientation, margins, and cutting when testing a new cassette or printer.

```sh
ssh YOUR_HA_HOST 'sudo -n docker exec -i homeassistant python -' \
  < tests/runtime_check.py
```

The runtime test uses an isolated configuration and mocks print submission.
Its optional fridge-script checks require `/config/scripts/labels.yaml`. This version targets Home
Assistant 2026.11 and its Pillow 13 dependency.

Protocol: [Brother Raster Command Reference, version 1.02](https://download.brother.com/welcome/docp100407/cv_ptp900_eng_raster_102.pdf),
especially pages 20 and 32–41. Font: [Noto Sans](https://github.com/google/fonts/tree/main/ofl/notosans),
bundled under the SIL Open Font License in `custom_components/brother_label_printer/fonts/OFL.txt`.

### Installed cassette detection (0.3.0)

`sensor.brother_label_printer_tape_width` polls the printer every 30 seconds using SNMPv1,
community `public`, UDP 161. Allow that port from Home Assistant to the printer.
The status OID is `1.3.6.1.4.1.2435.3.3.9.1.6.1.0`; width is byte 10 of Brother's
32-byte status packet. A missing cassette reports 0 mm; failed reads make the
sensor unavailable. Manual printing remains available when SNMP is offline.

`brother_label_printer.get_status` returns fresh `tape_width_mm`, `media_type`, `error`,
and `error_bytes` fields (requires a response). It does not print. Use this
response to format a label, then call `brother_label_printer.print_label` with that
`tape_width` and `verify_tape: true`. Immediately before sending, the integration
checks again and rejects cassette errors, non-TZe media, or a width mismatch.
The check and submission share the print lock. A physical cassette change in
the brief interval after the check cannot be prevented by software.

The fridge dashboard uses Auto for 12 mm single-line / 24 mm two-line dates,
and keeps explicit 12/24 mm choices as a manual fallback. No automatic printing
or retry occurs on cassette changes or detection failures.

Protocol reference: [Brother developer resources](https://atyourside.brother.it/developer-centre/developer-resources)
and [PT-P900 raster command reference](https://download.brother.com/welcome/docp100407/cv_ptp900_eng_raster_102.pdf).

## Remove

Delete the integration entry under Devices & services, then remove the download
from HACS and restart. Remove any automations or dashboards calling its actions.

## License

Code and original icon: MIT. Bundled Noto Sans: SIL Open Font License;
see `custom_components/brother_label_printer/fonts/OFL.txt`.
