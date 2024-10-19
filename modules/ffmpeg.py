import json
import re
import shlex
import subprocess
import time
from pathlib import Path

import box
import requests
from box import Box
from ffmpeg import Ffmpeg as F
from jsonschema import exceptions as JsonExceptions
from loguru import logger

from app.config import Config
from app.exceptions import RunError, ValidationError
from modules.base import BaseModule


class Ffmpeg(BaseModule):
    """The Ffmpeg module used to perform encoding.

    Attributes:
        heartbeat (Heartbeat): The heartbeat object for sending status back to the API server
        task (Box): The data that contains the task information to run from the job
        start_time (datetime): The time the module was initialized (task start time)
        ffmpeg (Ffmpeg): The `sisyphus-ffmpeg` module for processing `ffmpeg` tasks
    """
    ffmpeg: F

    def __init__(self, task):
        super().__init__(task)
        logger.info("Module loaded successfully.")
        logger.debug(f"Data: {self.task}")
        self.status = Box({
            "status": "in_progress",
            "task": "ffmpeg"
        })
        self.heartbeat.set_data(self.status)
        self.ffmpeg = F()

    def validate(self):
        for source in self.task.sources:
            source = Path(source)
            if not source.exists() or not source.is_file():
                raise ValidationError(
                    f"Source '{str(source.absolute())}' does not exist.")

        try:
            self.ffmpeg.load_from_object(self.task)
        except JsonExceptions.ValidationError as e:
            raise ValidationError(e.message)

        if self.get_options_from_server():
            try:
                self.ffmpeg.load_from_object(self.task)
            except JsonExceptions.ValidationError as e:
                raise ValidationError(e.message)

        logger.info("Task data validated successfully.")

    def run_encode(self) -> int:
        """Run the actual encode using Ffmpeg.

        Returns:
            int: The exit/return code of Ffmpeg.
        """
        command = self.ffmpeg.generate_command()
        info = self.ffmpeg.get_primary_video_information()
        logger.debug(f"Video information: {info}")
        logger.debug(f"Command to run: {command}")
        command = shlex.split(command)
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        while True:
            time.sleep(1)
            if (return_code := process.poll()) is not None:
                break
            for line in process.stdout:
                if match := re.search(r"frame=(\s*\d+)", line.decode()):
                    current_frame = int(match.group(1))
                    self.status.info = {
                        "current_frame": current_frame,
                    }
                    if info.frames:
                        self.status.info.total_frames = info.frames
                        self.status.progress = current_frame / info.frames * 100
                    self.heartbeat.set_data(self.status)
                    
        return return_code

    def run(self):
        """Run the encode with Ffmpeg.

        Raises:
            RunError: Ffmpeg fails to complete the encode successfully.
        """
        self.set_start_time()
        logger.info(f"Running ffmpeg encoding task")
        while True:
            return_code = self.run_encode()
        
            # This is here because of some issues with ffmpeg in the past.
            if return_code == -11:
                logger.warning("Encountered error with encode (SIGSEGV), restarting encode.")
                continue
                
            if return_code != 0:
                command = self.ffmpeg.generate_command()
                raise RunError(
                    f"The `ffmpeg` command returned exit code {return_code}, command: {command}")
                
            return

    def get_options_from_server(self) -> bool:
        """Retrieves module option set data from the API server.

        Raises:
            ValidationError: Cannot find the requested option set data from the API server.

        Returns:
            bool: Returns `True` if the task data has changed, otherwise `False`
        """
        has_changed = False
        for output_map in self.task.get("output_maps", []):
            output_map_keys = output_map.keys()
            if "option_set" in output_map_keys:
                has_changed = True
                logger.info(f"Retrieving option set: {output_map.option_set}")
                r = requests.get(Config.API_URL +
                                 "/data/ffmpeg/" + output_map.option_set)
                if r.status_code == 404:
                    raise ValidationError(
                        f"Could not find server-side option set '{output_map.option_set}'")
                options = Box(json.loads(r.content)).options
                output_map.options = output_map.get("options", {}) | options
                output_map.pop("option_set")

        if has_changed:
            logger.debug(f"Updated data: {self.task}")

        return has_changed
