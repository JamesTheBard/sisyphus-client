import os
import platform
import tomllib
import uuid

from box import Box

with open("pyproject.toml", 'rb') as f:
    pyproject = Box(tomllib.load(f))


class Config:
    API_URL = os.environ.get("API_URL", "http://localhost:5000")
    VERSION = pyproject.tool.poetry.version
    HOSTNAME = os.environ.get("HOSTNAME_OVERRIDE", platform.node())
    HOST_UUID = str(uuid.uuid4())
