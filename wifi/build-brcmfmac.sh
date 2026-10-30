#!/bin/bash
# Cross-builds the Broadcom brcmfmac Wi-Fi driver for the PICO-PI-IMX7's
# TechNexion 5.15.71 kernel, using the board's own /proc/config.gz.
set -eo pipefail

SRC=${SRC:-$HOME/src/linux-tn-imx}
OUT=${OUT:-$HOME/src/pico-build}
export ARCH=arm CROSS_COMPILE=arm-linux-gnueabi-

[ -f "$OUT/board.config" ] || ssh pico 'zcat /proc/config.gz' > "$OUT/board.config"

cd "$SRC"
cp "$OUT/board.config" .config
# Not a git checkout; keep the release string exactly "5.15.71" like the board.
touch .scmversion
scripts/config --module BRCMUTIL --module BRCMFMAC \
    --enable BRCMFMAC_PROTO_BCDC --enable BRCMFMAC_SDIO \
    --disable BRCMFMAC_USB --disable BRCMFMAC_PCIE --disable BRCM_TRACING \
    --disable WERROR
# libahci doesn't build with GCC 13; the i.MX7 has no SATA, and dropping it
# doesn't change the symbol CRCs brcmfmac links against.
scripts/config --disable SATA_AHCI_PLATFORM --disable AHCI_IMX
make olddefconfig >/dev/null

# MODVERSIONS needs the full vmlinux build to produce Module.symvers.
# The Vivante GPU driver trips GCC 13's -Werror=enum-int-mismatch.
make -j"$(nproc)" KCFLAGS="-Wno-error=enum-int-mismatch" zImage modules 2>&1 | tail -n 5

echo "kernelrelease: $(make -s kernelrelease)"
mkdir -p "$OUT/modules"
cp drivers/net/wireless/broadcom/brcm80211/brcmutil/brcmutil.ko \
   drivers/net/wireless/broadcom/brcm80211/brcmfmac/brcmfmac.ko "$OUT/modules/"
cp Module.symvers "$OUT/"
ls -l "$OUT/modules"
