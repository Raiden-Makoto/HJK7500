#!/bin/bash
# Run from WSL after build-brcmfmac.sh: copies the driver and firmware to the
# PICO and installs them.
set -e
cd "$(dirname "$0")"
OUT=${OUT:-$HOME/src/pico-build}

stage=$(mktemp -d)
mkdir -p "$stage/modules"
cp "$OUT"/modules/*.ko "$stage/modules/"
cp -r firmware install-wifi.sh wifi-powersave-off.conf "$stage/"
sed -i 's/\r$//' "$stage/install-wifi.sh" "$stage/wifi-powersave-off.conf"

ssh pico 'rm -rf /tmp/wifi'
scp -qr "$stage" pico:/tmp/wifi
rm -rf "$stage"
ssh pico 'sudo sh /tmp/wifi/install-wifi.sh'
