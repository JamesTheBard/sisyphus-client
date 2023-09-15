from app.heartbeat import heartbeat
from box import Box
from datetime import datetime
from loguru import logger

class BaseModule:
    def __init__(self, task):
        self.heartbeat = heartbeat
        self.task = Box(task)
        self.start_time = datetime.now()
        # pass

    def validate(self):
        logger.info("No validation actions, skipping")

    def run(self):
        logger.info("No run actions, skipping")

    def cleanup(self):
        pass

    def send_heartbeat(self):
        pass

    def get_duration(self):
        return datetime.now() - self.start_time
