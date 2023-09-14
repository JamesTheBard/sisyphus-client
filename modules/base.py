from app.heartbeat import heartbeat
from box import Box
from datetime import datetime

class BaseModule:
    def __init__(self, task):
        self.heartbeat = heartbeat
        self.task = Box(task)
        self.start_time = datetime.now()
        # pass

    def validate(self):
        pass

    def run(self):
        pass

    def cleanup(self):
        pass

    def send_heartbeat(self):
        pass

    def get_duration(self):
        return datetime.now() - self.start_time
