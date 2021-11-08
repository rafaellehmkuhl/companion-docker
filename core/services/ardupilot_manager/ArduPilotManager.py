import asyncio
import os
import pathlib
from copy import deepcopy
from typing import List, Optional, Set

from commonwealth.mavlink_comm.VehicleManager import VehicleManager
from commonwealth.utils.Singleton import Singleton
from loguru import logger

from exceptions import (
    EndpointCreationFail,
    EndpointDeleteFail,
    NoBoardsConnected,
    NoPreferredBoardSet,
    UndefinedBoard,
)
from firmware.FirmwareManagement import FirmwareManager
from flight_controller.Detector import Detector as BoardDetector
from flight_controller.PlatformManager import PlatformManager
from mavlink_proxy.Endpoint import Endpoint
from mavlink_proxy.Manager import Manager as MavlinkManager
from settings import Settings
from typedefs import (
    EndpointType,
    Firmware,
    FlightController,
    Platform,
    SITLFrame,
    Vehicle,
)


class ArduPilotManager(metaclass=Singleton):
    # pylint: disable=too-many-instance-attributes
    def __init__(self) -> None:
        self.settings = Settings()
        self.settings.create_app_folders()
        self.mavlink_manager = MavlinkManager()
        self.mavlink_manager.set_logdir(self.settings.log_path)
        self.platform_manager = PlatformManager()
        self.use_sitl = False
        self._current_sitl_frame: SITLFrame = SITLFrame.UNDEFINED

        # Load settings and do the initial configuration
        if self.settings.load():
            logger.info(f"Loaded settings from {self.settings.settings_file}.")
            logger.debug(self.settings.content)
        else:
            self.settings.create_settings_file()

        self.configuration = deepcopy(self.settings.content)
        self._load_endpoints()
        self.firmware_manager = FirmwareManager(self.settings.firmware_folder, self.settings.defaults_folder)
        self.vehicle_manager = VehicleManager()

        self._current_board: Optional[FlightController] = None

    async def auto_connect_board(self) -> None:
        """Periodically check for board disconnection and reconnect it."""
        while True:
            if self._current_board is not None and not BoardDetector.is_board_connected(self._current_board):
                logger.warning("Board disconnected. Resetting connection.")
                self._current_board = None

            if self._current_board is None:
                logger.warning("Trying board connection.")
                try:
                    await asyncio.sleep(1.0)
                    await self.stop_ardupilot()
                    await asyncio.sleep(1.0)
                    await self.start_ardupilot()
                except Exception as error:
                    logger.warning(f"Could not connect board. {error}")
            await asyncio.sleep(1.0)

    def run_with_board(self) -> None:
        chosen_board = self.get_board_to_be_used()
        logger.info(f"Using {chosen_board.name} flight-controller.")

        if chosen_board.platform in [Platform.NavigatorR3, Platform.Navigator]:
            self.start_navigator(chosen_board)
            return
        if chosen_board.platform in [Platform.Pixhawk1, Platform.Pixhawk4, Platform.GenericSerial]:
            self.start_serial(chosen_board)
            return

        raise RuntimeError(f"Invalid board type: {chosen_board.platform}")

    @staticmethod
    def check_running_as_root() -> None:
        if os.geteuid() != 0:
            raise RuntimeError("ArduPilot manager needs to run with root privilege.")

    @property
    def platform(self) -> Platform:
        if not self._current_board:
            return Platform.Undefined
        return self._current_board.platform

    @property
    def current_sitl_frame(self) -> SITLFrame:
        return self._current_sitl_frame

    @current_sitl_frame.setter
    def current_sitl_frame(self, frame: SITLFrame) -> None:
        self._current_sitl_frame = frame
        logger.info(f"Setting {frame.value} as frame for SITL.")

    def start_navigator(self, board: FlightController) -> None:
        if not self.firmware_manager.is_firmware_installed(board):
            if board.platform == Platform.NavigatorR3:
                self.firmware_manager.install_firmware_from_params(Vehicle.Sub, board)
            else:
                self.install_firmware_from_file(
                    pathlib.Path("/root/companion-files/ardupilot-manager/default/ardupilot_navigator_r4")
                )

        # ArduPilot process will connect as a client on the UDP server created by the mavlink router
        master_endpoint = Endpoint(
            "Master", self.settings.app_name, EndpointType.UDPServer, "127.0.0.1", 8852, protected=True
        )
        self.platform_manager.start_navigator_process(
            master_endpoint,
            self.firmware_manager.firmware_path(board.platform),
            pathlib.Path("f{self.settings.firmware_folder}/logs/"),
            pathlib.Path("f{self.settings.firmware_folder}/storage/"),
        )

        self.start_mavlink_manager(master_endpoint)
        self._current_board = board

    def start_serial(self, board: FlightController) -> None:
        if not board.path:
            raise ValueError(f"Could not find device path for board {board.name}.")
        self.start_mavlink_manager(
            Endpoint("Master", self.settings.app_name, EndpointType.Serial, board.path, 115200, protected=True)
        )
        self._current_board = board

    def run_with_sitl(self, frame: SITLFrame = SITLFrame.VECTORED) -> None:
        board = FlightController(name="SITL", manufacturer="ArduPilot Team", platform=Platform.SITL)
        if not self.firmware_manager.is_firmware_installed(board):
            self.firmware_manager.install_firmware_from_params(Vehicle.Sub, board)
        if frame == SITLFrame.UNDEFINED:
            frame = SITLFrame.VECTORED
            logger.warning(f"SITL frame is undefined. Setting {frame} as current frame.")
        self.current_sitl_frame = frame

        # ArduPilot SITL binary will bind TCP port 5760 (server) and the mavlink router will connect to it as a client
        master_endpoint = Endpoint(
            "Master", self.settings.app_name, EndpointType.TCPServer, "127.0.0.1", 5760, protected=True
        )

        self.platform_manager.start_sitl_process(
            master_endpoint,
            self.firmware_manager.firmware_path(board.platform),
            self.current_sitl_frame,
        )

        self.start_mavlink_manager(master_endpoint)
        self._current_board = board

    def start_mavlink_manager(self, device: Endpoint) -> None:
        try:
            self.add_new_endpoints(
                {
                    Endpoint(
                        "GCS Link",
                        self.settings.app_name,
                        EndpointType.UDPServer,
                        "0.0.0.0",
                        14550,
                        protected=True,
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

    def set_preferred_board(self, board: FlightController) -> None:
        logger.info(f"Setting {board.name} as preferred flight-controller.")
        self.configuration["preferred_board"] = board.dict(exclude={"path"})
        self.settings.save(self.configuration)

    def get_preferred_board(self) -> FlightController:
        preferred_board = self.configuration.get("preferred_board")
        if not preferred_board:
            raise NoPreferredBoardSet("Preferred board not set yet.")
        return FlightController(**preferred_board)

    def get_board_to_be_used(self) -> FlightController:
        """Check if preferred board exists and is connected. If so, use it, otherwise, choose by priority."""

        connected_boards = BoardDetector.detect()
        if not connected_boards:
            raise NoBoardsConnected("No flight controller boards detected.")
        if len(connected_boards) > 1:
            logger.warning(f"More than a single board detected: {connected_boards}")

        try:
            preferred_board = self.get_preferred_board()
            logger.info(f"Preferred flight-controller is {preferred_board.name}.")
            for board in connected_boards:
                # Compare connected boards with saved board, excluding path (which can change between sessions)
                if preferred_board.dict(exclude={"path"}).items() <= board.dict().items():
                    return board
            logger.info(f"Flight-controller {preferred_board.name} not connected.")
        except NoPreferredBoardSet as error:
            logger.info(error)

        connected_boards.sort(key=lambda board: board.platform)
        return connected_boards[0]

    async def stop_ardupilot(self) -> None:
        """Stop Ardupilot processes and communication."""

        if not self.platform == Platform.SITL:
            try:
                logger.info("Disarming vehicle.")
                self.vehicle_manager.disarm_vehicle()
            except Exception as error:
                logger.warning(f"Could not disarm vehicle: {error}. Proceeding with kill.")

        logger.info("Stopping running ardupilot processes.")
        try:
            await self.platform_manager.kill_ardupilot_process()
        except Exception as error:
            logger.warning(f"Could not kill Ardupilot process. {error}")

        logger.info("Stopping Mavlink manager.")
        self.mavlink_manager.stop()

    async def start_ardupilot(self) -> None:
        try:
            if self.use_sitl:
                self.run_with_sitl(self.current_sitl_frame)
                return
            self.run_with_board()
        except Exception as error:
            logger.warning(f"Failed to start Ardupilot: {error}.")
            raise error

    async def restart_ardupilot(self) -> None:
        if self.platform in [Platform.SITL, Platform.Navigator, Platform.NavigatorR3]:
            await self.stop_ardupilot()
            await self.start_ardupilot()
            return
        self.vehicle_manager.reboot_vehicle()

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

    def reload_endpoints(self) -> None:
        try:
            persistent_endpoints = set(filter(lambda endpoint: endpoint.persistent, self.get_endpoints()))
            self._save_endpoints_to_configuration(persistent_endpoints)
            self.settings.save(self.configuration)
            self.mavlink_manager.restart()
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
                self._reset_endpoints(loaded_endpoints)
                raise EndpointCreationFail(f"Failed to add endpoint '{endpoint.name}': {error}") from error

    def remove_endpoints(self, endpoints_to_remove: Set[Endpoint]) -> None:
        """Remove multiple endpoints from the mavlink manager and save them on the configuration file."""
        loaded_endpoints = self.get_endpoints()

        protected_endpoints = set(filter(lambda endpoint: endpoint.protected, endpoints_to_remove))
        if protected_endpoints:
            raise ValueError(f"Endpoints {[e.name for e in protected_endpoints]} are protected. Aborting operation.")

        for endpoint in endpoints_to_remove:
            try:
                self.mavlink_manager.remove_endpoint(endpoint)
                logger.info(f"Deleting endpoint '{endpoint.name}' and removing it from the settings file.")
            except Exception as error:
                self._reset_endpoints(loaded_endpoints)
                raise EndpointDeleteFail(f"Failed to remove endpoint '{endpoint.name}': {error}") from error

    def get_available_firmwares(self, vehicle: Vehicle) -> List[Firmware]:
        return self.firmware_manager.get_available_firmwares(vehicle, self.platform)

    def install_firmware_from_file(self, firmware_path: pathlib.Path) -> None:
        if not self._current_board:
            raise UndefinedBoard("Running board not defined. Cannot install new firmware.")
        self.firmware_manager.install_firmware_from_file(firmware_path, self._current_board)

    def install_firmware_from_url(self, url: str) -> None:
        if not self._current_board:
            raise UndefinedBoard("Running board not defined. Cannot install new firmware.")
        self.firmware_manager.install_firmware_from_url(url, self._current_board)

    def restore_default_firmware(self) -> None:
        if not self._current_board:
            raise UndefinedBoard("Running board not defined. Cannot install new firmware.")
        self.firmware_manager.restore_default_firmware(self._current_board)
