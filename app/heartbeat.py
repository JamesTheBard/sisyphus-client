import threading
import logging
import requests
import time
from app.config import Config
from box import Box
from loguru import logger


class Heartbeat:
    def __init__(self, interval: int = 10):
        self.interval = interval
        self.endpoint = Config.API_URL + '/workers/' + Config.HOST_UUID
        self.set_idle()
        self.thread = threading.Thread(target=self.send_heartbeat)
        self.thread.daemon = True
        self.job_id = None

    def start(self):
        self.thread.start()

    def set_data(self, data: dict):
        data = Box(data)
        data.hostname = Config.HOSTNAME
        data.version = Config.VERSION
        if self.job_id:
            data.job_id = self.job_id
        self.message = data

    def set_idle(self):
        self.job_id = None
        self.set_data({"status": "idle"})

    def set_startup(self):
        self.job_id = None
        self.set_data({"status": "startup"})
        
    def set_in_progress(self, data: dict):
        status = {"status": "in_progress"}
        data = data | status
        self.set_data(data)

    def send_heartbeat(self):
        while True:
            logger.debug(f"Sending status message: {self.message}")
            requests.post(self.endpoint, json=self.message)
            time.sleep(self.interval)

heartbeat = Heartbeat()
