import asyncio
import pathlib
import subprocess
from typing import Any, Dict, List, Optional

import psutil
from loguru import logger

from exceptions import ArdupilotProcessKillFail, UnknownBoardProcedure
from mavlink_proxy.Endpoint import Endpoint
from typedefs import FlightController, PlatformType, SITLFrame


class ArduPilotBinaryManager:
    def __init__(self) -> None:
        self._ardupilot_subprocess: Optional[Any] = None
        self._running_board: Optional[FlightController] = None

        self._launch_args: Dict[str, Any] = {}

    def start_linux_binary(  # pylint: disable=too-many-arguments
        self,
        board: FlightController,
        master_endpoint: Endpoint,
        firmware_path: pathlib.Path,
        log_path: pathlib.Path,
        storage_path: pathlib.Path,
    ) -> None:
        self._launch_args = {
            "board": board,
            "master_endpoint": master_endpoint,
            "firmware_path": firmware_path,
            "log_path": log_path,
            "storage_path": storage_path,
        }
        logger.debug(f"Starting binary for board '{board.name}'.")
        if not board.type == PlatformType.Linux:
            raise ValueError("Given board is not of Linux type.")
        self._running_board = board
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
            f" --log-directory {log_path}"
            f" --storage-directory {storage_path}"
            f" -C /dev/ttyS0"
            f" -B /dev/ttyAMA1"
            f" -E /dev/ttyAMA2"
            f" -F /dev/ttyAMA3",
            shell=True,
            encoding="utf-8",
            errors="ignore",
        )

    def start_sitl_binary(
        self, board: FlightController, master_endpoint: Endpoint, firmware_path: pathlib.Path, sitl_frame: SITLFrame
    ) -> None:
        self._launch_args = {
            "board": board,
            "master_endpoint": master_endpoint,
            "firmware_path": firmware_path,
            "sitl_frame": sitl_frame,
        }
        logger.debug(f"Starting binary for board '{board.name}'.")
        if not board.type == PlatformType.SITL:
            raise ValueError("Given board is not of SITL type.")
        self._running_board = board
        # Run ardupilot inside while loop to avoid exiting after reboot command
        # pylint: disable=consider-using-with
        self._ardupilot_subprocess = subprocess.Popen(
            [
                str(firmware_path),
                "--model",
                sitl_frame.value,
                "--base-port",
                str(master_endpoint.argument),
                "--home",
                "-27.563,-48.459,0.0,270.0",
            ],
            shell=False,
            encoding="utf-8",
            errors="ignore",
        )

    async def stop_linux_binary(self, board: FlightController) -> None:
        """Stop Linux board binary, if running."""
        self._running_board = None
        await self.kill_ardupilot_process(board)

    async def stop_sitl_binary(self, board: FlightController) -> None:
        """Stop SITL binary, if running."""
        self._running_board = None
        await self.kill_ardupilot_process(board)

    async def kill_ardupilot_process(self, board: FlightController) -> None:
        # TODO: Add shutdown command on HAL_SITL and HAL_LINUX, changing terminate/prune
        # logic with a simple "self.vehicle_manager.shutdown_vehicle()"
        logger.debug("Terminating Ardupilot subprocess.")
        await self.terminate_ardupilot_subprocess()

        logger.debug("Pruning Ardupilot's system processes.")
        await self.prune_ardupilot_process(board)

    async def terminate_ardupilot_subprocess(self) -> None:
        """Terminate Ardupilot subprocess."""
        if not self._ardupilot_subprocess:
            logger.warning("Ardupilot subprocess already not running.")
            return

        self._ardupilot_subprocess.terminate()
        for _ in range(10):
            if self._ardupilot_subprocess.poll() is not None:
                logger.info("Ardupilot subprocess terminated.")
                return
            logger.debug("Waiting for process to die...")
            await asyncio.sleep(0.5)
        raise ArdupilotProcessKillFail("Could not terminate Ardupilot subprocess.")

    @staticmethod
    async def prune_ardupilot_process(board: FlightController) -> None:
        """Kill all system processes using Ardupilot's firmware file."""
        for process in ArduPilotBinaryManager.running_ardupilot_process(board.platform):
            try:
                logger.debug(f"Killing Ardupilot process {process.name()}::{process.pid}.")
                process.kill()
                await asyncio.sleep(0.5)
            except Exception as error:
                raise ArdupilotProcessKillFail(f"Could not kill {process.name()}::{process.pid}.") from error

    @staticmethod
    def running_ardupilot_process(board: FlightController) -> List[psutil.Process]:
        """Return list of all Ardupilot process running on system."""

        def is_ardupilot_process(process: psutil.Process) -> bool:
            """Checks if given process is using Ardupilot's firmware file for current platform."""
            return board.platform.value in " ".join(process.cmdline())

        return list(filter(is_ardupilot_process, psutil.process_iter()))

    async def auto_restart_ardupilot_process(self) -> None:
        """Auto-restart Ardupilot when it's not running but was supposed to."""
        while True:
            await asyncio.sleep(5.0)
            current_board = self._running_board

            if current_board is None:
                # The current_board variable is None only when binary whas not started or was explicitly stopped
                continue

            if self.is_ardupilot_process_running(current_board):
                # If the process for the current_board is running, there's no need to restart
                continue

            logger.debug(f"Restarting binary for '{current_board}' board.")
            try:
                if current_board.type == PlatformType.Linux:
                    self.stop_linux_binary(current_board)
                    self.start_linux_binary(**self._launch_args)
                    continue
                if current_board.type == PlatformType.SITL:
                    self.stop_sitl_binary(current_board)
                    self.start_sitl_binary(**self._launch_args)
                    continue
                raise UnknownBoardProcedure(f"Cannot restart. Procedure for board '{current_board}' is unknown.")
            except Exception as error:
                logger.warning(f"Could not restart ArduPilot binary. {error}")
            finally:
                self._running_board = current_board

    def is_ardupilot_process_running(self, board: FlightController) -> bool:
        return (self._ardupilot_subprocess is not None and self._ardupilot_subprocess.poll() is None) or len(
            ArduPilotBinaryManager.running_ardupilot_process(board.platform)
        ) == 0
