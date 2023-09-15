from box import Box
from jsonschema import exceptions as JsonExceptions
from loguru import logger
from matroska import Matroska as M

from app.exceptions import RunError, ValidationError
from modules.base import BaseModule


class Matroska(BaseModule):
    def __init__(self, task):
        super().__init__(task)
        logger.info("Module loaded successfully.")
        logger.debug(f"Data: {self.task}")
        self.status = Box({
            "status": "in_progress",
            "task": "matroska"
        })
        self.heartbeat.set_data(self.status)
        self.matroska = M()

    def validate(self):
        try:
            self.matroska.load_from_object(self.task)
        except JsonExceptions.ValidationError as e:
            raise ValidationError(e.message)

        logger.info("Task data validated successfully.")

    def run(self):
        command = self.matroska.generate_command(as_string=True)
        logger.debug("Command to run: {command}")
        logger.info("Running mkvmerge muxing task")

        return_code = self.matroska.mux(delete_temp=True)
        if return_code != 0:
            raise RunError(
                f"The `mkvmerge` command returned exit code {return_code}, command: {command}")
