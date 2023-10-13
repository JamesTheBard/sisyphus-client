import importlib.util
import importlib
import json
import time
from typing import Optional
from datetime import datetime

import requests
from box import Box
from loguru import logger

from app.config import Config
from app.exceptions import (CleanupError, InitializationError, RunError,
                            ValidationError, NetworkError)
from app.heartbeat import heartbeat
from app.tasks import connect_to_api, validate_modules, complete_job

# Start the heartbeat
logger.info(f"Starting 'sisyphus-client', version {Config.VERSION}")
logger.info(f"Worker ID..........: {Config.HOST_UUID}")
logger.info(f"Hostname...........: {Config.HOSTNAME}")
logger.info(f"Sisyphus Server....: {Config.API_URL}")
heartbeat.interval = Config.HEARTBEAT_INTERVAL
heartbeat.set_startup()
heartbeat.start()
logger.debug(f"Heartbeat started, sending info to {Config.API_URL}")

# Processing loop
last_error: Optional[str] = None
queue_disabled = False
worker_disabled = False

while True:
    heartbeat.set_idle()
    time.sleep(Config.QUEUE_POLL_INTERVAL)

    # Check to see if the entire queue is disabled
    try:
        r = connect_to_api(
            "GET", "/queue", "Error polling API queue for status!")
    except NetworkError as e:
        if last_error != "ERR_QUEUE_STATUS":
            logger.warning(e.message)
        last_error = "ERR_QUEUE_STATUS"
        time.sleep(Config.NETWORK_RETRY_INTERVAL)
        continue

    data = Box(json.loads(r.content))
    if data.attributes.disabled:
        if last_error != "ERR_QUEUE_DISABLED":
            logger.info("The main server queue is disabled")
            last_error = "ERR_QUEUE_DISABLED"
        continue

    # Check to see if we're 'allowed' to process the queue
    try:
        r = connect_to_api("GET", "/workers/" + Config.HOST_UUID,
                           "Error polling worker for queue permissions!")
    except NetworkError as e:
        if last_error != "ERR_WORKER_STATUS":
            logger.warning(e.message)
        last_error = "ERR_WORKER_STATUS"
        time.sleep(Config.NETWORK_RETRY_INTERVAL)
        continue

    if r.status_code != 200:
        logger.warning("Could not pull worker status from server!")
        continue

    data = Box(json.loads(r.content))
    if data.attributes.disabled:
        if last_error != "ERR_WORKER_DISABLED":
            logger.info("The worker is disabled from the API server")
            last_error = "ERR_WORKER_DISABLED"
        continue

    # Pull a task off the queue
    try:
        r = connect_to_api("GET", "/queue/poll",
                           "Error polling queue for jobs!")
    except NetworkError as e:
        if last_error != "ERR_POLL_STATUS":
            logger.warning(e.message)
        last_error = "ERR_POLL_STATUS"
        time.sleep(Config.NETWORK_RETRY_INTERVAL)
        continue

    if r.status_code == 404:
        if last_error != "ERR_QUEUE_EMPTY":
            logger.info("There are currently no jobs on the queue")
            last_error = "ERR_QUEUE_EMPTY"
        continue

    # Reset errors since we made it through the connection gauntlet
    last_error = None

    data = Box(json.loads(r.content))

    # Update heartbeat
    heartbeat.message.status = "in_progress"
    heartbeat.message.job_id = data.job_id
    logger.info(f"Starting job: {data.job_id}")
    logger.info(f"Job title: {data.job_title}")
    heartbeat.job_id, heartbeat.job_title = data.job_id, data.job_title

    start_time = datetime.now(tz=Config.API_TIMEZONE)

    # Start processing job
    job_results_info = Box()
    job_results_info.start_time = str(start_time)
    job_results_info.worker = Config.HOSTNAME
    job_results_info.worker_id = Config.HOST_UUID
    job_results_info.version = Config.VERSION

    # Load all job modules and validate task data for the modules
    logger.info("Validating all task modules and data.")
    modules = None
    try:
        modules = validate_modules(data)
    except InitializationError as e:
        job_results_info.message = e.message
        logger.warning(e.message)
    except ValidationError as e:
        job_results_info.message = f"Could not validate task data: {e.message}"
        logger.warning(f"Could not validate task data: {e.message}")
    except:
        job_results_info.message = f"Encountered unknown error initializing/validating tasks!"
        logger.warning(
            f"Encountered unknown error initializing/validating tasks!")

    if not modules:
        job_results_info.end_time = str(datetime.now(tz=Config.API_TIMEZONE))
        job_results_info.runtime = str(
            datetime.now(tz=Config.API_TIMEZONE) - start_time)
        logger.warning(f"Aborting job: {data.job_id}")
        try:
            complete_job(data=data, job_info=job_results_info, failed=True)
        except NetworkError as e:
            logger.warning(e.message)
        break

    # Start running tasks
    tasks = [i.module for i in data.tasks]
    logger.info(f"Found tasks in job: {' >> '.join(tasks)}")

    for idx, task in enumerate(data.tasks):
        job_failed = True
        
        module = modules[idx]
        task = Box(task)
        task_name, task_data = task.module, task.data
        logger.info(
            f"Starting task: {task_name} [{idx + 1} of {len(data.tasks)}]")
        job_results_info.module = task_name

        try:
            module.run()
            module.cleanup()
        except RunError as e:
            job_results_info.message = f"Failed to run task: {e.message}"
            logger.warning(f"Failed to run task: {e.message}")
            logger.warning(f"Aborting job: {data.job_id} -> {task_name}")
            logger.warning(f"Module runtime: {module.get_duration()}")
            break
        except CleanupError as e:
            job_results_info.message = f"Failed to cleanup task: {e.message}"
            logger.warning(f"Failed to cleanup task: {e.message}")
            logger.warning(f"Aborting job: {data.job_id} -> {task_name}")
            logger.warning(f"Module runtime: {module.get_duration()}")
            break
        # except:
        #     job_results_info.message = f"Unknown failure on task!"
        #     logger.warning(f"Unknown failure on task!")
        #     logger.warning(f"Aborting job: {data.job_id} -> {task_name}")
        #     logger.warning(f"Module runtime: {module.get_duration()}")
        #     break

        job_failed = False
        logger.info(f"Module runtime: {module.get_duration()}")

    job_results_info.completed = not job_failed
    if job_failed:
        job_log_level = "WARNING"
    else:
        job_log_level = "SUCCESS"
        job_results_info.pop("module")

    job_results_info.end_time = str(datetime.now(tz=Config.API_TIMEZONE))
    job_results_info.runtime = str(
        datetime.now(tz=Config.API_TIMEZONE) - start_time)
    logger.log(job_log_level,
               f"Job runtime: {datetime.now(tz=Config.API_TIMEZONE) - start_time}")

    # Move job information into the appropriate collection
    try:
        complete_job(data=data, job_info=job_results_info, failed=job_failed)
    except NetworkError:
        logger.warning(e.message)
