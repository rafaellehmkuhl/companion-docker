import subprocess
import pathlib
from typing import Optional
from flight_controller.ArduPilotBinaryManager import ArduPilotBinaryManager
from loguru import logger
from mavlink_proxy.Endpoint import Endpoint
from typedefs import FlightController, PlatformType


class LinuxBinaryManager(ArduPilotBinaryManager):
    def __init__(self) -> None:
        super().__init__()
        self._log_path: Optional[pathlib.Path] = None
        self._storage_path: Optional[pathlib.Path] = None

    def set_log_path(self, log_path: pathlib.Path) -> None:
        self._log_path = log_path

    def set_storage_path(self, storage_path: pathlib.Path) -> None:
        self._storage_path = storage_path

    def start(self, board: FlightController, master_endpoint: Endpoint, firmware_path: pathlib.Path) -> None:
        logger.debug(f"Starting binary for board '{board.name}'.")
        if not self._log_path:
            raise ValueError("No path was set for the logs folder.")
        if not self._storage_path:
            raise ValueError("No path was set for the storage folder.")

        if not board.type == PlatformType.Linux:
            raise ValueError("Given board is not of Linux type.")
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

        self._ardupilot_subprocess = subprocess.Popen(
            f"{firmware_path}"
            f" -A udp:{master_endpoint.place}:{master_endpoint.argument}"
            f" --log-directory {self._log_path}"
            f" --storage-directory {self._storage_path}"
            f" -C /dev/ttyS0"
            f" -B /dev/ttyAMA1"
            f" -E /dev/ttyAMA2"
            f" -F /dev/ttyAMA3",
            shell=True,
            encoding="utf-8",
            errors="ignore",
        )
        super().start(board, master_endpoint, firmware_path)
