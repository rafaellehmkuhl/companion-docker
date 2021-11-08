import pathlib

from ardupilot_fw_uploader import find_bootloader, uploader

from exceptions import (
    BoardBootloaderCommFail,
    UnsupportedBoardType,
    UnsupportedPlatform,
)
from typedefs import Platform

corresponding_platform = {
    9: Platform.Pixhawk1,
    50: Platform.Pixhawk4,
}

corresponding_board_type = {platform: board_type for board_type, platform in corresponding_platform.items()}


class BoardIdentifier:
    @staticmethod
    def get_board_type(port: pathlib.Path, bootloader_baud: int = 115200, flighstack_baud: int = 57600) -> int:
        """Get board type for connected board."""
        up = uploader(port, bootloader_baud, flighstack_baud)
        if not find_bootloader(up, port):
            raise BoardBootloaderCommFail("Could not find board bootloader.")
        up.identify()
        return int(up.board_type)

    @staticmethod
    def get_board_platform(board_type: int) -> Platform:
        platform = corresponding_platform.get(board_type, None)
        if not platform:
            raise UnsupportedPlatform(f"Board with type {board_type} is not supported as a platform in Companion.")
        return platform

    @staticmethod
    def get_platform_board_type(platform: Platform) -> int:
        board_type = corresponding_board_type.get(platform, None)
        if not board_type:
            raise UnsupportedBoardType(f"Platform {platform} has no associated board type in Companion.")
        return board_type
