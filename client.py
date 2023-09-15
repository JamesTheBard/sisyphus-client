import importlib
import json
import time
from datetime import datetime
import traceback

import requests
from box import Box
from loguru import logger

from app.config import Config
from app.exceptions import (CleanupError, InitializationError, RunError,
                            ValidationError)
from app.heartbeat import heartbeat

# Start the heartbeat
logger.info("Starting client")
logger.info(f"Worker ID..........: {Config.HOST_UUID}")
logger.info(f"Hostname...........: {Config.HOSTNAME}")
logger.info(f"Sisyphus Server URL: {Config.API_URL}")
heartbeat.interval = 5
heartbeat.set_startup()
heartbeat.start()
logger.debug(f"Heartbeat started, sending info to {Config.API_URL}")

# Processing loop
empty_queue = False
while True:
    heartbeat.set_idle()
    time.sleep(5)

    # Check to see if the entire queue is disabled
    r = requests.get(Config.API_URL + '/queue')
    data = Box(json.loads(r.content))
    if data.attributes.disabled:
        logger.info("The main server queue is disabled")
        continue

    # Check to see if we're 'allowed' to process the queue
    r = requests.get(Config.API_URL + '/workers/' + Config.HOST_UUID)
    data = Box(json.loads(r.content))
    if data.attributes.disabled:
        logger.info("The worker is disabled on the main server")
        continue

    # Pull a task off the queue
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
    heartbeat.job_id = data.job_id

    # Start running tasks
    start_time = datetime.now()
    logger.info(f"Found tasks in job: {', '.join(data.tasks.keys())}")
    job_failed = True
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
            module.run()
            module.cleanup()
        except ValidationError as e:
            logger.warning(f"Could not validate task data: {e.message}")
            logger.warning(f"Aborting job: {data.job_id} -> {task}")
            logger.warning(f"Module runtime: {module.get_duration()}")
            break
        except RunError as e:
            logger.warning(f"Failed to run task: {e.message}")
            logger.warning(f"Aborting job: {data.job_id} -> {task}")
            logger.warning(f"Module runtime: {module.get_duration()}")
            break
        except CleanupError as e:
            logger.warning(f"Failed to cleanup task: {e.message}")
            logger.warning(f"Aborting job: {data.job_id} -> {task}")
            logger.warning(f"Module runtime: {module.get_duration()}")
            break
        except:
            logger.warning(f"Unknown failure on task!")
            logger.warning(f"Aborting job: {data.job_id} -> {task}")
            logger.warning(f"Module runtime: {module.get_duration()}")
            break
        
        job_failed = False

        logger.info(f"Module runtime: {module.get_duration()}")
    
    job_log_level = "WARNING" if job_failed else "SUCCESS"
    logger.log(job_log_level, f"Job runtime: {datetime.now() - start_time}")
