#! /usr/bin/env python3
import argparse
import asyncio
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Set

from commonwealth.utils.apis import PrettyJSONResponse
from commonwealth.utils.logs import InterceptHandler
from fastapi import Body, FastAPI, File, Response, UploadFile, status
from fastapi.staticfiles import StaticFiles
from fastapi_versioning import VersionedFastAPI, version
from loguru import logger
from uvicorn import Config, Server

from ArduPilotManager import ArduPilotManager
from exceptions import InvalidFirmwareFile
from flight_controller.Detector import Detector as BoardDetector
from mavlink_proxy.Endpoint import Endpoint
from typedefs import Firmware, FlightController, Platform, SITLFrame, Vehicle

FRONTEND_FOLDER = Path.joinpath(Path(__file__).parent.absolute(), "frontend")

parser = argparse.ArgumentParser(description="ArduPilot Manager service for Blue Robotics Companion")
parser.add_argument("-s", "--sitl", help="run SITL instead of connecting any board", action="store_true")

args = parser.parse_args()

logging.basicConfig(handlers=[InterceptHandler()], level=0)


app = FastAPI(
    title="ArduPilot Manager API",
    description="ArduPilot Manager is responsible for managing ArduPilot devices connected to Companion.",
    default_response_class=PrettyJSONResponse,
    debug=True,
)
logger.info("Starting ArduPilot Manager.")
autopilot = ArduPilotManager()
autopilot.check_running_as_root()


@app.get("/endpoints", response_model=List[Dict[str, Any]])
@version(1, 0)
def get_available_endpoints() -> Any:
    return list(map(Endpoint.as_dict, autopilot.get_endpoints()))


@app.post("/endpoints", status_code=status.HTTP_201_CREATED)
@version(1, 0)
def create_endpoints(response: Response, endpoints: Set[Endpoint] = Body(...)) -> Any:
    try:
        autopilot.add_new_endpoints(endpoints)
        autopilot.reload_endpoints()
    except ValueError as error:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"message": f"{error}"}


@app.delete("/endpoints", status_code=status.HTTP_200_OK)
@version(1, 0)
def remove_endpoints(response: Response, endpoints: Set[Endpoint] = Body(...)) -> Any:
    try:
        autopilot.remove_endpoints(endpoints)
        autopilot.reload_endpoints()
    except ValueError as error:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"message": f"{error}"}


@app.get(
    "/available_firmwares",
    response_model=List[Firmware],
    summary="Retrieve dictionary of available firmwares versions with their respective URL.",
)
@version(1, 0)
def get_available_firmwares(response: Response, vehicle: Vehicle) -> Any:
    try:
        return autopilot.get_available_firmwares(vehicle)
    except Exception as error:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": f"{error}"}


@app.post("/install_firmware_from_url", summary="Install firmware for given URL.")
@version(1, 0)
async def install_firmware_from_url(response: Response, url: str) -> Any:
    try:
        await autopilot.stop_ardupilot()
        autopilot.install_firmware_from_url(url)
    except Exception as error:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": f"{error}"}
    finally:
        await autopilot.start_ardupilot()


@app.post("/install_firmware_from_file", summary="Install firmware from user file.")
@version(1, 0)
async def install_firmware_from_file(response: Response, binary: UploadFile = File(...)) -> Any:
    custom_firmware = Path.joinpath(autopilot.settings.firmware_folder, "custom_firmware")
    try:
        with open(custom_firmware, "wb") as buffer:
            shutil.copyfileobj(binary.file, buffer)
        await autopilot.stop_ardupilot()
        autopilot.install_firmware_from_file(custom_firmware)
        os.remove(custom_firmware)
    except InvalidFirmwareFile as error:
        response.status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
        return {"message": f"Cannot use this file: {error}"}
    except Exception as error:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": f"{error}"}
    finally:
        binary.file.close()
        await autopilot.start_ardupilot()


@app.get("/platform", response_model=Platform, summary="Check what is the current running platform.")
@version(1, 0)
def platform(response: Response) -> Any:
    try:
        return autopilot.platform
    except Exception as error:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": f"{error}"}


@app.post("/platform", summary="Toggle between SITL and default platform (auto-detected).")
@version(1, 0)
async def set_platform(response: Response, use_sitl: bool, sitl_frame: SITLFrame = SITLFrame.VECTORED) -> Any:
    try:
        autopilot.use_sitl = use_sitl
        autopilot.current_sitl_frame = sitl_frame

        logger.debug("Restarting ardupilot...")
        await autopilot.stop_ardupilot()
        await autopilot.start_ardupilot()
        logger.debug("Ardupilot successfully restarted.")
    except Exception as error:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": f"{error}"}


@app.post("/restart", summary="Restart the autopilot with current set options.")
@version(1, 0)
async def restart(response: Response) -> Any:
    try:
        logger.debug("Restarting ardupilot...")
        await autopilot.restart_ardupilot()
        logger.debug("Ardupilot successfully restarted.")
    except Exception as error:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": f"{error}"}


@app.post("/restore_default_firmware", summary="Restore default firmware.")
@version(1, 0)
async def restore_default_firmware(response: Response) -> Any:
    try:
        await autopilot.stop_ardupilot()
        autopilot.restore_default_firmware()
    except Exception as error:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": f"{error}"}
    finally:
        await autopilot.start_ardupilot()


@app.get("/available_boards", response_model=List[FlightController], summary="Retrieve list of connected boards.")
@version(1, 0)
def available_boards(response: Response) -> Any:
    try:
        return BoardDetector.detect()
    except Exception as error:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": f"{error}"}


@app.get("/preferred_board", response_model=FlightController, summary="Retrieve which board is preferred.")
@version(1, 0)
def get_preferred_board(response: Response) -> Any:
    try:
        return autopilot.get_preferred_board()
    except Exception as error:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": f"{error}"}


@app.post("/preferred_board", summary="Set preferred board.")
@version(1, 0)
def set_preferred_board(response: Response, board: FlightController) -> Any:
    try:
        return autopilot.set_preferred_board(board)
    except Exception as error:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": f"{error}"}


app = VersionedFastAPI(app, version="1.0.0", prefix_format="/v{major}.{minor}", enable_latest=True)
app.mount("/", StaticFiles(directory=str(FRONTEND_FOLDER), html=True))


if __name__ == "__main__":
    if args.sitl:
        autopilot.use_sitl = True

    loop = asyncio.new_event_loop()

    # # Running uvicorn with log disabled so loguru can handle it
    config = Config(app=app, loop=loop, host="0.0.0.0", port=8000, log_config=None)
    server = Server(config)

    loop.create_task(autopilot.start_ardupilot())
    loop.create_task(autopilot.platform_manager.auto_restart_ardupilot_process())
    loop.create_task(autopilot.mavlink_manager.auto_restart_router())
    loop.run_until_complete(server.serve())
    loop.run_until_complete(autopilot.stop_ardupilot())
