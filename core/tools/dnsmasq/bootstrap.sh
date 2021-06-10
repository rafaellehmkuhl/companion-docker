#!/usr/bin/env bash

# Exit if something goes wrong
set -e

# Dnsmasq provides DHCP and DNS servers for small networks
echo "Installing dnsmasq."
apt install -y --no-install-recommends dnsmasq

# Stops dnsmasq service. It will be run independently.
echo "Stopping dnsmasq service."
service dnsmasq stop

echo "Configuring dnsmasq."
CONFIG_ORIG_PATH="/home/pi/tools/dnsmasq/dnsmasq.conf"
CONFIG_DEST_PATH="/etc/dnsmasq.conf"
[ ! -f "${CONFIG_DEST_PATH}" ] && (
    echo "Dnsmasq configuration file does not exist: ${CONFIG_DEST_PATH}"
    exit 1
)
cp $CONFIG_ORIG_PATH $CONFIG_DEST_PATH

echo "Dnsmasq configuration:"
cat $CONFIG_DEST_PATH

