from datetime import datetime
from typing import Union

from box import Box
from loguru import logger

from app.exceptions import (CleanupError, InitializationError, RunError,
                            ValidationError)
from app.heartbeat import Heartbeat, heartbeat


class BaseModule:
    """The base Sisyphus module for tasks.

    Attributes:
        heartbeat (Heartbeat): The heartbeat object for sending status back to the API server
        task (Box): The data that contains the task information to run from the job
        start_time (datetime): The time the module was initialized (task start time)
    """
    heartbeat: Heartbeat
    task: Box
    start_time: datetime

    def __init__(self, task: Union[dict, Box]):
        """Initializes the instance based on task information.

        Args:
            task (Union[dict, Box]): The task data from the main job

        Raises:
            InitializationError: An error occured when initializing the module.
        """
        self.heartbeat = heartbeat
        self.task = Box(task)
        self.start_time = datetime.now()
        # pass

    def validate(self) -> None:
        """Validates the task data before execution.

        Raises:
            ValidationError: An error occured when attempting to validate the data.
        """
        logger.info("No validation actions, skipping")

    def run(self) -> None:
        """Run the task.

        Raises:
            RunError: An error occured when running the module.
        """
        logger.info("No run actions, skipping")

    def cleanup(self) -> None:
        """Perform cleanup tasks associated with the module.

        Raises:
            CleanupError: An error occured when cleaning up after module execution.
        """
        pass

    def get_duration(self) -> datetime:
        """Return the amount of time the module has run since it started.

        Returns:
            datetime: The time elapsed since module start
        """
        return datetime.now() - self.start_time
