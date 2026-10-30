#!/bin/bash
# Run from WSL: copies the app, font and .env to the PICO and (re)starts it.
set -e
cd "$(dirname "$0")/.."
HOST=${HOST:-pico}

stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
mkdir -p "$stage/hjk7500/app" "$stage/hjk7500/luminator-horizon"
cp app/*.py app/hjk7500.service app/hjk7500-backlight.service app/fluxbox-apps "$stage/hjk7500/app/"
[ -f app/.env ] && cp app/.env "$stage/hjk7500/app/"
cp luminator-horizon/*.otf luminator-horizon/*.txt "$stage/hjk7500/luminator-horizon/"
sed -i 's/\r$//' "$stage"/hjk7500/app/* "$stage"/hjk7500/luminator-horizon/*.txt

ssh "$HOST" 'rm -rf ~/hjk7500.new'
scp -qr "$stage/hjk7500" "$HOST:hjk7500.new"
ssh "$HOST" 'set -e
    rm -rf ~/hjk7500 && mv ~/hjk7500.new ~/hjk7500
    chmod 600 ~/hjk7500/app/.env 2>/dev/null || true
    sudo install -D -m 644 ~/hjk7500/app/fluxbox-apps ~/.fluxbox/apps
    pkill -USR2 -x fluxbox || true
    # The Xfce panel stacks above the board and covers its top 27 px; the
    # board is the only thing on screen, so skip the Xfce desktop entirely.
    sudo sed -i "s/^startxfce4 &/# startxfce4 \&  # disabled by hjk7500/" ~/.fluxbox/startup
    sudo install -m 644 ~/hjk7500/app/hjk7500.service ~/hjk7500/app/hjk7500-backlight.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable hjk7500.service hjk7500-backlight.service >/dev/null 2>&1
    sudo systemctl restart hjk7500.service
    sleep 3
    systemctl --no-pager --lines=8 status hjk7500.service | tail -n 9'
