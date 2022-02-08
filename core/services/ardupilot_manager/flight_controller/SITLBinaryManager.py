import subprocess
import pathlib
from typing import Optional
from flight_controller.ArduPilotBinaryManager import ArduPilotBinaryManager
from loguru import logger
from mavlink_proxy.Endpoint import Endpoint
from typedefs import FlightController, PlatformType, SITLFrame


class SITLBinaryManager(ArduPilotBinaryManager):
    def __init__(self) -> None:
        super().__init__()
        self._sitl_frame: Optional[SITLFrame]

    def set_sitl_frame(self, sitl_frame: SITLFrame) -> None:
        self._sitl_frame = sitl_frame

    def start(self, board: FlightController, master_endpoint: Endpoint, firmware_path: pathlib.Path) -> None:
        logger.debug(f"Starting binary for board '{board.name}'.")
        if not self._sitl_frame:
            raise ValueError("No SITL frame set.")
        if not board.type == PlatformType.SITL:
            raise ValueError("Given board is not of SITL type.")
        # Run ardupilot inside while loop to avoid exiting after reboot command
        # pylint: disable=consider-using-with
        self._ardupilot_subprocess = subprocess.Popen(
            [
                str(firmware_path),
                "--model",
                self._sitl_frame.value,
                "--base-port",
                str(master_endpoint.argument),
                "--home",
                "-27.563,-48.459,0.0,270.0",
            ],
            shell=False,
            encoding="utf-8",
            errors="ignore",
        )
        super().start(board, master_endpoint, firmware_path)
