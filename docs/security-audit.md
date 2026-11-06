# Pre-publication security review — 2026-11-06

Scope: integration Python, configuration flow, service schemas, rendering,
TCP transport, SNMP parser, bundled font, installer, public repository contents,
and validation workflow. This is a source review with automated checks, not
an independent penetration test or a guarantee of security.

## Findings and fixes

- **Concurrent submission on cancellation:** a cancelled action could release
  its lock while the executor thread still sent bytes. Submission now shields
  the worker and retains the lock until it finishes. A regression test cancels
  a blocked submission and checks that the lock remains held.
- **Private deployment details:** removed the private printer hostname from
  defaults and test fixtures; the public repository starts from a clean snapshot,
  without private Git history. The SSH installer now requires an explicit host.
- GitHub Actions use immutable commit references and read-only repository
  permissions. Upstream HACS/hassfest actions still select their own container
  images, so these dependencies require ongoing review. They do not use `pull_request_target` or receive deployment secrets.

## Checks

- Bandit scan of integration code: no findings.
- Gitleaks redacted scan of the publication working tree: no secrets found.
- pip-audit against Pillow 13.0.0, PySNMP 7.1.27 and the installed pyasn1
  dependency (0.6.5): no known vulnerabilities returned on the review date.
- Raster tests cover framing, copy limits, overflow, rejected characters,
  Swedish text, and exact delivery to a local TCP listener.
- Isolated Home Assistant runtime checks cover configuration, validation,
  cassette mismatch/error/timeout rejection, no retries, concurrency, unload,
  and cancellation. Print transport is mocked; no physical labels are printed.

Pillow is supplied by the required Home Assistant version. PySNMP declares a
minimum version so Home Assistant can apply dependency security updates without
a conflicting integration pin. The versions above are the audited test baseline.

## Security boundaries and residual risks

- Text is rasterized; it cannot become raw printer commands. No user-selected
  paths, image decoders, subprocesses, shell execution, or dynamic code loading
  are exposed through actions. The font is bundled and not user-selectable.
- Input is bounded to 500 characters, four lines, 16–160 pixel font size,
  300 mm image length and 1–10 copies. Only configured tape widths are accepted.
- Only the configured printer destination is used. Print actions cannot choose
  arbitrary network hosts or URLs. Setup is managed through Home Assistant's
  config flow; it can connect to an administrator-specified TCP endpoint.
- SNMP checks a fixed OID, response length and packet header. SNMP has a five
  second outer timeout and no retries; TCP connect/send timeouts are bounded.
- TCP 9100 and SNMPv1 are unencrypted and unauthenticated at the device level.
  An attacker on the LAN can spoof status or print directly. Restrict network
  access. Status checks do not authenticate a printer or guarantee tape width
  if someone swaps the cassette between checking and submission.
- Home Assistant action permissions are the authorization boundary. Repeated
  authenticated print calls can consume tape; this integration is not a quota
  or billing system. Never retry ambiguous failures automatically.
- No telemetry, remote font download or external URL fetch occurs during normal
  operation. Home Assistant downloads declared Python dependencies at setup.
  Traces may retain label text; do not share them without redaction.
- Dependency results reflect published advisories at the time of scanning;
  future vulnerabilities and Home Assistant's wider dependency tree are outside
  this review. The bundled font retains its SIL Open Font License.
