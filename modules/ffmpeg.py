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

    def run(self):
        command = self.ffmpeg.generate_command()
        info = self.ffmpeg.get_primary_video_information()
        logger.debug(f"Video information: {info}")
        logger.debug(f"Command to run: {command}")
        logger.info(f"Running ffmpeg encoding task")
        command = shlex.split(command)
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        
        while True:
            time.sleep(1)
            if (return_code := process.poll()):
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
                    
        if return_code != 0:
            raise RunError(f"The `ffmpeg` command returned exit code {return_code}, command: {' '.join(command)}")
                

    def get_options_from_server(self) -> bool:
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
