#! /usr/bin/env python3
import argparse
import asyncio
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from commonwealth.utils.apis import PrettyJSONResponse
from commonwealth.utils.general import is_running_as_root
from commonwealth.utils.logs import InterceptHandler
from fastapi import Body, FastAPI, File, HTTPException, Response, UploadFile, status
from fastapi.staticfiles import StaticFiles
from fastapi_versioning import VersionedFastAPI, version
from flight_controller_detector.Detector import Detector
from loguru import logger
from uvicorn import Config, Server

from ArduPilotManager import ArduPilotManager
from exceptions import InvalidFirmwareFile
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
if not is_running_as_root():
    raise RuntimeError("ArduPilot manager needs to run with root privilege.")


@app.get("/endpoints", response_model=List[Dict[str, Any]])
@version(1, 0)
def get_available_endpoints() -> Any:
    return list(map(Endpoint.as_dict, autopilot.get_endpoints()))


@app.post("/endpoints", status_code=status.HTTP_201_CREATED)
@version(1, 0)
def create_endpoints(endpoints: Set[Endpoint] = Body(...)) -> Any:
    try:
        autopilot.add_new_endpoints(endpoints)
    except Exception as error:
        logger.error(error)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@app.delete("/endpoints", status_code=status.HTTP_200_OK)
@version(1, 0)
def remove_endpoints(endpoints: Set[Endpoint] = Body(...)) -> Any:
    try:
        autopilot.remove_endpoints(endpoints)
    except Exception as error:
        logger.error(error)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@app.put("/endpoints", status_code=status.HTTP_200_OK)
@version(1, 0)
def update_endpoints(endpoints: Set[Endpoint] = Body(...)) -> Any:
    try:
        autopilot.update_endpoints(endpoints)
    except Exception as error:
        logger.error(error)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@app.get(
    "/available_firmwares",
    response_model=List[Firmware],
    summary="Retrieve dictionary of available firmwares versions with their respective URL.",
)
@version(1, 0)
def get_available_firmwares(response: Response, vehicle: Vehicle) -> Any:
    try:
        current_board = autopilot.running_board
        if not current_board:
            raise ValueError("Cannot get available firmwares. No running board.")
        return autopilot.get_available_firmwares(vehicle, current_board)
    except Exception as error:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": f"{error}"}


@app.post("/install_firmware_from_url", summary="Install firmware for given URL.")
@version(1, 0)
async def install_firmware_from_url(response: Response, url: str) -> Any:
    try:
        current_board = autopilot.running_board
        if not current_board:
            raise ValueError("Cannot install firmware. No running board.")
        await autopilot.stop()
        autopilot.install_firmware_from_url(url, current_board)
    except Exception as error:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": f"{error}"}
    finally:
        await autopilot.start(current_board)


@app.post("/install_firmware_from_file", summary="Install firmware from user file.")
@version(1, 0)
async def install_firmware_from_file(response: Response, binary: UploadFile = File(...)) -> Any:
    custom_firmware = Path.joinpath(autopilot.settings.firmware_folder, "custom_firmware")
    try:
        current_board = autopilot.running_board
        if not current_board:
            raise ValueError("Cannot install firmware. No running board.")
        with open(custom_firmware, "wb") as buffer:
            shutil.copyfileobj(binary.file, buffer)
        await autopilot.stop()
        autopilot.install_firmware_from_file(custom_firmware, current_board)
        os.remove(custom_firmware)
    except InvalidFirmwareFile as error:
        response.status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
        return {"message": f"Cannot use this file: {error}"}
    except Exception as error:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": f"{error}"}
    finally:
        binary.file.close()
        await autopilot.start(current_board)


@app.get("/platform", response_model=Platform, summary="Check what is the current running platform.")
@version(1, 0)
def platform(response: Response) -> Any:
    try:
        current_board = autopilot.running_board
        if not current_board:
            raise ValueError("Cannot fetch current platform. No running board.")
        return current_board.platform
    except Exception as error:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": f"{error}"}


@app.post("/board", summary="Connect ArduPilot manager to a different board.")
@version(1, 0)
async def set_board(response: Response, board: FlightController, sitl_frame: SITLFrame = SITLFrame.VECTORED) -> Any:
    try:
        await autopilot.stop()
        await autopilot.start(board, sitl_frame)
    except Exception as error:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": f"{error}"}


@app.post("/restart", summary="Restart the autopilot with current set options.")
@version(1, 0)
async def restart(response: Response) -> Any:
    try:
        current_board = autopilot.running_board
        await autopilot.stop()
        await autopilot.start(current_board)
    except Exception as error:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": f"{error}"}


@app.post("/start", summary="Start the autopilot.")
@version(1, 0)
async def start(response: Response, board: FlightController) -> Any:
    try:
        await autopilot.start(board)
    except Exception as error:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": f"{error}"}


@app.post("/stop", summary="Stop the autopilot.")
@version(1, 0)
async def stop(response: Response) -> Any:
    try:
        await autopilot.stop()
    except Exception as error:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": f"{error}"}


@app.post("/restore_default_firmware", summary="Restore default firmware.")
@version(1, 0)
async def restore_default_firmware(response: Response) -> Any:
    try:
        current_board = autopilot.running_board
        if not current_board:
            raise ValueError("Cannot restore firmware. No running board.")
        await autopilot.stop()
        autopilot.restore_default_firmware(current_board)
    except Exception as error:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": f"{error}"}
    finally:
        await autopilot.start(current_board)


@app.get("/available_boards", response_model=List[FlightController], summary="Retrieve list of connected boards.")
@version(1, 0)
def available_boards(response: Response) -> Any:
    try:
        return autopilot.available_boards()
    except Exception as error:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": f"{error}"}


@app.get("/preferred_board", response_model=Optional[FlightController], summary="Retrieve which board is preferred.")
@version(1, 0)
def get_preferred_board(response: Response) -> Any:
    try:
        return autopilot.preferred_board
    except Exception as error:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": f"{error}"}


@app.post("/preferred_board", summary="Set preferred board.")
@version(1, 0)
def set_preferred_board(response: Response, board: FlightController) -> Any:
    try:
        autopilot.set_preferred_board(board)
    except Exception as error:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": f"{error}"}


app = VersionedFastAPI(app, version="1.0.0", prefix_format="/v{major}.{minor}", enable_latest=True)
app.mount("/", StaticFiles(directory=str(FRONTEND_FOLDER), html=True))


if __name__ == "__main__":
    loop = asyncio.new_event_loop()

    # # Running uvicorn with log disabled so loguru can handle it
    config = Config(app=app, loop=loop, host="0.0.0.0", port=8000, log_config=None)
    server = Server(config)

    chosen_board = autopilot.get_primary_board()
    if args.sitl:
        chosen_board = Detector.detect_sitl()

    loop.create_task(autopilot.start(chosen_board))
    loop.run_until_complete(server.serve())
    loop.run_until_complete(autopilot.stop())
