import re
import subprocess
import time
from pathlib import Path

from box import Box

from config import Config
from helpers.ffmpeg import FfmpegInfo
from helpers.handbrake import Handbrake as Hb
from helpers.handbrake import HandbrakeTrack
from modules.base import BaseModule
from modules.exceptions import JobRunFailureError, JobValidationError


class Handbrake(BaseModule):
    def __init__(self, data: dict, job_title: str):
        super().__init__(data, job_title)
        self.module_name = "handbrake"
        if "HANDBRAKE_CLI_PATH" in list(Config.__dict__):
            self.encoder = Hb(cli_path=getattr(Config, "HANDBRAKE_CLI_PATH"))
        else:
            self.encoder = Hb()

    def process_data(self):
        self.encoder.source = self.data.source
        self.encoder.output_file = self.data.output_file

        # Go through each group and put the data where Handbrake expects it to be.  If it's not there, no big deal,
        # just skip it as the default for the module is an empty Box.
        option_sections = [
            "general",
            "source",
            "destination",
            "video",
            "picture",
            "filters",
        ]
        for option in option_sections:
            try:
                setattr(
                    self.encoder, f"{option}_options", self.data[f"{option}_options"]
                )
            except KeyError:
                pass

        # Need to add all the tracks to the audio and subtitle sections.  Again, if there are no audio or subtitle
        # tracks associated with it, then it's not an issue.
        track_sections = [
            "audio",
            "subtitle",
        ]
        for section in track_sections:
            try:
                for track in self.data[f"{section}_tracks"]:
                    a = getattr(self.encoder, f"{section}_tracks")
                    a.append(HandbrakeTrack(**track))
            except TypeError:
                raise JobValidationError(
                    message=f'Only "track" and "option" definitions allowed in {section} track!',
                    module=self.module_name,
                )
            except KeyError:
                pass

    def run(self):
        self.process_data()
        total_frames = (
            FfmpegInfo(source_file=self.encoder.source).video_tracks[0].frames
        )
        command = self.encoder.generate_cli()
        if "--json" not in command:
            command.append("--json")
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )

        while True:
            time.sleep(1)
            if (return_code := process.poll()) is not None:
                break
            for line in process.stdout:
                if match := re.search(r'"Progress": (\d+\.\d+)', line.decode()):
                    completed_perc = float(match.group(1))
                    progress = {
                        "current_frame": int(completed_perc * total_frames),
                        "total_frames": total_frames,
                        "percent_complete": "{:0.2f}".format(completed_perc * 100),
                    }
                    self.update_progress(progress)

        if return_code != 0:
            raise JobRunFailureError(
                message=f"'{self.module_name}' returned exit code {return_code}: {command}",
                module=self.module_name,
            )
        return True

    def validate(self):
        # Verify that the encoder actually exists if given via the cli_path variable
        if not self.encoder.cli_path.exists():
            raise JobValidationError(
                message=f"Could not find the HandBrake CLI binary at '{self.encoder.cli_path.absolute()}'",
                module=self.module_name,
            )

        # Verify that the source is specified in the data
        if "source" not in self.data.keys():
            raise JobValidationError(
                message="No source file specified.", module=self.module_name
            )

        # Make sure that the input and output options aren't actually used.  The default style
        # for these are the "source" and "output_file" settings in the data
        for section in self.data.values():
            if type(section) is Box:
                keys = set(section.keys())
                illegal = {"i", "input", "o", "output"}
                if keys.intersection(illegal):
                    raise JobValidationError(
                        message=f"Cannot set input/output files via option sections!",
                        module=self.module_name,
                    )

        # Make sure that the source actually exists and is a file
        if not Path(self.data.source).exists() or not Path(self.data.source).is_file():
            raise JobValidationError(
                message=f"The source file '{Path(self.data.source).absolute()}' either does not exist "
                f"or is not a file.",
                module=self.module_name,
            )

        # Verify that there is an actual output file
        if "output_file" not in self.data.keys():
            raise JobValidationError(
                message=f"There is no output file defined in the job, abandoning job.",
                module=self.module_name,
            )
