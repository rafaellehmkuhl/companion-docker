#!/usr/bin/env python3

import os
import ssl

from setuptools import setup

# Ignore ssl if it fails
if not os.environ.get("PYTHONHTTPSVERIFY", "") and getattr(ssl, "_create_unverified_context", None):
    ssl._create_default_https_context = ssl._create_unverified_context

setup(
    name="ping_service",
    version="0.1.0",
    description="Ping service for BlueRobotics' Ping1D and Pìng360",
    license="MIT",
    install_requires=["pyserial == 3.5", "bluerobotics-ping == 0.1.0"],
)
