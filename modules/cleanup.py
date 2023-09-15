import json
import os
import shutil
from pathlib import Path

import jsonschema
from box import Box
from loguru import logger

from app.exceptions import RunError, ValidationError
from modules.base import BaseModule


class Cleanup(BaseModule):
    def __init__(self, task):
        super().__init__(task)
        logger.info("Module loaded successfully.")
        logger.debug(f"Data: {self.task}")
        self.status = Box({
            "status": "in_progress",
            "task": "cleanup"
        })
        self.heartbeat.set_data(self.status)
        schema_path = Path(
            os.path.dirname(os.path.abspath(__file__)))
        self.schema = schema_path / Path('schema/cleanup.schema.json')

    def validate(self):
        with self.schema.open('r') as f:
            schema = json.load(f)

        try:
            jsonschema.validate(self.task, schema)
        except jsonschema.ValidationError as e:
            raise ValidationError(e.message)

        logger.info("Task data validated successfully.")

    def run(self):
        logger.info("Running cleanup tasks")
        for k, v in self.task.items():
            getattr(self, f"_{k}")(v)

    def _delete(self, list_of_files: list[str]):
        files = [Path(i) for i in list_of_files]
        try:
            for f in files:
                if f.is_file():
                    f.unlink(missing_ok=True)
                    logger.debug(f"Deleted file: {str(f)}")
                if f.is_dir():
                    f.rmdir()
                    logger.debug(f"Removed empty directory: {str(f)}")
                else:
                    logger.debug(f"Skipping: {str(f)}")
        except OSError as e:
            raise RunError(e.message)
        except PermissionError as e:
            raise RunError(e.message)

    def _move(self, data: list):
        try:
            for i in data:
                src, dest = Path(i["source"]), Path(i["destination"])
                src.rename(dest)
                logger.debug(f"Moved file: {str(src)} -> {str(dest)}")
        except OSError as e:
            raise RunError(e.message)
        except PermissionError as e:
            raise RunError(e.message)

    def _copy(self, data: list):
        try:
            for i in data:
                src, dest = Path(i["source"]), Path(i["destination"])
                shutil.copy(src, dest)
                logger.debug(f"Copied file: {str(src)} -> {str(dest)}")
        except OSError as e:
            raise RunError(e.message)
        except PermissionError as e:
            raise RunError(e.message)
