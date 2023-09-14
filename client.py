import importlib
import json
import time
from datetime import datetime

import requests
from box import Box
from loguru import logger

from app.config import Config
from app.exceptions import InitializationError, ValidationError, RunError
from app.heartbeat import heartbeat

# Start the heartbeat
logger.level("INFO")
logger.info("Starting client")
heartbeat.interval = 5
heartbeat.set_startup()
logger.debug(f"Heartbeat started, sending info to {Config.API_URL}")
heartbeat.start()

# time.sleep(10)

empty_queue = False
while True:
    heartbeat.set_idle()
    time.sleep(5)
    # Get a task from the server
    r = requests.get(Config.API_URL + '/queue')
    data = Box(json.loads(r.content))
    if data.attributes.disabled:
        logger.info("The main server queue is disabled")
        continue

    r = requests.get(Config.API_URL + '/workers/' + Config.HOST_UUID)
    data = Box(json.loads(r.content))
    if data.attributes.disabled:
        logger.info("The worker is disabled on the main server")
        continue

    r = requests.get(Config.API_URL + '/queue/poll')
    if r.status_code == 404:
        if not empty_queue:
            logger.info("There are currently no jobs on the queue")
            empty_queue = True
        continue

    empty_queue = False

    data = Box(json.loads(r.content))

    # Update heartbeat
    heartbeat.message.status = "in_progress"
    heartbeat.message.job_id = data.job_id
    logger.info(f"Starting job: {data.job_id}")
    logger.info(f"Job title: {data.job_title}")

    # Start running tasks
    start_time = datetime.now()
    logger.info(f"Found tasks in job: {', '.join(data.tasks.keys())}")
    for task, task_data in data.tasks.items():
        logger.info(f"Starting task: {task}")
        module_path = f"modules.{task}"

        try:
            module = getattr(importlib.import_module(
                module_path), task.capitalize())
            module = module(task=task_data)
        except InitializationError as e:
            logger.warning(f"Could not initialize module: {e.message}")
            logger.warning(f"Aborting job: {data.job_id}")
            break

        try:
            module.validate()
        except ValidationError as e:
            logger.warning(f"Could not validate task data: {e.message}")
            logger.warning(f"Aborting job: {data.job_id} -> {task}")
            logger.warning(f"Module runtime: {module.get_duration()}")
            break

        try:
            module.run()
        except RunError as e:
            logger.warning(f"Failed to run task: {e.message}")
            logger.warning(f"Aborting job: {data.job_id} -> {task}")
            logger.warning(f"Module runtime: {module.get_duration()}")
            break

        module.cleanup()
        logger.info(f"Module runtime: {module.get_duration()}")

    logger.success(f"Job runtime: {datetime.now() - start_time}")
