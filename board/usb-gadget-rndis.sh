#!/bin/sh
# USB RNDIS network gadget with Microsoft OS descriptors so Windows binds
# its inbox rndiscmp.inf driver automatically. Run as root on the board.
set -e

modprobe -r g_ether 2>/dev/null || true
modprobe libcomposite

G=/sys/kernel/config/usb_gadget/g1
[ -d "$G" ] && exit 0
mkdir -p "$G"
cd "$G"

# New VID/PID so Windows doesn't reuse the cached usbser binding for 0525:a4a2.
echo 0x1d6b > idVendor
echo 0x0104 > idProduct
echo 0xEF > bDeviceClass
echo 0x02 > bDeviceSubClass
echo 0x01 > bDeviceProtocol

mkdir -p strings/0x409
echo "PICO-PI-IMX7" > strings/0x409/product
echo "TechNexion" > strings/0x409/manufacturer

mkdir -p configs/c.1 functions/rndis.usb0

echo 1 > os_desc/use
echo 0xcd > os_desc/b_vendor_code
echo MSFT100 > os_desc/qw_sign
echo RNDIS > functions/rndis.usb0/os_desc/interface.rndis/compatible_id
echo 5162001 > functions/rndis.usb0/os_desc/interface.rndis/sub_compatible_id

ln -s functions/rndis.usb0 configs/c.1/
ln -s configs/c.1 os_desc/

ls /sys/class/udc | head -n1 > UDC
