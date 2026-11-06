#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
host="${HA_SSH_HOST:?Set HA_SSH_HOST to your Home Assistant SSH host}"
# This host's `ha` CLI lacks Supervisor credentials. Use its running Core
# container for the same full configuration check instead.
check_config() {
  ssh "$host" 'sudo -n docker exec homeassistant python -m homeassistant --script check_config -c /config'
}
check_config
ssh "$host" 'set -eu
if [ -d /config/custom_components/brother_label_printer ]; then
  mkdir -p /config/backups
  cp -R /config/custom_components/brother_label_printer "/config/backups/brother_label_printer-$(date +%Y%m%d%H%M%S)"
fi
mkdir -p /config/custom_components/brother_label_printer'
rsync -av --exclude=__pycache__/ custom_components/brother_label_printer/ "$host:/config/custom_components/brother_label_printer/"
check_config
echo 'Installed Brother Label Printer. Restart Home Assistant, then add the integration.'
