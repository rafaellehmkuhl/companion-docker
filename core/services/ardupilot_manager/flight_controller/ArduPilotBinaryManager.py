import abc
import asyncio
import pathlib
from typing import Any, Dict, List, Optional

import psutil
from loguru import logger

from exceptions import ArdupilotProcessKillFail
from mavlink_proxy.Endpoint import Endpoint
from typedefs import FlightController


class ArduPilotBinaryManager(metaclass=abc.ABCMeta):
    def __init__(self) -> None:
        self._ardupilot_subprocess: Optional[Any] = None
        self._running_board: Optional[FlightController] = None
        self._master_endpoint: Optional[Endpoint] = None
        self._firmware_path: Optional[pathlib.Path] = None

        self._launch_args: Dict[str, Any] = {}

    @abc.abstractmethod
    def start(self, board: FlightController, master_endpoint: Endpoint, firmware_path: pathlib.Path) -> None:
        self._running_board = board
        self._master_endpoint = master_endpoint
        self._firmware_path = firmware_path

        logger.debug("Starting watchdog for ArduPilot binary manager.")
        try:
            asyncio.get_running_loop()
            asyncio.create_task(self.auto_restart_ardupilot_process(), name="ardupilot-binary-watchdog")
        except Exception:
            logger.warning("No async loop detected. Watchdog won't be running.")

    async def stop(self) -> None:
        """Stop board binary, if running."""
        try:
            await self.kill_ardupilot_process(self._running_board)
        except Exception:
            pass
        finally:
            self._running_board = None
            self._master_endpoint = None
            self._firmware_path = None

            logger.debug("Stopping watchdog for ArduPilot binary manager.")
            try:
                asyncio.get_running_loop()
                (task,) = [task for task in asyncio.all_tasks() if task.get_name() == "ardupilot-binary-watchdog"]
                task.cancel()
            except Exception:
                logger.warning("No async loop detected. Watchdog won't be running.")

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
                self.stop()
                if None in [self._running_board, self._master_endpoint, self._firmware_path]:
                    raise ValueError("One or more start parameters is not defined.")
                self.start(self._running_board, self._master_endpoint, self._firmware_path)
            except Exception as error:
                logger.warning(f"Could not restart ArduPilot binary. {error}")
            finally:
                self._running_board = current_board

    def is_ardupilot_process_running(self, board: FlightController) -> bool:
        return (self._ardupilot_subprocess is not None and self._ardupilot_subprocess.poll() is None) or len(
            ArduPilotBinaryManager.running_ardupilot_process(board.platform)
        ) == 0
