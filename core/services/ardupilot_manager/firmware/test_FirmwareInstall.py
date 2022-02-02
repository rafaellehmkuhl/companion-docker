import pathlib

import pytest

from exceptions import InvalidFirmwareFile, UndefinedPlatform
from firmware.FirmwareDownload import FirmwareDownloader
from firmware.FirmwareInstall import FirmwareInstaller
from typedefs import Platform, Vehicle


def test_firmware_validation() -> None:
    downloader = FirmwareDownloader()
    installer = FirmwareInstaller()

    # Pixhawk1 APJ firmwares should always work
    temporary_file = downloader.download(Vehicle.Sub, Platform.Pixhawk1)
    installer.validate_firmware(temporary_file, Platform.Pixhawk1)

    # New SITL firmwares should always work
    temporary_file = downloader.download(Vehicle.Sub, Platform.SITL, version="DEV")
    installer.validate_firmware(temporary_file, Platform.SITL)

    # Raise when validating Navigator firmwares (as test platform is x86)
    temporary_file = downloader.download(Vehicle.Sub, Platform.NavigatorR5)
    with pytest.raises(InvalidFirmwareFile):
        installer.validate_firmware(temporary_file, Platform.NavigatorR5)

    # Install SITL firmware
    temporary_file = downloader.download(Vehicle.Sub, Platform.SITL, version="DEV")
    installer.install_firmware(temporary_file, Platform.SITL, pathlib.Path(f"{temporary_file}_dest"))
