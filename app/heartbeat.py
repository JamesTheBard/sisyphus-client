import logging
import threading
import time
from datetime import datetime
from typing import Optional

import requests
from box import Box
from loguru import logger

from app.config import Config


class Heartbeat:
    """The heartbeat class used to communicate status back to the central API server.

    Attributes:
        endpoint (str): The URL to used to send updates to the API server
        interval (int): The number of seconds between sending updates back to the API server
        job_id (str, optional): If processing a job, the `job_id` in progress, otherwise None.
        job_title (str, optional): If processing a job, the `job_title` in progress, otherwise None.
        thread (threading.Thread): The thread used to send updates to the API server in the background.
    """
    interval: int
    endpoint: str
    job_id: Optional[str]
    job_title: Optional[str]
    thread: threading.Thread
    start_time: Optional[datetime]

    def __init__(self, interval: int = 10):
        """Initializes the instance based on the provided interval.

        Args:
            interval (int, optional): The number of seconds between sending updates back to the API server. Defaults to 10.
        """
        self.interval = interval
        self.endpoint = Config.API_URL + '/workers/' + Config.HOST_UUID
        self.job_id = None
        self.job_title = None
        self.start_time = None
        self.set_idle()
        self.thread = threading.Thread(target=self.send_heartbeat)
        self.thread.daemon = True

    def start(self) -> None:
        """Start the background thread to send updates to the API server.
        """
        self.start_time = datetime.now()
        self.thread.start()

    def set_data(self, data: dict) -> None:
        """Update the heartbeat status data sent to the API server.

        Args:
            data (dict): The data to include in the status message
        """
        data = Box(data)
        data.hostname = Config.HOSTNAME
        data.version = Config.VERSION
        data.online_at = str(self.start_time)
        if self.job_id:
            data.job_id = self.job_id
        if self.job_title:
            data.job_title = self.job_title
        self.message = data

    def set_idle(self) -> None:
        """Update the heartbeat status to idle.
        """
        self.job_id = None
        self.set_data({"status": "idle"})

    def set_startup(self) -> None:
        """Update the heartbeat status to startup.
        """
        self.job_id = None
        self.set_data({"status": "startup"})

    def set_in_progress(self, data: dict) -> None:
        """Update the heartbeat status to in progress using the provided data.

        Args:
            data (dict): The data to send to the central API server.
        """
        status = {"status": "in_progress"}
        data = data | status
        self.set_data(data)

    def send_heartbeat(self) -> None:
        """Send the heartbeat to the API server.
        """
        while True:
            logger.debug(f"Sending status message: {self.message}")
            requests.post(self.endpoint, json=self.message)
            time.sleep(self.interval)


heartbeat = Heartbeat()
