import json
import os
import shutil
from pathlib import Path
from typing import List, Dict

import jsonschema
from box import Box
from loguru import logger

from app.exceptions import RunError, ValidationError
from modules.base import BaseModule


class Cleanup(BaseModule):
    """A post-job cleanup module used to move, copy, and delete files.

    Attributes:
        heartbeat (Heartbeat): The heartbeat object for sending status back to the API server
        task (Box): The data that contains the task information to run from the job
        start_time (datetime): The time the module was initialized (task start time)
    """
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

    def _delete(self, list_of_files: List[str]) -> None:
        """Delete files on the filesystem.

        Args:
            list_of_files (List[str]): List of files to delete.

        Raises:
            RunError: Cannot delete a file provided.
        """
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
            raise RunError(f"OS error raised when deleting file: {str(f)}")

        except PermissionError as e:
            raise RunError(e.message)

    def _move(self, data: List[Dict[str, str]]) -> None:
        """Move files in the filesystem.

        Args:
            data (List[dict[str, str]]): A list of source/destination paths.

        Raises:
            RunError: Cannot move the source file to the given destination path
        """
        try:
            for i in data:
                src, dest = Path(i["source"]), Path(i["destination"])
                shutil.copy2(src, dest)
                src.unlink()
                logger.debug(f"Moved file: {str(src)} -> {str(dest)}")
        except OSError as e:
            raise RunError(f"OS error raised when moving file: {str(src)} -> {str(dest)}")
        except FileNotFoundError as e:
            raise RunError(f"File not found during move: {e.filename}")
        except PermissionError as e:
            raise RunError(e.message)

    def _copy(self, data: List[Dict[str, str]]) -> None:
        """Copy files in the filesystem.

        Args:
            data (List[dict[str, str]]): A list of source/destination paths.

        Raises:
            RunError: Cannot copy the source file to the given destination path
        """
        try:
            for i in data:
                src, dest = Path(i["source"]), Path(i["destination"])
                shutil.copy2(src, dest)
                logger.debug(f"Copied file: {str(src)} -> {str(dest)}")
        except OSError as e:
            raise RunError(f"OS error raised when copying file: {str(src)} -> {str(dest)}")
        except FileNotFoundError as e:
            raise RunError(f"File not found during copy: {e.filename}")
        except PermissionError as e:
            raise RunError(e.message)
