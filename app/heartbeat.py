import threading
import logging
import requests
import time
from app.config import Config
from box import Box


class Heartbeat:
    def __init__(self, interval: int = 10):
        self.interval = 1
        self.endpoint = Config.API_URL + '/workers/' + Config.HOST_UUID
        self.set_idle()
        self.thread = threading.Thread(target=self._send_heartbeat)
        self.thread.daemon = True

    def start(self):
        self.thread.start()

    def set_data(self, data: dict):
        data = Box(data)
        data.hostname = Config.HOSTNAME
        data.version = Config.VERSION
        data.worker_id = Config.HOST_UUID

    def set_idle(self):
        self.message = Box({
            "hostname": Config.HOSTNAME,
            "status": "idle",
            "version": Config.VERSION,
        })

    def set_startup(self):
        self.message = Box({
            "hostname": Config.HOSTNAME,
            "status": "startup",
            "version": Config.VERSION,
        })

    def _send_heartbeat(self):
        while True:
            requests.post(self.endpoint, json=self.message)
            time.sleep(self.interval)

heartbeat = Heartbeat()
