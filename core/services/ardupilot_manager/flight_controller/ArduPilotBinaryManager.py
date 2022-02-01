import asyncio
import pathlib
import subprocess
from typing import Any, Dict, List, Optional

import psutil
from loguru import logger

from exceptions import ArdupilotProcessKillFail, UndefinedPlatform, UnsupportedPlatform
from mavlink_proxy.Endpoint import Endpoint
from typedefs import Platform, SITLFrame


class ArduPilotBinaryManager:
    def __init__(self) -> None:
        self.ardupilot_subprocess: Optional[Any] = None
        self._running_platform: Platform = Platform.Undefined
        self.should_be_running = False

        self.launch_args: Dict[str, Any] = {}

    def start_navigator_process(
        self,
        platform: Platform,
        endpoint: Endpoint,
        firmware_path: pathlib.Path,
        log_path: pathlib.Path,
        storage_path: pathlib.Path,
    ) -> None:
        self.launch_args = {
            "platform": platform,
            "endpoint": endpoint,
            "firmware_path": firmware_path,
            "log_path": log_path,
            "storage_path": storage_path,
        }
        if not platform in [Platform.NavigatorR3, Platform.NavigatorR5]:
            raise ValueError("Platform specified is not a Navigator.")
        self.should_be_running = True
        self._running_platform = platform
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

        self.ardupilot_subprocess = subprocess.Popen(
            f"{firmware_path}"
            f" -A udp:{endpoint.place}:{endpoint.argument}"
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

    def start_sitl_process(self, endpoint: Endpoint, firmware_path: pathlib.Path, sitl_frame: SITLFrame) -> None:
        self.launch_args = {
            "endpoint": endpoint,
            "firmware_path": firmware_path,
            "sitl_frame": sitl_frame,
        }
        self.should_be_running = True
        self._running_platform = Platform.SITL
        # Run ardupilot inside while loop to avoid exiting after reboot command
        # pylint: disable=consider-using-with
        self.ardupilot_subprocess = subprocess.Popen(
            [
                str(firmware_path),
                "--model",
                sitl_frame.value,
                "--base-port",
                str(endpoint.argument),
                "--home",
                "-27.563,-48.459,0.0,270.0",
            ],
            shell=False,
            encoding="utf-8",
            errors="ignore",
        )

    async def kill_ardupilot_process(self) -> None:
        # TODO: Add shutdown command on HAL_SITL and HAL_LINUX, changing terminate/prune
        # logic with a simple "self.vehicle_manager.shutdown_vehicle()"

        if self._running_platform == Platform.Undefined:
            raise UndefinedPlatform("No Ardupilot platform running. Aborting kill.")

        logger.debug("Terminating Ardupilot subprocess.")
        await self.terminate_ardupilot_subprocess()

        logger.debug("Pruning Ardupilot's system processes.")
        await self.prune_ardupilot_processes()

        self.should_be_running = False
        self._running_platform = Platform.Undefined

    @staticmethod
    def running_ardupilot_processes(platform: Platform) -> List[psutil.Process]:
        """Return list of all Ardupilot process running on system."""

        def is_ardupilot_process(process: psutil.Process) -> bool:
            """Checks if given process is using Ardupilot's firmware file for current platform."""
            return platform.value in " ".join(process.cmdline())

        return list(filter(is_ardupilot_process, psutil.process_iter()))

    async def terminate_ardupilot_subprocess(self) -> None:
        """Terminate Ardupilot subprocess."""
        if not self.ardupilot_subprocess:
            logger.warning("Ardupilot subprocess already not running.")
            return

        self.ardupilot_subprocess.terminate()
        for _ in range(10):
            if self.ardupilot_subprocess.poll() is not None:
                logger.info("Ardupilot subprocess terminated.")
                return
            logger.debug("Waiting for process to die...")
            await asyncio.sleep(0.5)
        raise ArdupilotProcessKillFail("Could not terminate Ardupilot subprocess.")

    async def prune_ardupilot_processes(self) -> None:
        """Kill all system processes using Ardupilot's firmware file."""
        for process in ArduPilotBinaryManager.running_ardupilot_processes(self._running_platform):
            try:
                logger.debug(f"Killing Ardupilot process {process.name()}::{process.pid}.")
                process.kill()
                await asyncio.sleep(0.5)
            except Exception as error:
                raise ArdupilotProcessKillFail(f"Could not kill {process.name()}::{process.pid}.") from error

    def ardupilot_process_not_running(self) -> bool:
        return (self.ardupilot_subprocess is not None and self.ardupilot_subprocess.poll() is not None) or len(
            ArduPilotBinaryManager.running_ardupilot_processes(self._running_platform)
        ) != 0

    async def auto_restart_ardupilot_process(self) -> None:
        """Auto-restart Ardupilot when it's not running but was supposed to."""
        while True:
            await asyncio.sleep(5.0)
            current_platform = self._running_platform
            needs_restart = self.should_be_running and self.ardupilot_process_not_running()

            if not needs_restart:
                continue

            logger.debug("Restarting ardupilot...")
            try:
                await self.kill_ardupilot_process()
            except Exception as error:
                logger.warning(f"Could not kill Ardupilot process. {error}")
            try:
                if current_platform in [Platform.NavigatorR3, Platform.NavigatorR5]:
                    self.start_navigator_process(**self.launch_args)
                    continue
                if current_platform == Platform.SITL:
                    self.start_sitl_process(**self.launch_args)
                    continue
                raise UnsupportedPlatform(f"Supported platforms are Navigator and SITL. Received {current_platform}.")
            except Exception as error:
                logger.warning(f"Could not start Ardupilot process. {error}")

            self.should_be_running = True
