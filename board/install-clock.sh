#!/bin/bash
# Run from WSL: installs the ntp resync hook on the board.
set -e
cd "$(dirname "$0")"
HOST=${HOST:-pico}

sed 's/\r$//' 90-ntp-resync > /tmp/90-ntp-resync
scp -q /tmp/90-ntp-resync "$HOST:/tmp/"
ssh "$HOST" 'sudo install -m 755 /tmp/90-ntp-resync /etc/NetworkManager/dispatcher.d/90-ntp-resync'
