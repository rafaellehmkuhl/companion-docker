from typing import Any, Dict, List

from loguru import logger

from commonwealth.mavlink_comm.exceptions import VehicleDisarmFail
from commonwealth.mavlink_comm.MavlinkComm import MavlinkMessenger

MAV_MODE_FLAG_SAFETY_ARMED = 128


class VehicleManager:
    def __init__(self) -> None:
        self.mavlink2rest = MavlinkMessenger()

        self.target_system = 1
        self.target_component = 1
        self.confirmation = 0

    def set_target_system(self, target_system: int) -> None:
        self.target_system = target_system

    def set_target_component(self, target_component: int) -> None:
        self.target_component = target_component

    def set_confirmation(self, confirmation: int) -> None:
        self.confirmation = confirmation

    def command_long_message(self, command_type: str, params: List[float]) -> Dict[str, Any]:
        return {
            "type": "COMMAND_LONG",
            "param1": params[0] if len(params) > 0 else 0,
            "param2": params[1] if len(params) > 1 else 0,
            "param3": params[2] if len(params) > 2 else 0,
            "param4": params[3] if len(params) > 3 else 0,
            "param5": params[4] if len(params) > 4 else 0,
            "param6": params[5] if len(params) > 5 else 0,
            "param7": params[6] if len(params) > 6 else 0,
            "command": {"type": command_type},
            "target_system": self.target_system,
            "target_component": self.target_component,
            "confirmation": self.confirmation,
        }

    def reboot_vehicle(self) -> None:
        message = self.command_long_message("MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN", [1.0])
        self.mavlink2rest.send_mavlink_message(message)

    def shutdown_vehicle(self) -> None:
        shutdown_message = self.command_long_message("MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN", [2.0])
        self.mavlink2rest.send_mavlink_message(shutdown_message)

    def is_vehicle_armed(self) -> bool:
        get_response = self.mavlink2rest.get_updated_mavlink_message("HEARTBEAT")
        base_mode_bits = get_response["message"]["base_mode"]["bits"]
        if not isinstance(base_mode_bits, int):
            raise ValueError("Got unexpected HEARTBEAT message from Autopilot.")

        # Check if bit representing an armed vehicle is on base_mode bit array
        return bool(base_mode_bits & MAV_MODE_FLAG_SAFETY_ARMED)

    def disarm_vehicle(self) -> None:
        if not self.is_vehicle_armed():
            logger.debug("Vehicle already disarmed.")
            return

        logger.debug("Trying to disarm vehicle.")

        disarm_message = self.command_long_message("MAV_CMD_COMPONENT_ARM_DISARM", [])

        self.mavlink2rest.send_mavlink_message(disarm_message)
        if self.is_vehicle_armed():
            raise VehicleDisarmFail("Failed to disarm vehicle. Please try a manual disarm.")

        logger.debug("Successfully disarmed vehicle.")

    def is_heart_beating(self) -> bool:
        try:
            return bool(self.mavlink2rest.get_updated_mavlink_message("HEARTBEAT"))
        except Exception as error:
            logger.error(f"Fetching for heatbeat failed. {error}")
            return False
