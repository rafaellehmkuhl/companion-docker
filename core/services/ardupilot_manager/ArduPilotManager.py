import os
import shutil
import subprocess
import time
from copy import deepcopy
from typing import Any, List, Optional, Set, Tuple

from loguru import logger

from firmware_download.FirmwareDownload import FirmwareDownload, Platform, Vehicle
from flight_controller_detector.Detector import Detector as BoardDetector
from flight_controller_detector.Detector import FlightControllerType
from mavlink_proxy.Endpoint import Endpoint, EndpointType
from mavlink_proxy.Manager import Manager as MavlinkManager
from settings import Settings
from Singleton import Singleton


class ArduPilotManager(metaclass=Singleton):
    def __init__(self) -> None:
        self.settings = Settings()
        self.mavlink_manager = MavlinkManager()
        self.mavlink_manager.set_logdir(self.settings.log_path)

        # Load settings and do the initial configuration
        if self.settings.load():
            logger.info(f"Loaded settings from {self.settings.settings_file}.")
            logger.debug(self.settings.content)
        else:
            self.settings.create_settings_file()

        self.configuration = deepcopy(self.settings.content)
        self._load_endpoints()
        self.subprocess: Optional[Any] = None
        self.firmware_download = FirmwareDownload()

    def run_with_board(self) -> None:
        ArduPilotManager.check_running_as_root()

        while not self.start_board(BoardDetector.detect()):
            logger.warning("Flight controller board not detected, will try again.")
            time.sleep(2)

    @staticmethod
    def check_running_as_root() -> None:
        if os.geteuid() != 0:
            raise RuntimeError("ArduPilot manager needs to run with root privilege.")

    def start_navigator(self) -> None:
        firmware = os.path.join(self.settings.firmware_path, "ardusub")
        if not os.path.isfile(firmware):
            temporary_file = self.firmware_download.download(Vehicle.Sub, Platform.Navigator)
            assert temporary_file, "Failed to download navigator binary."
            shutil.move(str(temporary_file), firmware)

        # ArduPilot process will connect as a client on the UDP server created by the mavlink router
        master_endpoint = Endpoint(
            "Master", self.settings.app_name, EndpointType.UDPServer, "127.0.0.1", 8852, protected=True
        )

        # Run ardupilot inside while loop to avoid exiting after reboot command
        ## Can be changed back to a simple command after https://github.com/ArduPilot/ardupilot/issues/17572
        ## gets fixed.
        # pylint: disable=consider-using-with
        #
        # The mapping of serial ports works as in the following table:
        #
        # |    ArduSub   |       Navigator         |
        # | -C = Serial1 | Serial1 => /dev/ttyS0   |
        # | -B = Serial3 | Serial3 => /dev/ttyAMA1 |
        # | -E = Serial4 | Serial4 => /dev/ttyAMA2 |
        # | -F = Serial5 | Serial5 => /dev/ttyAMA3 |
        #
        # The first column comes from https://ardupilot.org/dev/docs/sitl-serial-mapping.html

        self.subprocess = subprocess.Popen(
            "while true; do "
            f"{firmware} -A udp:{master_endpoint.place}:{master_endpoint.argument}"
            f" --log-directory {self.settings.firmware_path}/logs/"
            f" --storage-directory {self.settings.firmware_path}/storage/"
            f" -C /dev/ttyS0"
            f" -B /dev/ttyAMA1"
            f" -E /dev/ttyAMA2"
            f" -F /dev/ttyAMA3"
            "; sleep 1; done",
            shell=True,
            encoding="utf-8",
            errors="ignore",
        )

        self.start_mavlink_manager(master_endpoint)

    def start_serial(self, device: str) -> None:
        self.start_mavlink_manager(
            Endpoint("Master", self.settings.app_name, EndpointType.Serial, device, 115200, protected=True)
        )

    def run_with_sitl(self, vehicle: str = "vectored") -> None:
        firmware = os.path.join(self.settings.firmware_path, "sitl")
        if not os.path.exists(firmware):
            temporary_file = self.firmware_download.download(Vehicle.Sub, Platform.SITL)
            assert temporary_file, "Failed to download SITL binary."
            shutil.move(str(temporary_file), firmware)

        # ArduPilot SITL binary will bind TCP port 5760 (server) and the mavlink router will connect to it as a client
        master_endpoint = Endpoint(
            "Master", self.settings.app_name, EndpointType.TCPServer, "127.0.0.1", 5760, protected=True
        )
        # The mapping of serial ports works as in the following table:
        #
        # |    ArduSub   |       Navigator         |
        # | -C = Serial1 | Serial1 => /dev/ttyS0   |
        # | -B = Serial3 | Serial3 => /dev/ttyAMA1 |
        # | -E = Serial4 | Serial4 => /dev/ttyAMA2 |
        # | -F = Serial5 | Serial5 => /dev/ttyAMA3 |
        #
        # pylint: disable=consider-using-with
        self.subprocess = subprocess.Popen(
            [
                firmware,
                "--model",
                vehicle,
                "--base-port",
                str(master_endpoint.argument),
                "--home",
                "-27.563,-48.459,0.0,270.0",
                "-C",
                "/dev/ttyS0",
                "-B",
                "/dev/ttyAMA1",
                "-E",
                "/dev/ttyAMA2",
                "-F",
                "/dev/ttyAMA3",
            ],
            shell=False,
            encoding="utf-8",
            errors="ignore",
        )

        self.start_mavlink_manager(master_endpoint)

    def start_mavlink_manager(self, device: Endpoint) -> None:
        try:
            self.add_new_endpoints(
                {
                    Endpoint(
                        "GCS Link", self.settings.app_name, EndpointType.UDPClient, "192.168.2.1", 14550, protected=True
                    )
                }
            )
            self.add_new_endpoints(
                {
                    Endpoint(
                        "MAVLink2Rest",
                        self.settings.app_name,
                        EndpointType.UDPClient,
                        "127.0.0.1",
                        14000,
                        protected=True,
                    )
                }
            )
        except Exception as error:
            logger.error(f"Could not create default GCS endpoint: {error}")
        self.mavlink_manager.set_master_endpoint(device)
        self.mavlink_manager.start()

    def start_board(self, boards: List[Tuple[FlightControllerType, str]]) -> bool:
        if not boards:
            return False

        if len(boards) > 1:
            logger.warning(f"More than a single board detected: {boards}")

        # Sort by priority
        boards.sort(key=lambda tup: tup[0].value)

        flight_controller_type, place = boards[0]
        logger.info(f"Board in use: {flight_controller_type.name}.")

        if FlightControllerType.Navigator == flight_controller_type:
            self.start_navigator()
            return True
        if FlightControllerType.Serial == flight_controller_type:
            self.start_serial(place)
            return True
        raise RuntimeError("Invalid board type: {boards}")

    def restart(self) -> None:
        self.mavlink_manager.restart()

    def _get_configuration_endpoints(self) -> Set[Endpoint]:
        return {Endpoint(**endpoint) for endpoint in self.configuration.get("endpoints") or []}

    def _save_endpoints_to_configuration(self, endpoints: Set[Endpoint]) -> None:
        self.configuration["endpoints"] = list(map(Endpoint.as_dict, endpoints))

    def _load_endpoints(self) -> None:
        """Load endpoints from the configuration file to the mavlink manager."""
        for endpoint in self._get_configuration_endpoints():
            try:
                self.mavlink_manager.add_endpoint(endpoint)
            except Exception as error:
                logger.error(f"Could not load endpoint {endpoint}: {error}")

    def _reset_endpoints(self, endpoints: Set[Endpoint]) -> None:
        try:
            self.mavlink_manager.clear_endpoints()
            self.mavlink_manager.add_endpoints(endpoints)
            logger.info("Resetting endpoints to previous state.")
        except Exception as error:
            logger.error(f"Error resetting endpoints: {error}")

    def _update_endpoints(self) -> None:
        try:
            persistent_endpoints = set(filter(lambda endpoint: endpoint.persistent, self.get_endpoints()))
            self._save_endpoints_to_configuration(persistent_endpoints)
            self.settings.save(self.configuration)
            self.restart()
        except Exception as error:
            logger.error(f"Error updating endpoints: {error}")

    def get_endpoints(self) -> Set[Endpoint]:
        """Get all endpoints from the mavlink manager."""
        return self.mavlink_manager.endpoints()

    def add_new_endpoints(self, new_endpoints: Set[Endpoint]) -> None:
        """Add multiple endpoints to the mavlink manager and save them on the configuration file."""
        loaded_endpoints = self.get_endpoints()

        for endpoint in new_endpoints:
            try:
                self.mavlink_manager.add_endpoint(endpoint)
                logger.info(f"Adding endpoint '{endpoint.name}' and saving it to the settings file.")
            except Exception as error:
                logger.error(f"Failed to add endpoint '{endpoint.name}': {error}")
                self._reset_endpoints(loaded_endpoints)
                raise

        self._update_endpoints()

    def remove_endpoints(self, endpoints_to_remove: Set[Endpoint]) -> None:
        """Remove multiple endpoints from the mavlink manager and save them on the configuration file."""
        loaded_endpoints = self.get_endpoints()

        protected_endpoints = set(filter(lambda endpoint: endpoint.protected, endpoints_to_remove))
        if protected_endpoints:
            raise ValueError(f"Endpoints {protected_endpoints} are protected. Aborting operation.")

        for endpoint in endpoints_to_remove:
            try:
                self.mavlink_manager.remove_endpoint(endpoint)
                logger.info(f"Deleting endpoint '{endpoint.name}' and removing it from the settings file.")
            except Exception as error:
                logger.error(f"Failed to remove endpoint '{endpoint.name}': {error}")
                self._reset_endpoints(loaded_endpoints)
                raise

        self._update_endpoints()
