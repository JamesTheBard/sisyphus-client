from modules.base import BaseModule
from loguru import logger
from ffmpeg import Ffmpeg as F
from jsonschema import exceptions as JsonExceptions
from app.exceptions import ValidationError



class Ffmpeg(BaseModule):
    def __init__(self, task):
        super().__init__(task)
        logger.info("Module loaded successfully.")
        logger.debug(f"Data: {self.task}")
        self.ffmpeg = F()

    def validate(self):
        try:
            self.ffmpeg.load_from_object(self.task)
        except JsonExceptions.ValidationError as e:
            raise ValidationError(e.message)
        logger.info("Data validated successfully.")