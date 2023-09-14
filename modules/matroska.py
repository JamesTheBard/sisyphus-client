from modules.base import BaseModule
from loguru import logger


class Matroska(BaseModule):
    def __init__(self, task):
        super().__init__(task)
        logger.info("Module loaded successfully.")

