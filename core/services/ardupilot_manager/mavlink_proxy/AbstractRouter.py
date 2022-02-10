import abc
import asyncio
from asyncio import subprocess
import pathlib
import shlex
import shutil
import tempfile
import time
from typing import Any, List, Optional, Set, Type

from loguru import logger

from exceptions import (
    DuplicateEndpointName,
    EndpointAlreadyExists,
    EndpointDontExist,
    MavlinkRouterStartFail,
)
from mavlink_proxy.Endpoint import Endpoint


async def log_async_subprocess(process: asyncio.subprocess.Process):
    while True:
        await asyncio.sleep(0.1)
        stdout_b: Optional[bytes] = None
        stderr_b: Optional[bytes] = None

        try:
            stdout_b = await asyncio.wait_for(process.stdout.readline(), 0.001)
            if stdout_b:
                logger.info(stdout_b.decode("utf-8").replace("\n", ""))
        except Exception:
            pass
        try:
            stderr_b = await asyncio.wait_for(process.stderr.readline(), 0.001)
            if stderr_b:
                logger.error(stderr_b.decode("utf-8").replace("\n", ""))
        except Exception:
            pass

        if not stdout_b and not stderr_b and process.returncode is not None:
            break


class AbstractRouter(metaclass=abc.ABCMeta):
    def __init__(self) -> None:
        self._endpoints: Set[Endpoint] = set()
        self._master_endpoint: Optional[Endpoint] = None
        self._subprocess: Optional[asyncio.subprocess.Process] = None

        # Since this methods can fail we need to have the other variables defined
        # to avoid any problem in __del__
        self._binary = shutil.which(self.binary_name())
        self._logdir = pathlib.Path(tempfile.gettempdir())
        self._version = self._get_version()

    @staticmethod
    @abc.abstractmethod
    def name() -> str:
        pass

    @staticmethod
    @abc.abstractmethod
    def binary_name() -> str:
        pass

    @abc.abstractmethod
    def _get_version(self) -> Optional[str]:
        pass

    @staticmethod
    @abc.abstractmethod
    def is_ok() -> bool:
        pass

    @staticmethod
    @abc.abstractmethod
    def _validate_endpoint(endpoint: Endpoint) -> None:
        pass

    @abc.abstractmethod
    def assemble_command(self) -> str:
        pass

    @staticmethod
    def possible_interfaces() -> List[str]:
        return [subclass.name() for subclass in AbstractRouter.__subclasses__()]

    @staticmethod
    def available_interfaces() -> List[Type["AbstractRouter"]]:
        return list(filter(lambda subclass: subclass.is_ok, AbstractRouter.__subclasses__()))

    @staticmethod
    def get_interface(name: str) -> Type["AbstractRouter"]:
        for interface in AbstractRouter.__subclasses__():
            if interface.is_ok() and interface.name() == name:
                return interface
        raise RuntimeError("Interface is not ok or does not exist.")

    def binary(self) -> Optional[str]:
        return self._binary

    def version(self) -> Optional[str]:
        return self._version

    def set_master_endpoint(self, master_endpoint: Endpoint) -> None:
        self._master_endpoint = master_endpoint

    async def start(self, _verbose: bool = False) -> None:
        command = self.assemble_command()
        logger.debug(f"Calling router using following command: '{command}'.")

        try:
            self._subprocess = await asyncio.create_subprocess_shell(
                command, stdout=asyncio.subprocess.subprocess.PIPE, stderr=asyncio.subprocess.subprocess.PIPE
            )
            asyncio.create_task(log_async_subprocess(self._subprocess))
        except Exception as error:
            logger.error(f"Could not spawn async stream for Mavlink router subprocess. {error}")

        # Since the process takes some time to successfully start or fail, we need to wait before checking it's state
        await asyncio.sleep(1)
        if not self.is_running():
            exit_code = self._subprocess.returncode
            raise MavlinkRouterStartFail(f"Failed to initialize Mavlink router. Exit code: {exit_code}.")

    async def exit(self) -> None:
        if self.is_running():
            assert self._subprocess is not None
            await self._subprocess.kill()
        else:
            logger.info("Tried to stop router, but it was already not running.")

    async def restart(self) -> None:
        await self.exit()
        await self.start()

    def is_running(self) -> bool:
        return self._subprocess is not None and self._subprocess.returncode is None

    def process(self) -> Any:
        assert self._subprocess is not None
        return self._subprocess

    def logdir(self) -> pathlib.Path:
        return self._logdir

    def set_logdir(self, directory: pathlib.Path) -> None:
        if not directory.exists():
            raise ValueError(f"Logging directory {directory} does not exist.")
        self._logdir = directory

    def add_endpoint(self, endpoint: Endpoint) -> None:
        self._validate_endpoint(endpoint)

        if endpoint in self._endpoints:
            raise EndpointAlreadyExists(f"Endpoint '{endpoint.name}' already exists.")

        if endpoint.name in [endpoint.name for endpoint in self._endpoints]:
            raise DuplicateEndpointName(f"Name '{endpoint.name}' already being used by an existing endpoint.")

        self._endpoints.add(endpoint)

    def remove_endpoint(self, endpoint: Endpoint) -> None:
        if endpoint not in self._endpoints:
            raise EndpointDontExist(f"Endpoint '{endpoint.name}' not found.")

        self._endpoints.remove(endpoint)

    def endpoints(self) -> Set[Endpoint]:
        return self._endpoints

    def clear_endpoints(self) -> None:
        """Remove all output endpoints."""
        self._endpoints = set()

    def __del__(self) -> None:
        loop = asyncio.get_running_loop()
        loop.create_task(self.exit())
