#!/usr/bin/env python3

from loguru import logger
import pathlib
import tempfile
import subprocess
from typing import List, Optional
import shlex
import time
import re
from enum import Enum

class HostapdFrequency(str, Enum):
    """Valid hostapd frequency modes."""

    HW_2_4 = "g" # Hostapd id for 2.4 GHz mode
    HW_5_0 = "a" # Hostapd id for 5.0 GHz mode

def hostapd_config(ap_interface: str, ap_channel: int, ap_ssid: str, ap_passphrase: str, ap_hw_mode: HostapdFrequency) -> str:
    return f'''
    # WiFi interface to be used (in this case a virtual one)
    interface={ap_interface}
    # Channel (frequency) of the access point
    channel={ap_channel}
    # SSID broadcasted by the access point
    ssid={ap_ssid}
    # Passphrase for the access point
    wpa_passphrase={ap_passphrase}
    # Use the 2.4GHz band
    hw_mode={ap_hw_mode.value}
    # Accept all MAC addresses
    macaddr_acl=0
    # Use WPA authentication
    auth_algs=1
    # Require clients to know the network name
    ignore_broadcast_ssid=0
    # Use WPA2
    wpa=2
    # Use a pre-shared key
    wpa_key_mgmt=WPA-PSK
    wpa_pairwise=TKIP
    rsn_pairwise=CCMP
    '''

def interface_running_channel(interface_name: str) -> Optional[int]:
    iw_output = subprocess.check_output(shlex.split(f"iw {interface_name} info"))
    return int(re.findall("channel \d*", str(iw_output))[0].split()[1])

def mode_from_channel(channel: int) -> HostapdFrequency:
    def valid_2_4_channels() -> List[int]:
        return list(range(1,15))
    return HostapdFrequency.HW_2_4 if channel in valid_2_4_channels() else HostapdFrequency.HW_5_0

AP_INTERFACE_NAME="uap0"
desired_channel = interface_running_channel('wlan0') or 1

filled_config = hostapd_config(
    ap_interface=AP_INTERFACE_NAME,
    ap_channel=desired_channel,
    ap_hw_mode=mode_from_channel(desired_channel),
    ap_ssid="BlueOS",
    ap_passphrase="blueosbr",
)
logger.info(f"Hostapd configuration: {filled_config}")

temp_dir = pathlib.Path(tempfile.tempdir)
hostapd_config_path = temp_dir.joinpath("hostapd.conf")

logger.info(f"Saving temporary hostapd config file on {hostapd_config_path}")
with open(hostapd_config_path, "w", encoding="utf-8") as f:
    f.write(filled_config)


logger.info("Deleting virtual access point interface (if exists).")
subprocess.Popen(shlex.split(f"iw dev {AP_INTERFACE_NAME} del"))
time.sleep(3)

logger.info("Create virtual access point interface.")
subprocess.Popen(shlex.split(f"iw dev wlan0 interface add {AP_INTERFACE_NAME} type __ap"))
time.sleep(3)

logger.info("Starting virtual access point interface.")
subprocess.Popen(shlex.split(f"ifconfig {AP_INTERFACE_NAME} up"))
time.sleep(3)

logger.info("Starting hotspot with hostapd.")
subprocess.Popen(shlex.split(f"hostapd {hostapd_config_path} "))
time.sleep(3)

logger.info("Killing DHCP server (dnsmasq) if running.")
subprocess.Popen(shlex.split(f"pkill -9 dnsmasq"))
time.sleep(3)

logger.info("Starting DHCP server (dnsmasq).")
subprocess.Popen(shlex.split(f"dnsmasq --no-daemon --conf-file=/home/pi/services/cable_guy/api/settings/dnsmasq.conf"))
time.sleep(3)

