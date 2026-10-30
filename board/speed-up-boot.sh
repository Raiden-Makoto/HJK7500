#!/bin/sh
# Run on the board with sudo. Turns off services the departure board doesn't
# use; snapd alone delays graphical.target by ~6 s. Undo with `systemctl unmask`.
set -e

systemctl disable --now snapd.service snapd.socket snapd.seeded.service apport.service
systemctl mask snapd.service snapd.socket snapd.seeded.service apport.service
