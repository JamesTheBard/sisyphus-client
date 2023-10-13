import re
import subprocess
import time
from pathlib import Path

from box import Box
from handbrake.parser import Parser
from jsonschema import exceptions as JsonExceptions
from loguru import logger

from app.config import Config
from app.exceptions import RunError, ValidationError
from ffprobe import Ffprobe
from modules.base import BaseModule


class Handbrake(BaseModule):
    """The Hanbrake module used to perform encoding.

    Attributes:
        heartbeat (Heartbeat): The heartbeat object for sending status back to the API server
        task (Box): The data that contains the task information to run from the job
        start_time (datetime): The time the module was initialized (task start time)
        handbrake (Parser): The `sisyphus-handbrake` module for processing `handbrake` tasks
    """
    handbrake: Parser

    def __init__(self, task):
        super().__init__(task)
        logger.info("Module loaded successfully.")
        logger.debug(f"Data: {self.task}")
        self.status = Box({
            "status": "in_progress",
            "task": "handbrake"
        })
        self.heartbeat.set_data(self.status)
        self.handbrake = Parser()

    def validate(self):
        try:
            self.handbrake.load_from_object(self.task)
        except JsonExceptions.ValidationError as e:
            raise ValidationError(f"Could not validate task: {e.message}, {e.json_path}")
        logger.info("Task data validated successfully.")

    def run_encode(self) -> int:
        """Run the actual encode using Handbrake.

        Returns:
            int: The exit/return code of HandBrakeCLI.
        """
        ffprobe = Ffprobe(self.handbrake.data.source)
        frames = ffprobe.get_streams("video")[0].frames
        frames = frames if frames else None

        command = self.handbrake.generate_command()
        if "--json" not in command:
                command.append("--json")
                
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )

        working_state = False
        while True:
            time.sleep(1)
            if (return_code := process.poll()) is not None:
                break
            for line in process.stdout:
                if not working_state:
                    if match := re.search(r'"WORKING"', line.decode()):
                        working_state = True
                if (match := re.search(r'"Progress": (\d+\.\d+)', line.decode())) and working_state:
                    completed_perc = float(match.group(1))
                    encode_progress = int(completed_perc * frames) if frames else None
                
                    self.status.info = {
                        "current_frame": encode_progress,
                    }
                    if frames:
                        self.status.info.total_frames = frames
                        self.status.progress = encode_progress / frames * 100
                    self.heartbeat.set_data(self.status)
        
        return process.returncode

    def run(self):
        """Run the encode with HandBrakeCLI.

        Raises:
            RunError: HandBrakeCLI fails to complete the encode successfully.
        """
        self.set_start_time()
        logger.info(f"Running handbrake encoding task")
        while True:
            return_code = self.run_encode()
            if return_code != 0:
                command = self.handbrake.generate_command(as_string=True)
                raise RunError(
                    f"The `HandBrakeCLI` command returned exit code {return_code}, command: {' '.join(command)}")
            return
