#!/usr/bin/env bash

# Exit if something goes wrong
set -e

# Hostapd turns the network wireless interface into a wifi hotspot
echo "Installing hostapd."
apt install -y --no-install-recommends hostapd

echo "Configuring hostapd."
CONFIG_ORIG_PATH="/home/pi/tools/hostapd/hostapd.conf"
CONFIG_DEST_PATH="/etc/hostapd/hostapd.conf"
cp $CONFIG_ORIG_PATH $CONFIG_DEST_PATH

# Stops hostapd service. It will be run independently.
echo "Stopping hostapd service."
service hostapd stop

echo "hostapd configuration:"
cat $CONFIG_DEST_PATH

