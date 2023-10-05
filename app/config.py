import os
import platform
import tomllib
import uuid
from zoneinfo import ZoneInfo

from box import Box

with open("pyproject.toml", 'rb') as f:
    pyproject = Box(tomllib.load(f))

with open("modules.toml", 'rb') as f:
    modules = Box(tomllib.load(f))


class Config:
    API_URL = os.environ.get("API_URL", "http://localhost:5000")
    API_TIMEZONE = ZoneInfo(os.environ.get("API_TIMEZONE", "UTC"))
    VERSION = pyproject.tool.poetry.version
    HOSTNAME = os.environ.get("HOSTNAME_OVERRIDE", platform.node())
    HOST_UUID = os.environ.get("HOST_UUID", str(uuid.uuid4()))
    HEARTBEAT_INTERVAL = int(os.environ.get("HEARTBEAT_INTERVAL", "5"))
    QUEUE_POLL_INTERVAL = int(os.environ.get("QUEUE_POLL_INTERVAL", "10"))
    NETWORK_RETRY_INTERVAL = int(
        os.environ.get("NETWORK_RETRY_INTERVAL", "20"))
    MODULES = modules.enabled
