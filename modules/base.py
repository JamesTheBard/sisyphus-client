from app.heartbeat import heartbeat

class BaseModule:
    def __init__(self, task):
        self.heartbeat = heartbeat
        self.task = task
        # pass

    def validate(self):
        pass

    def run(self):
        pass

    def cleanup(self):
        pass

    def send_heartbeat(self):
        pass
