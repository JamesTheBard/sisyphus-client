from box import Box
from jsonschema import exceptions as JsonExceptions
from loguru import logger
from mkvmerge import MkvMerge as M

from app.exceptions import RunError, ValidationError
from modules.base import BaseModule


class Mkvmerge(BaseModule):
    """The Mkvmerge module used to merge tracks and other information into a Matroska file.

    Attributes:
        heartbeat (Heartbeat): The heartbeat object for sending status back to the API server
        task (Box): The data that contains the task information to run from the job
        start_time (datetime): The time the module was initialized (task start time)
        mkvmerge (MkvMerge): The `sisyphus-ffmpeg` module for processing `ffmpeg` tasks
    """
    mkvmerge: M

    def __init__(self, task):
        super().__init__(task)
        logger.info("Module loaded successfully.")
        logger.debug(f"Data: {self.task}")
        self.status = Box({
            "status": "in_progress",
            "task": "mkvmerge"
        })
        self.heartbeat.set_data(self.status)
        self.mkvmerge = M()

    def validate(self):
        try:
            self.mkvmerge.load_from_object(self.task)
        except JsonExceptions.ValidationError as e:
            raise ValidationError(e.message)

        logger.info("Task data validated successfully.")

    def run(self):
        self.mkvmerge.reload_source_information()
        logger.info("Rescanned source information.")
        
        for source in self.mkvmerge.sources:
            if not source.source_file.exists:
                raise RunError(f"The source file '{str(source.source_file)}' does not exist!")
            if not len(source.info):
                raise RunError(f"The source file '{str(source.source_file)}' is either corrupt or has no track information associated with it!")
            
        command = self.mkvmerge.generate_command(as_string=True)
        logger.debug("Command to run: {command}")
        logger.info("Running mkvmerge muxing task")
        
        return_code = self.mkvmerge.mux(delete_temp=True)
        if return_code != 0:
            raise RunError(
                f"The `mkvmerge` command returned exit code {return_code}, command: {command}")
