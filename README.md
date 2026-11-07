# Brother Label Printer

![Brother Label Printer icon](custom_components/brother_label_printer/brand/icon.png)

Print text labels locally from Home Assistant on compatible Brother P-touch
network printers. The tested device is a **PT-P900Wc**; see the compatibility
table below for other models. Text is rendered at 360 dpi;
no Brother driver, cloud account, print server, or USB connection is needed.
This is an independent community integration, not an official Brother product.

## Printer compatibility

Compatibility requires both the right raster format and a supported network
connection. **Expected compatible** is an inference from Brother's documentation,
not a hardware-test result or a guarantee.

| Model | Connection for this integration | Status |
| --- | --- | --- |
| **PT-P900Wc** | Wi-Fi, raw TCP | **Tested device** used to develop this integration. Network submission and SNMP cassette detection have been exercised, including detection of 12 and 24 mm tape. |
| **PT-P900W** | Wi-Fi, raw TCP | **Expected compatible; untested as a separate model.** Covered by the raster and network-status references below. |
| **PT-P950NW** | Wi-Fi or Ethernet, raw TCP | **Expected compatible; untested.** Shares the documented raster format and network-status interface. |
| **PT-P900** (without W) | No supported native network connection | **Not supported by the current transport.** Sharing the raster format does not provide USB/serial support. |
| **PT-P910BT** | USB / Bluetooth | **Not supported by the current transport.** A related raster format does not provide USB/Bluetooth support. |

Other models, including **PT-P700, PT-P750W, PT-P710BT and the QL series**, are
**not claimed supported**. Wi-Fi, TZe tape, or a working SNMP response alone is
not enough to establish printing compatibility. No USB, Bluetooth, or external
print-server bridge has been implemented or validated here.

### Why the P900W and P950NW are candidates

The encoder implements 360 × 360 dpi, a 560-pin head, 70-byte uncompressed raster
rows, and the TZe print-area/margin values in Brother's shared
[PT-P900/P900W/P950NW/P910BT raster reference](https://download.brother.com/welcome/docp100407/cv_ptp900_eng_raster_102.pdf)
(printed pages 12, 20 and 40). Brother's
[network specifications](https://brothermobilesolutions.com/wp-content/uploads/2021/11/PT900-950-Datasheet-online-02-21-1.pdf)
list raw port 9100 for the network models and distinguish their interfaces.
The [developer network-status documentation](https://atyourside.brother.co.uk/developer-centre/developer-resources)
explicitly lists PT-P900W and PT-P950NW for the same SNMP status OID used here.
The [PT-P910BT specifications](https://support.brother.com/g/b/spec.aspx?c=us&lang=en&prod=p910bteus)
list USB and Bluetooth interfaces.

These similarities justify testing, but firmware, cutting behavior and status
reporting still need confirmation on each model. Setup detects the model family from the SNMP status packet when available.
Identification does not certify printing compatibility.

### Limits and compatibility reports

The integration renders **6, 9, 12, 18, 24 and 36 mm TZe tape**; this is not a
claim that every width has been physically tested. It does not support 3.5 mm
printing, HSe tubing, FLe die-cut media, or the printer's high-resolution mode.

To confirm another model, first read `brother_label_printer.get_status` and
compare the reported width with the cassette. Then submit one short label with
`copies: 1`, the actual `tape_width`, and `verify_tape: true`. Check the physical
text, orientation, margins and cut. A successful submission alone is not proof
of a successful print. If a send fails, inspect the printer before retrying.

Please report the exact model/suffix, firmware, connection type, tape width,
status-detection result and physical print/cut result in a GitHub issue. Omit
private network addresses, credentials and sensitive label contents. Verified
reports can move a model from **expected compatible** to **tested**.

## Install with HACS

Requires **Home Assistant 2026.11.0 or later** and HACS.

1. Open HACS → menu → **Custom repositories**.
2. Add `https://github.com/stoffus/ha-brother-label-printer`, category **Integration**.
3. Find **Brother Label Printer**, download it, and restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration → Brother Label Printer**.
5. Enter the printer hostname/IP, TCP port (normally 9100), and default TZe tape width.
6. Review the detected model. Leave the optional model-name override blank for
   automatic detection, or enter a preferred display name.

Setup checks TCP connectivity without printing. One printer is supported.
To change settings later, open **Settings → Devices & services → Brother Label
Printer → entry menu (⋮) → Reconfigure**. Edit the address, TCP port, default
width or model-name override. Changed connections are checked before saving;
failed checks leave existing settings intact. The entry and entities are retained
and reloaded automatically. With an unchanged address/port, defaults can also be
edited while the printer is offline.
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
not return status to TCP queries; readiness and errors are read separately over SNMP.
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
`error_bytes`, `errors`, `printer_status`, and `ready` fields (requires a response). It does not print. Use this
response to format a label, then call `brother_label_printer.print_label` with that
`tape_width` and `verify_tape: true`. Immediately before sending, the integration
checks again and rejects errors, busy/unknown readiness, non-TZe media, or a width mismatch.
The check and submission share the print lock. A physical cassette change in
the brief interval after the check cannot be prevented by software.

The fridge dashboard uses Auto for 12 mm single-line / 24 mm two-line dates,
and keeps explicit 12/24 mm choices as a manual fallback. No automatic printing
or retry occurs on cassette changes or detection failures.

Protocol reference: [Brother developer resources](https://atyourside.brother.it/developer-centre/developer-resources)
and [PT-P900 raster command reference](https://download.brother.com/welcome/docp100407/cv_ptp900_eng_raster_102.pdf).

## Automatic model identification

Starting with 0.5.0, setup reads the model byte in Brother's SNMP status packet.
Known codes identify PT-P900, PT-P900W, PT-P950NW and PT-P910BT. The existing
30-second status polling also refreshes the device model after setup; no extra
polling requests are needed. `get_status` and the tape sensor attributes include
`model` (detected name) and `model_code` (hexadecimal byte).

The PT-P900Wc reports the PT-P900W family code; this response does not distinguish
the `c` suffix. You can enter `PT-P900Wc` as a display override during setup.
An override takes precedence in device information, while status attributes
continue to report what the printer actually returns. It does not change raster
encoding or add printer support. Use **Reconfigure** to change the override later;
clear it to return to automatic detection.

Unknown model codes display **Unknown**. If SNMP is unavailable at startup, the
device uses the override or **Unknown**, and manual printing remains available.
A later successful poll updates automatic identification. A temporary read
failure retains the last detected device model until restart, while the tape
sensor becomes unavailable. Existing entries without an override automatically
use detection after upgrading and restarting; no reconfiguration is needed.

Model codes are documented on printed page 24 of the
[Brother raster reference](https://download.brother.com/welcome/docp100407/cv_ptp900_eng_raster_102.pdf).
The P900W entry prints ASCII `o` with an inconsistent hexadecimal value; this
integration uses `0x6f`, matching ASCII and the tested PT-P900Wc response.

## Printer status and submission history (0.6.0)

The device exposes these additional sensors:

- **Printer status**: ready, busy, error, no tape, unsupported tape, powered off,
  or unknown. Updates with the existing 30-second SNMP poll; failed reads make
  status and error sensors unavailable. A powered-off printer usually cannot
  answer SNMP and will therefore appear unavailable.
- **Printer errors**: decoded Brother flags, including cover open, cutter jam,
  tape exhausted, and overheating. The full list is in the `errors` attribute;
  raw codes remain available for diagnostics. These reports are not a guarantee
  that the next print will succeed.
- **Last submission**: idle, preparing, submitting, submitted, failed, rejected,
  cancelled, or unknown. Attributes include attempt start/completion time,
  `last_sent_at` (last successful network send), copies, width, and an explanation.
  **Submitted means sent over TCP, not confirmed physically printed.** A failed
  send can still have reached the printer: check it before retrying.

Last-submission state is restored through Home Assistant's restore-state system.
An interrupted preparing/submitting state restores as unknown, never as success.
Label text is not stored in this sensor. No automatic retry or print queue is added.
Checks rejected before the print action starts (including an overlapping request)
do not replace the active/previous attempt. The history survives integration reloads
and normal restarts; an abrupt power loss can lose the latest restore-state update.

## Remove

Delete the integration entry under Devices & services, then remove the download
from HACS and restart. Remove any automations or dashboards calling its actions.

## License

Code and original icon: MIT. Bundled Noto Sans: SIL Open Font License;
see `custom_components/brother_label_printer/fonts/OFL.txt`.
