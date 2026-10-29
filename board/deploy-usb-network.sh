#!/bin/bash
# Run from WSL: copies board/ to the PICO and installs the USB network setup.
set -e
cd "$(dirname "$0")/.."
sed -i 's/\r$//' board/*.sh board/*.service board/*.rules
scp -qr board pico:/tmp/
# Detached: recreating the usb0 profile drops this SSH session mid-install.
ssh pico 'sudo setsid sh /tmp/board/install-usb-network.sh > /tmp/install-usb-network.log 2>&1 < /dev/null &'
