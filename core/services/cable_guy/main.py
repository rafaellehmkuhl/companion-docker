#! /usr/bin/env python3
import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, List

import uvicorn
from fastapi import Body, FastAPI, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi_versioning import VersionedFastAPI, version
from loguru import logger
from starlette.responses import Response as StarletteResponse

from api import manager
from api.manager import EthernetInterface

parser = argparse.ArgumentParser(description="Cable Guy service for Blue Robotics Companion")
parser.add_argument("-v", "--verbose", help="increase output verbosity", action="store_true")

args = parser.parse_args()

if not args.verbose:
    logger.remove()
    logger.add(sys.stderr, format="<green>{time:HH:mm:ss.SSS}</green> | <level>{message}</level>")


class InterceptHandler(logging.Handler):
    def emit(self, record) -> None:  # type: ignore
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back  # type: ignore
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


logging.basicConfig(handlers=[InterceptHandler()], level=0)


class PrettyJSONResponse(StarletteResponse):
    media_type = "application/json"

    def render(self, content: Any) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            separators=(", ", ": "),
        ).encode(self.charset)


HTML_FOLDER = Path.joinpath(Path(__file__).parent.absolute(), "html")

app = FastAPI(
    title="Cable Guy API",
    description="Cable Guy is responsible for managing internet interfaces on Companion.",
    default_response_class=PrettyJSONResponse,
    debug=True,
)


@app.get("/ethernet", response_model=List[EthernetInterface], summary="Retrieve ethernet interfaces.")
@version(1, 0)
def retrieve_interfaces() -> Any:
    """REST API endpoint to retrieve the configured ethernet interfaces."""
    return manager.ethernetManager.get_interfaces()


@app.post("/ethernet", response_model=EthernetInterface, summary="Configure a ethernet interface.")
@version(1, 0)
def configure_interface(interface: EthernetInterface = Body(...)) -> Any:
    """REST API endpoint to configure a new ethernet interface or modify an existing one."""
    if not manager.ethernetManager.set_configuration(interface):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not configure ethernet interface with provided configuration.",
        )

    manager.ethernetManager.save()
    return interface


app = VersionedFastAPI(
    app,
    version="1.0.0",
    prefix_format="/v{major}.{minor}",
    enable_latest=True,
)
app.mount("/", StaticFiles(directory=str(HTML_FOLDER), html=True))

if __name__ == "__main__":
    if os.geteuid() != 0:
        logger.error(
            "You need root privileges to run this script.\nPlease try again, this time using **sudo**. Exiting."
        )
        sys.exit(1)

    # Running uvicorn with log disabled so loguru can handle it
    uvicorn.run(app, host="0.0.0.0", port=9090, log_config=None)
