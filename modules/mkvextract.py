from modules.base import BaseModule
from mkvextract import MkvExtract as M
from jsonschema.exceptions import JsonExceptions
from app.exceptions import ValidationError, RunError
from loguru import logger

class Mkvextract(BaseModule):
    def __init__(self, task):
        super().__init__(task)
        logger.info("Module loaded successfully.")
        logger.debug(f"Data: {self.task}")
        self.status = Box({
            "status": "in_progress",
            "task": "mkvextract"
        })
        self.heartbeat.set_data(self.status)
        self.mkvextract = M()

    def validate(self):
        try:
            self.mkvextract.load_from_object(self.task)
        except JsonExceptions.ValidationError as e:
            raise ValidationError(e.message)

        logger.info("Task data validated successfully.")
        logger.debug(f"Task data: {self.task}")

    def run(self):
        logger.info("Running 'mkvextract' task")
        return_code = self.mkvextract.extract()
        if return_code != 0:
            raise RunError(f"The 'mkvextract' command exited with error code: {return_code}")
