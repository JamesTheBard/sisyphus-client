from box import Box
from jsonschema.exceptions import JsonExceptions
from loguru import logger
from mkvextract import MkvExtract as M

from app.exceptions import RunError, ValidationError
from modules.base import BaseModule


class Mkvextract(BaseModule):
    """The Mkvextract module used to extract tracks and other information from a Matroska file.

    Attributes:
        heartbeat (Heartbeat): The heartbeat object for sending status back to the API server
        task (Box): The data that contains the task information to run from the job
        start_time (datetime): The time the module was initialized (task start time)
        mkvextract (MkvExtract): The `sisyphus-ffmpeg` module for processing `ffmpeg` tasks
    """
    mkvextract: M

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
            raise RunError(
                f"The 'mkvextract' command exited with error code: {return_code}")
