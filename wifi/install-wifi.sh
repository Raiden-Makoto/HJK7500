#!/bin/sh
# Installs the brcmfmac driver and BCM4339 (AP6335) firmware on the board.
# Run as root from the directory containing modules/ and firmware/.
set -e
cd "$(dirname "$0")"
KVER=$(uname -r)

install -d /lib/modules/$KVER/extra /lib/firmware/brcm
install -m 644 modules/brcmutil.ko modules/brcmfmac.ko /lib/modules/$KVER/extra/
install -m 644 firmware/brcmfmac4339-sdio.bin firmware/brcmfmac4339-sdio.txt /lib/firmware/brcm/
depmod -a

# Load at boot; the SDIO card enumerates without a modalias match for us.
echo brcmfmac > /etc/modules-load.d/brcmfmac.conf

modprobe brcmfmac
sleep 5
dmesg | grep -i brcmf | tail -n 15
ip -br link | grep -E '^wlan' || echo "no wlan interface yet"
