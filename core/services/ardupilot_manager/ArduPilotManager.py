import pathlib
from copy import deepcopy
from typing import List, Set

from commonwealth.mavlink_comm.VehicleManager import VehicleManager
from commonwealth.utils.Singleton import Singleton
from loguru import logger

from firmware.FirmwareManagement import FirmwareManager
from mavlink_proxy.Endpoint import Endpoint
from mavlink_proxy.Manager import Manager as MavlinkManager
from settings import Settings
from typedefs import Firmware, Platform, Vehicle


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

    async def start_mavlink_manager_watchdog(self) -> None:
        await self.mavlink_manager.auto_restart_router()

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

    def _save_current_endpoints(self) -> None:
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
