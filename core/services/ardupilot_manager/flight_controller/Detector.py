import os
from typing import List, Optional

from loguru import logger
from serial.tools.list_ports_linux import SysFS, comports
from smbus2 import SMBus

from typedefs import FlightController, Platform


class Detector:
    @staticmethod
    def _is_root() -> bool:
        """Check if the script is running as root

        Returns:
            bool: True if running as root
        """
        return os.geteuid() == 0

    @staticmethod
    def get_navigator_r3_if_connected() -> Optional[FlightController]:
        """Returns Navigator R3 if connected.
        Check for connection using the sensors on the I²C BUS.

        Returns:
            Optional[FlightController]: Return flight-controller if connected, None otherwise.
        """
        try:
            bus = SMBus(1)
            ADS1115_address = 0x48
            bus.read_byte_data(ADS1115_address, 0)

            bus = SMBus(4)
            PCA9685_address = 0x40
            bus.read_byte_data(PCA9685_address, 0)

            return FlightController(name="Navigator", manufacturer="Blue Robotics", platform=Platform.NavigatorR3)
        except Exception as error:
            logger.info("Navigator R3 not detected on I2C bus.")
            logger.debug(error)
            return None

    @staticmethod
    def get_navigator_r4_if_connected() -> Optional[FlightController]:
        """Returns Navigator R4 if connected.
        Check for connection using the sensors on the I²C BUS.

        Returns:
            Optional[FlightController]: Return flight-controller if connected, None otherwise.
        """
        try:
            bus = SMBus(1)
            ADS1115_address = 0x48
            bus.read_byte_data(ADS1115_address, 0)

            AK09915_address = 0x0C
            bus.read_byte_data(AK09915_address, 0)

            BME280_address = 0x76
            bus.read_byte_data(BME280_address, 0)

            bus = SMBus(4)
            PCA9685_address = 0x40
            bus.read_byte_data(PCA9685_address, 0)

            return FlightController(name="Navigator", manufacturer="Blue Robotics", platform=Platform.Navigator)
        except Exception as error:
            logger.info("Navigator R4 not detected on I2C bus.")
            logger.debug(error)
            return None

    @staticmethod
    def detect_serial_flight_controllers() -> List[FlightController]:
        """Check if pixhawks or other serial valid flight controllers are connected.

        Returns:
            List[FlightController]: List of connected serial flight controllers.
        """

        def is_valid_flight_controller(port: SysFS) -> bool:
            return port.manufacturer == "ArduPilot" or (port.manufacturer == "3D Robotics" and "PX4" in port.product)

        return [
            FlightController(
                name=port.product, manufacturer=port.manufacturer, platform=Platform.Pixhawk1, path=port.device
            )
            for port in comports()
            if is_valid_flight_controller(port)
        ]

    @staticmethod
    def detect() -> List[FlightController]:
        """Return a list of available flight controllers

        Returns:
            List[FlightController]: List of available flight controllers
        """
        available = []
        if Detector._is_root():
            # We should detect R4 first since it shares some sensors as R3
            navigator_r4 = Detector.get_navigator_r4_if_connected()
            if navigator_r4:
                available.append(navigator_r4)
            else:
                navigator_r3 = Detector.get_navigator_r3_if_connected()
                if navigator_r3:
                    available.append(navigator_r3)

        available.extend(Detector().detect_serial_flight_controllers())

        return available
