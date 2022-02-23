from ctypes import Union
from commonwealth.utils.DHCPServerManager import Dnsmasq as DHCPServerManager
from ipaddress import IPv4Address
import shutil
from loguru import logger
import pathlib
import tempfile
import subprocess
from typing import Any, List, Optional
import shlex
import time
import re
from enum import Enum

import psutil

class HostapdFrequency(str, Enum):
    """Valid hostapd frequency modes."""

    HW_2_4 = "g" # Hostapd id for 2.4 GHz mode
    HW_5_0 = "a" # Hostapd id for 5.0 GHz mode

    @staticmethod
    def mode_from_channel(channel: int) -> "HostapdFrequency":
        def valid_2_4_channels() -> List[int]:
            return list(range(1,15))
        return HostapdFrequency.HW_2_4 if channel in valid_2_4_channels() else HostapdFrequency.HW_5_0


class HotspotManager:
    AP_INTERFACE_NAME="uap0"
    AP_SSID="BlueOS"
    AP_PASSPHRASE="blueosbr"

    def __init__(self, base_interface: str, ipv4_gateway: IPv4Address) -> None:
        self._subprocess: Optional[Any] = None

        if base_interface not in psutil.net_if_stats():
            raise ValueError(f"Base interface '{base_interface}' not found.")
        self._base_interface = base_interface

        self._ipv4_gateway = ipv4_gateway

        self._dhcp_server = Optional[DHCPServerManager] = None

        binary_path = shutil.which(self.binary_name())
        if binary_path is None:
            raise ValueError("Hostapd binary not found on system's PATH.")

        self._binary = pathlib.Path(binary_path)
        assert self.is_binary_working()

        self._create_temp_config_file()

    @staticmethod
    def binary_name() -> str:
        return "hostapd"

    def binary(self) -> pathlib.Path:
        return self._binary

    def is_binary_working(self) -> bool:
        if self.binary() is None:
            return False

        try:
            subprocess.check_output([self.binary(), "--help"])
            return True
        except subprocess.CalledProcessError as error:
            logger.error(f"Invalid binary: {error}")
            return False

    def base_interface_channel(self) -> Optional[int]:
        iw_output = subprocess.check_output(shlex.split(f"iw {self._base_interface} info"))
        return int(re.findall("channel \d*", str(iw_output))[0].split()[1])

    def desired_channel(self) -> int:
        return self.base_interface_channel() or 1

    def _create_virtual_interface(self):
        logger.info("Deleting virtual access point interface (if exists).")
        subprocess.Popen(shlex.split(f"iw dev {self.AP_INTERFACE_NAME} del"))
        time.sleep(3)

        logger.info("Create virtual access point interface.")
        subprocess.Popen(shlex.split(f"iw dev {self._base_interface} interface add {self.AP_INTERFACE_NAME} type __ap"))
        time.sleep(3)

        logger.info("Starting virtual access point interface.")
        subprocess.Popen(shlex.split(f"ifconfig {self.AP_INTERFACE_NAME} up"))
        time.sleep(3)

    def command_list(self) -> List[Union[str, pathlib.Path]]:
        """List of arguments to be used in the command line call.
        Refer to https://thekelleys.org.uk/dnsmasq/docs/dnsmasq-man.html for details about each argument."""

        return [
            self.binary(),
            self.config_path()
        ]

    def start(self) -> None:
        logger.info("Starting hotspot.")
        try:
            # pylint: disable=consider-using-with
            self._subprocess = subprocess.Popen(self.command_list(), shell=False, encoding="utf-8", errors="ignore")
            if not self._dhcp_server:
                self._dhcp_server = DHCPServerManager(self.AP_INTERFACE_NAME, self._ipv4_gateway)
            self._dhcp_server.start()
        except Exception as error:
            raise RuntimeError(f"Unable to start hotspot. {error}") from error

    def stop(self) -> None:
        logger.info("Stopping hotspot.")
        if self.is_running():
            assert self._subprocess is not None
            self._subprocess.kill()
            if not self._dhcp_server:
                logger.warning("Cannot stop DHCP server for hotspot, as was already not running.")
                return
            self._dhcp_server.stop()
        else:
            logger.info("Tried to stop hostpot, but it was already not running.")

    def restart(self) -> None:
        self.stop()
        self.start()

    def is_running(self) -> bool:
        return self._subprocess is not None and self._subprocess.poll() is None

    def config_path(self) -> pathlib.Path:
        temp_dir = pathlib.Path(tempfile.tempdir)
        return temp_dir.joinpath("hostapd.conf")

    def hostapd_config(self) -> str:
        desired_channel = self.desired_channel()

        return f'''
        # WiFi interface to be used (in this case a virtual one)
        interface={self.AP_INTERFACE_NAME}
        # Channel (frequency) of the access point
        channel={desired_channel}
        # SSID broadcasted by the access point
        ssid={self.AP_SSID}
        # Passphrase for the access point
        wpa_passphrase={self.AP_PASSPHRASE}
        # Use the 2.4GHz band
        hw_mode={HostapdFrequency.mode_from_channel(desired_channel).value}
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

    def _create_temp_config_file(self) -> None:
        logger.info(f"Saving temporary hostapd config file on {self.config_path()}")
        with open(self.config_path(), "w", encoding="utf-8") as f:
            f.write(self.hostapd_config())
