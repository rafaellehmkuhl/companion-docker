import pathlib

import pytest

from exceptions import InvalidFirmwareFile, UndefinedPlatform
from firmware.FirmwareDownload import FirmwareDownloader
from firmware.FirmwareInstall import FirmwareInstaller
from typedefs import FlightController, Platform, Vehicle


def test_firmware_validation() -> None:
    downloader = FirmwareDownloader()
    installer = FirmwareInstaller()

    # Pixhawk1 APJ firmwares should always work
    temporary_file = downloader.download(Vehicle.Sub, Platform.Pixhawk1)
    installer._validate_apj(temporary_file, Platform.Pixhawk1)

    # New SITL firmwares should always work
    temporary_file = downloader.download(Vehicle.Sub, Platform.SITL, version="DEV")
    installer._validate_elf(temporary_file, Platform.SITL)

    # Raise when validating for Undefined platform
    with pytest.raises(UndefinedPlatform):
        board = FlightController(name="Undefined board", manufacturer="Unknown", platform=Platform.Undefined)
        installer.validate_firmware(pathlib.Path(""), board)

    # Raise when validating Navigator firmwares (as test platform is x86)
    temporary_file = downloader.download(Vehicle.Sub, Platform.NavigatorR5)
    with pytest.raises(InvalidFirmwareFile):
        installer._validate_elf(temporary_file, Platform.NavigatorR5)

    # Install SITL firmware
    temporary_file = downloader.download(Vehicle.Sub, Platform.SITL, version="DEV")
    board = FlightController(name="SITL", manufacturer="ArduPilot Team", platform=Platform.SITL)
    installer.install_firmware(temporary_file, board, pathlib.Path(f"{temporary_file}_dest"))
