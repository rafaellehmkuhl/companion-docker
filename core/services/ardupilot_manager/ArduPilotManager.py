import pathlib
from copy import deepcopy
from typing import List, Optional, Set

from commonwealth.mavlink_comm.VehicleManager import VehicleManager
from commonwealth.utils.Singleton import Singleton
from loguru import logger

from exceptions import (
    BoardIsNotConnected,
    BoardIsStillConnected,
    EndpointAlreadyExists,
    NoAvailableBoard,
    UnknownBoardProcedure,
)
from firmware.FirmwareManagement import FirmwareManager
from flight_controller.ArduPilotBinaryManager import ArduPilotBinaryManager
from flight_controller_detector.Detector import Detector as BoardDetector
from mavlink_proxy.Endpoint import Endpoint
from mavlink_proxy.Manager import Manager as MavlinkManager
from settings import Settings
from typedefs import (
    EndpointType,
    Firmware,
    FlightController,
    PlatformType,
    SITLFrame,
    Vehicle,
)


class ArduPilotManager(metaclass=Singleton):
    def __init__(self) -> None:
        self.settings = Settings()
        self.settings.create_app_folders()
        self.mavlink_manager = MavlinkManager()
        self.mavlink_manager.set_logdir(self.settings.log_path)

        # Load settings and do the initial configuration
        if self.settings.load():
            logger.info(f"Loaded settings from {self.settings.settings_file}.")
            logger.debug(self.settings.content)
        else:
            self.settings.create_settings_file()

        self.configuration = deepcopy(self.settings.content)
        self.firmware_manager = FirmwareManager(self.settings.firmware_folder, self.settings.defaults_folder)
        self.vehicle_manager = VehicleManager()
        self.binary_manager = ArduPilotBinaryManager()

    async def start(self, board: FlightController, sitl_frame: SITLFrame = SITLFrame.VECTORED) -> None:
        """Start a flight-controller (automatically chosen) and add it to the mavlink connection."""
        logger.info("Starting ArduPilot manager.")
        self.set_preferred_board(board)
        master_endpoint = self.get_default_master_endpoint(board)
        self.start_board(board, master_endpoint, sitl_frame)
        self.mavlink_manager.clear_endpoints()
        self._load_saved_endpoints()
        self._load_default_endpoints()
        logger.info(f"Starting mavlink connection on '{master_endpoint}' with flight-controller {board.name}.")
        self.mavlink_manager.start(master_endpoint)
        if not self.is_connected(board):
            await self.stop()
            raise BoardIsNotConnected(f"Failed to connect to '{board.name}' board.")

    async def stop(self) -> None:
        """Stop any available board and the cease the mavlink connection."""
        logger.info("Stopping all boards and ceasing mavlink connection.")
        for board in self.available_boards():
            await self.stop_board(board)
        self.mavlink_manager.stop()

    def start_board(self, board: FlightController, master_endpoint: Endpoint, sitl_frame: SITLFrame) -> None:
        """Start given board."""
        logger.info(f"Starting flight-controller '{board.name}'.")
        if board.type == PlatformType.Linux:
            self.binary_manager.start_linux_binary(
                board,
                master_endpoint,
                self.firmware_manager.firmware_path(board.platform),
                pathlib.Path("f{self.settings.firmware_folder}/logs/"),
                pathlib.Path("f{self.settings.firmware_folder}/storage/"),
            )
            return
        if board.type == PlatformType.Serial:
            return
        if board.type == PlatformType.SITL:
            self.binary_manager.start_sitl_binary(
                board, master_endpoint, self.firmware_manager.firmware_path(board.platform), sitl_frame
            )
            return
        raise UnknownBoardProcedure(f"Procedure to start flight-controller of type '{board.type}' is unknown.")

    async def stop_board(self, board: FlightController) -> None:
        """Stop given board."""
        logger.info(f"Stopping flight-controller '{board.name}'.")
        if board.type == PlatformType.Linux:
            await self.binary_manager.stop_linux_binary(board)
            return
        if board.type == PlatformType.Serial:
            # Serial boards cannot be stopped.
            return
        if board.type == PlatformType.SITL:
            await self.binary_manager.stop_sitl(board)
            return
        raise UnknownBoardProcedure(f"Procedure to stop board of type '{board.type}' is unknown.")

    def get_primary_board(self) -> Optional[FlightController]:
        """Get which board should be used based on pre-defined priorities."""
        if self.preferred_board:
            logger.debug(f"Preferred flight-controller is {self.preferred_board.name}.")
            for board in self.available_boards():
                # Compare connected boards with saved board, excluding path (which can change between sessions)
                if self.preferred_board.dict(exclude={"path"}).items() <= board.dict().items():
                    return board
            logger.debug(f"Flight-controller {self.preferred_board.name} not connected.")

        self.available_boards().sort(key=lambda board: board.platform)
        return self.available_boards()[0] if self.available_boards() else None

    def set_preferred_board(self, board: FlightController) -> None:
        logger.info(f"Setting {board.name} as preferred flight-controller.")
        self.configuration["preferred_board"] = board.dict(exclude={"path"})
        self.settings.save(self.configuration)

    @property
    def preferred_board(self) -> Optional[FlightController]:
        preferred_board = self.configuration.get("preferred_board")
        if preferred_board is None:
            return None
        return FlightController(**preferred_board)

    @property
    def running_board(self) -> Optional[FlightController]:
        """Board which is currently running."""
        for board in self.available_boards():
            if self.is_connected(board):
                return board
        return None

    @staticmethod
    def available_boards() -> List[FlightController]:
        """Get list of boards available on system."""
        return BoardDetector.detect()

    def is_connected(self, board: FlightController) -> bool:
        """Check if given board is connected."""
        if self.mavlink_manager.master_endpoint is None:
            return False
        return (
            self.get_default_master_endpoint(board) == self.mavlink_manager.master_endpoint
            and self.vehicle_manager.is_heart_beating()
        )

    def get_default_master_endpoint(self, board: FlightController) -> Endpoint:
        """Get master endpoint to be used for given board."""
        if board.type == PlatformType.Linux:
            return Endpoint("Master", self.settings.app_name, EndpointType.UDPServer, "127.0.0.1", 8852, protected=True)
        if board.type == PlatformType.Serial:
            return Endpoint("Master", self.settings.app_name, EndpointType.Serial, board.path, 115200, protected=True)
        if board.type == PlatformType.SITL:
            return Endpoint("Master", self.settings.app_name, EndpointType.TCPServer, "127.0.0.1", 5760, protected=True)
        raise UnknownBoardProcedure(f"Default master endpoint for board of type '{board.type}' is unknown.")

    async def start_mavlink_manager_watchdog(self) -> None:
        logger.info("Starting watchdog for mavlink manager.")
        await self.mavlink_manager.auto_restart_router()

    async def start_ardupilot_binary_watchdog(self) -> None:
        logger.info("Starting watchdog for ArduPilot binary.")
        await self.binary_manager.auto_restart_ardupilot_process()

    def _load_default_endpoints(self) -> None:
        logger.info("Adding default endpoints to mavlink connection.")
        default_endpoints = [
            Endpoint(
                "GCS Server Link",
                self.settings.app_name,
                EndpointType.UDPServer,
                "0.0.0.0",
                14550,
                persistent=True,
                enabled=False,
            ),
            Endpoint(
                "GCS Client Link",
                self.settings.app_name,
                EndpointType.UDPClient,
                "192.168.2.1",
                14550,
                persistent=True,
                enabled=True,
            ),
            Endpoint(
                "Internal Link",
                self.settings.app_name,
                EndpointType.UDPServer,
                "127.0.0.1",
                14001,
                persistent=True,
                protected=True,
            ),
        ]
        for endpoint in default_endpoints:
            try:
                self.mavlink_manager.add_endpoint(endpoint)
            except EndpointAlreadyExists:
                pass
            except Exception as error:
                logger.warning(str(error))

    def _get_configuration_endpoints(self) -> Set[Endpoint]:
        return {Endpoint(**endpoint) for endpoint in self.configuration.get("endpoints") or []}

    def _save_endpoints_to_configuration(self, endpoints: Set[Endpoint]) -> None:
        self.configuration["endpoints"] = list(map(Endpoint.as_dict, endpoints))

    def _load_saved_endpoints(self) -> None:
        """Load endpoints from the configuration file to the mavlink manager."""
        logger.info("Loading endpoints from settings file.")
        for endpoint in self._get_configuration_endpoints():
            try:
                self.mavlink_manager.add_endpoint(endpoint)
            except Exception as error:
                logger.error(f"Could not load endpoint {endpoint}: {error}")

    def _save_current_endpoints(self) -> None:
        logger.info("Saving current endpoints to settings file.")
        try:
            persistent_endpoints = set(filter(lambda endpoint: endpoint.persistent, self.get_endpoints()))
            self._save_endpoints_to_configuration(persistent_endpoints)
            self.settings.save(self.configuration)
        except Exception as error:
            logger.error(f"Could not save endpoints. {error}")

    def get_endpoints(self) -> Set[Endpoint]:
        """Get all endpoints from the mavlink manager."""
        return self.mavlink_manager.endpoints()

    def add_new_endpoints(self, new_endpoints: Set[Endpoint]) -> None:
        """Add multiple endpoints to the mavlink manager and save them on the configuration file."""
        logger.info(f"Adding endpoints {[e.name for e in new_endpoints]} and updating settings file.")
        self.mavlink_manager.add_endpoints(new_endpoints)
        self._save_current_endpoints()
        self.mavlink_manager.restart()

    def remove_endpoints(self, endpoints_to_remove: Set[Endpoint]) -> None:
        """Remove multiple endpoints from the mavlink manager and save them on the configuration file."""
        logger.info(f"Removing endpoints {[e.name for e in endpoints_to_remove]} and updating settings file.")
        self.mavlink_manager.remove_endpoints(endpoints_to_remove)
        self._save_current_endpoints()
        self.mavlink_manager.restart()

    def update_endpoints(self, endpoints_to_update: Set[Endpoint]) -> None:
        """Update multiple endpoints from the mavlink manager and save them on the configuration file."""
        logger.info(f"Modifying endpoints {[e.name for e in endpoints_to_update]} and updating settings file.")
        self.mavlink_manager.update_endpoints(endpoints_to_update)
        self._save_current_endpoints()
        self.mavlink_manager.restart()

    def get_available_firmwares(self, vehicle: Vehicle, platform: Platform) -> List[Firmware]:
        return self.firmware_manager.get_available_firmwares(vehicle, platform)

    def install_firmware_from_file(self, firmware_path: pathlib.Path, platform: Platform) -> None:
        self.firmware_manager.install_firmware_from_file(firmware_path, platform)

    def install_firmware_from_url(self, url: str, platform: Platform) -> None:
        self.firmware_manager.install_firmware_from_url(url, platform)

    def restore_default_firmware(self, platform: Platform) -> None:
        self.firmware_manager.restore_default_firmware(platform)
