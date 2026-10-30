#!/bin/sh
# Installs Tailscale from its official apt repository. Run as root.
set -e
export DEBIAN_FRONTEND=noninteractive

# TechNexion's image ships a Vivaldi source without its signing key, which
# makes every apt-get update fail.
[ -f /etc/apt/sources.list.d/vivaldi.list ] && \
    mv /etc/apt/sources.list.d/vivaldi.list /etc/apt/sources.list.d/vivaldi.list.disabled

apt-get update -q
apt-get install -y -q curl ca-certificates

. /etc/os-release
curl -fsSL "https://pkgs.tailscale.com/stable/ubuntu/$VERSION_CODENAME.noarmor.gpg" \
    > /usr/share/keyrings/tailscale-archive-keyring.gpg
curl -fsSL "https://pkgs.tailscale.com/stable/ubuntu/$VERSION_CODENAME.tailscale-keyring.list" \
    > /etc/apt/sources.list.d/tailscale.list

apt-get update -q
apt-get install -y -q tailscale

# The TechNexion kernel has no iptables/nftables support, so kernel-mode
# tailscaled can't start. Userspace networking still accepts inbound SSH.
sed -i 's/^FLAGS=.*/FLAGS="--tun=userspace-networking"/' /etc/default/tailscaled
systemctl reset-failed tailscaled || true
systemctl enable tailscaled
systemctl restart tailscaled
tailscale version
