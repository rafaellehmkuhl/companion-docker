import os
from enum import Enum
from typing import List, Tuple

from smbus2 import SMBus


class FlightControllerType(Enum):
    Serial = 1
    Navigator = 2


class Detector:
    @staticmethod
    def _is_root() -> bool:
        """Check if the script is running as root

        Returns:
            bool: True if running as root
        """
        return os.geteuid() == 0

    @staticmethod
    def detect_navigator() -> Tuple[bool, str]:
        """Check if navigator is connected using the sensors on the I²C BUS

        Returns:
            (bool, str): True if a navigator is connected, false otherwise.
                String is always empty
        """
        try:
            bus = SMBus(1)
            PCA9685_address = 0x40
            ADS115_address = 0x48

            bus.read_byte_data(PCA9685_address, 0)
            bus.read_byte_data(ADS115_address, 0)
            return (True, "")
        except Exception as error:
            print(f"Navigator not detected on I2C bus: {error}")
            return (False, "")

    @staticmethod
    def detect_serial_flight_controller() -> Tuple[bool, str]:
        """Check if a pixhawk or any serial valid flight controller is connected

        Returns:
            (bool, str): True if a serial flight controller is connected, false otherwise.
                String will point to the serial device.
        """
        serial_path = "/dev/autopilot"
        result = (True, serial_path) if os.path.exists(serial_path) else (False, "")
        return result

    @staticmethod
    def detect() -> List[Tuple[FlightControllerType, str]]:
        """Return a list of available flight controllers

        Returns:
            (FlightControllerType, str): List of available flight controllers
        """
        available = []
        if Detector._is_root():
            result, path = Detector.detect_navigator()
            if result:
                available.append((FlightControllerType.Navigator, path))

        result, path = Detector.detect_serial_flight_controller()
        if result:
            available.append((FlightControllerType.Serial, path))

        return available