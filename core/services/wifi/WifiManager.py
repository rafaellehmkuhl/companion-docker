from typing import Any, Dict, List

from exceptions import FetchError, ParseError
from typedefs import SavedWifiNetwork, ScannedWifiNetwork, WifiCredentials
from wpa_supplicant import WPASupplicant


class WifiManager:
    wpa = WPASupplicant()

    def connect(self, path: Any) -> None:
        """Does the connection with wpa_supplicant service

        Arguments:
            path {[tuple/str]} -- Can be a tuple to connect (ip/port) or unix socket file
        """
        self.wpa.run(path)
        self.scanning = False

    @staticmethod
    def __decode_escaped(data: bytes) -> str:
        """Decode escaped byte array
        For more info: https://stackoverflow.com/questions/14820429/how-do-i-decodestring-escape-in-python3
        """
        return data.decode("unicode-escape").encode("latin1").decode("utf-8")

    @staticmethod
    def __dict_from_table(table: bytes) -> List[Dict[str, Any]]:
        """Create a dict from table text

        Arguments:
            table {[bytes]} -- A byte string table provided by wpa_supplicant

        Returns:
            [list of dicts] -- A list of dicts where keys are table header values
        """
        raw_lines = table.strip().split(b"\n")

        listed_lines = []
        for raw_line in raw_lines:
            listed_lines += [raw_line.split(b"\t")]

        # Create keys from header
        try:
            temp_header = listed_lines.pop(0)[0]
            header = temp_header.replace(b" ", b"").split(b"/")
        except Exception as error:
            raise ParseError("Failed creating header to dictionary.") from error

        output: List[Any] = []
        for line in listed_lines:
            output += [{}]
            try:
                for key, value in zip(header, line):
                    output[-1][WifiManager.__decode_escaped(key)] = WifiManager.__decode_escaped(value)
            except Exception as error:
                raise ParseError("Failed parsing dictionary data from table.") from error

        return output

    @staticmethod
    def __dict_from_list(data: bytes) -> Dict[str, Any]:
        """Create a dict from a value based list

        Arguments:
            data {[bytes]} -- A byte string list provided by wpa_supplicant

        Returns:
            [dict] -- Dict where which key is the variable value of the list
        """
        raw_lines = data.strip().split(b"\n")

        output = {}
        for line in raw_lines:
            try:
                key, value = line.split(b"=")
                output[WifiManager.__decode_escaped(key)] = WifiManager.__decode_escaped(value)
            except Exception as error:
                raise ParseError("Failed parsing dictionary data from list.") from error

        return output

    async def get_wifi_available(self) -> List[ScannedWifiNetwork]:
        """Get a dict from the wifi signals available"""
        if not self.scanning:
            self.scanning = True
            try:
                await self.wpa.send_command_scan(timeout=15)
            except Exception as error:
                raise FetchError("Failed to fetch wifi list.") from error
            finally:
                self.scanning = False

        data = await self.wpa.send_command_scan_results()
        networks_list = WifiManager.__dict_from_table(data)
        return [ScannedWifiNetwork(**network) for network in networks_list]

    async def get_saved_wifi_network(self) -> List[SavedWifiNetwork]:
        """Get a list of saved wifi networks"""
        try:
            data = await self.wpa.send_command_list_networks()
            networks_list = WifiManager.__dict_from_table(data)
            return [SavedWifiNetwork(**network) for network in networks_list]
        except Exception as error:
            raise FetchError("Failed to fetch saved networks list.") from error

    async def add_network(self, credentials: WifiCredentials) -> int:
        """Set network ssid and password

        Arguments:
            credentials {[WifiCredentials]} -- object containing ssid and password of the network
        """
        try:
            data = await self.wpa.send_command_add_network()
            data = data.strip()
            if not data.isdigit():
                raise RuntimeError("Failed to add new network.")

            network_number = int(data)
            await self.wpa.send_command_set_network(str(network_number), "ssid", f'"{credentials.ssid}"')
            await self.wpa.send_command_set_network(str(network_number), "psk", f'"{credentials.password}"')
            await self.wpa.send_command_save_config()
            await self.wpa.send_command_reconfigure()
            return network_number
        except Exception as error:
            raise ConnectionError("Failed to set new network.") from error

    async def connect_to_network(self, network_id: int) -> Any:
        """Connect to wifi network

        Arguments:
            ssid {str} -- Network SSID
        """
        try:
            await self.wpa.send_command_enable_network(network_id)
            await self.wpa.send_command_reconnect()
        except Exception as error:
            raise ConnectionError("Failed to connect to network.") from error

    async def status(self) -> Dict[str, Any]:
        """Check wpa_supplicant status"""
        try:
            data = await self.wpa.send_command_status()
            return WifiManager.__dict_from_list(data)
        except Exception as error:
            raise FetchError("Failed to get status from wifi manager.") from error

    async def reconfigure(self) -> None:
        """Reconfigure wpa_supplicant
        This will force the reevaluation of the conf file
        """
        try:
            await self.wpa.send_command_reconfigure()
        except Exception as error:
            raise RuntimeError("Failed to reconfigure wifi manager.") from error

    async def disconnect(self) -> None:
        """Reconfigure wpa_supplicant
        This will force the reevaluation of the conf file
        """
        try:
            await self.wpa.send_command_disconnect()
        except Exception as error:
            raise ConnectionError("Failed to disconnect from wifi network.") from error
