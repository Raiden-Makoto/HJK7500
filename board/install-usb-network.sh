#!/bin/sh
# Installs the USB RNDIS gadget as a boot service and gives usb0 a fixed
# address on the Windows Internet Connection Sharing subnet. Run as root.
set -e
cd "$(dirname "$0")"

install -m 755 usb-gadget-rndis.sh /usr/local/sbin/usb-gadget-rndis.sh
install -m 644 usb-gadget-rndis.service /etc/systemd/system/usb-gadget-rndis.service
install -m 644 86-usb0-managed.rules /etc/udev/rules.d/86-usb0-managed.rules
systemctl daemon-reload
systemctl enable usb-gadget-rndis.service

nmcli con delete usb-host >/dev/null 2>&1 || true
nmcli con add type ethernet ifname usb0 con-name usb-host \
    ipv4.method manual ipv4.addresses 192.168.137.2/24 \
    ipv4.gateway 192.168.137.1 ipv4.dns 192.168.137.1 \
    ipv6.method ignore connection.autoconnect yes
