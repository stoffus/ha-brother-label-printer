# Security

Report suspected vulnerabilities privately using GitHub's **Security → Report a
vulnerability** tab. Do not put credentials, label contents, or network captures
in public issues. Only the latest release is maintained.

This integration is intended for a trusted local network. Raw TCP printing and
SNMPv1 (`public`, read-only requests) are unencrypted and do not authenticate the
printer. Restrict TCP 9100 and UDP 161 to Home Assistant and trusted management
hosts; do not expose them to the Internet. Network access to the printer can
permit printing outside Home Assistant. Status verification is an operational
check, not a security authentication mechanism.

Printing uses Home Assistant's authenticated action API. Users and automations
allowed to call actions can consume tape. The integration adds no anonymous
HTTP endpoints and has no cloud telemetry. It accepts text, not image uploads,
file paths, templates to execute, or raw printer commands. Templates are handled
by Home Assistant before the action is called. Label text is not intentionally
logged by this integration, but Home Assistant traces can retain action data.

See [the pre-publication review](docs/security-audit.md) for scope and limitations.
