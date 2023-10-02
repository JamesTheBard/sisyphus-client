import importlib
import json
import time
from typing import Optional
from datetime import datetime, timezone

import requests
from box import Box
from loguru import logger

from app.config import Config
from app.exceptions import (CleanupError, InitializationError, RunError,
                            ValidationError, NetworkError)
from app.heartbeat import heartbeat

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

def connect_to_api(method: str, rest_path: str, fail_message: str, **kwargs) -> requests.Response:
    """Connect to the API server via REST.

    Args:
        method (str): The method to use (e.g. `GET`, `POST`)
        rest_path (str): The path to use (e.g. `/queue`)
        fail_message (str): The message to use in case of failure

    Raises:
        NetworkError: When there is any issue connecting to the API server or getting data from it.

    Returns:
        requests.Response: The resulting response from the request.
    """
    url = Config.API_URL + rest_path
    try:
        logger.debug(f"Attempting '{method}' request on: '{url}'")
        r = requests.request(method, url, timeout=3, **kwargs)
    except Exception:
        raise NetworkError(fail_message)
    return r


while True:
    heartbeat.set_idle()
    time.sleep(Config.QUEUE_POLL_INTERVAL)

    # Check to see if the entire queue is disabled
    try:
        r = connect_to_api("GET", "/queue", "Error polling API queue for status!")
    except NetworkError as e:
        if last_error != "ERR_QUEUE_STATUS":
            logger.warning(e.message)
        last_error = "ERR_QUEUE_STATUS"
        time.sleep(Config.NETWORK_RETRY_INTERVAL)
        continue
        
    data = Box(json.loads(r.content))
    if data.attributes.disabled:
        if not queue_disabled:
            logger.info("The main server queue is disabled")
            queue_disabled = True
        continue
    queue_disabled = False

    # Check to see if we're 'allowed' to process the queue
    try:
        r = connect_to_api("GET", "/workers/" + Config.HOST_UUID, "Error polling worker for queue permissions!")
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
        if not worker_disabled:
            logger.info("The worker is disabled on the main server")
            worker_disabled = True
        continue
    worker_disabled = False

    # Pull a task off the queue
    try:
        r = connect_to_api("GET", "/queue/poll", "Error polling queue for jobs!")
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

    # Start running tasks
    start_time = datetime.now(tz=timezone.utc)
    tasks = [i.module for i in data.tasks]
    logger.info(f"Found tasks in job: {' >> '.join(tasks)}")
    job_failed = True
    job_results_info = Box()
    job_results_info.start_time = str(start_time)
    for idx, task in enumerate(data.tasks):
        task = Box(task)
        task_name, task_data = task.module, task.data
        logger.info(
            f"Starting task: {task_name} [{idx + 1} of {len(data.tasks)}]")
        module_path = f"modules.{task_name}"
        job_results_info.module = task_name
        job_results_info.worker = Config.HOSTNAME
        job_results_info.worker_id = Config.HOST_UUID
        job_results_info.version = Config.VERSION

        try:
            module = getattr(importlib.import_module(
                module_path), task_name.capitalize())
            module = module(task=task_data)
        except InitializationError as e:
            job_results_info.message = f"Could not initialize module: {e.message}"
            logger.warning(f"Could not initialize module: {e.message}")
            logger.warning(f"Aborting job: {data.job_id}")
            break
        except ModuleNotFoundError as e:
            job_results_info.message = f"Could not find module: {module_path}"
            logger.warning(f"Could not find module: {module_path}")
            logger.warning(f"Aborting job: {data.job_id}")
            break

        try:
            module.validate()
            module.run()
            module.cleanup()
        except ValidationError as e:
            job_results_info.message = f"Could not validate task data: {e.message}"
            logger.warning(f"Could not validate task data: {e.message}")
            logger.warning(f"Aborting job: {data.job_id} -> {task_name}")
            logger.warning(f"Module runtime: {module.get_duration()}")
            break
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
        except:
            job_results_info.message = f"Unknown failure on task!"
            logger.warning(f"Unknown failure on task!")
            logger.warning(f"Aborting job: {data.job_id} -> {task_name}")
            logger.warning(f"Module runtime: {module.get_duration()}")
            break

        job_failed = False
        job_results_info.completed = not job_failed
        logger.info(f"Module runtime: {module.get_duration()}")

    if job_failed:
        job_log_level = "WARNING"
    else:
        job_log_level = "SUCCESS"
        job_results_info.pop("module")

    job_results_info.end_time = str(datetime.now())
    job_results_info.runtime = str(datetime.now() - start_time)
    logger.log(job_log_level, f"Job runtime: {datetime.now() - start_time}")
    
    # Move job information into the appropriate collection
    try:
        connect_to_api(
            method="PATCH", 
            rest_path=f'/jobs/{data.job_id}/completed',
            fail_message="Could not finalize job in the queue!",
            json={"failed": job_failed, "info": job_results_info}
        )
    except NetworkError:
        logger.warning(e.message)
    