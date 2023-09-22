import importlib
import json
import time
from datetime import datetime

import requests
from box import Box
from loguru import logger

from app.config import Config
from app.exceptions import (CleanupError, InitializationError, RunError,
                            ValidationError)
from app.heartbeat import heartbeat

# Start the heartbeat
logger.info(f"Starting 'sisyphus-client', version {Config.VERSION}")
logger.info(f"Worker ID..........: {Config.HOST_UUID}")
logger.info(f"Hostname...........: {Config.HOSTNAME}")
logger.info(f"Sisyphus Server....: {Config.API_URL}")
heartbeat.interval = 5
heartbeat.set_startup()
heartbeat.start()
logger.debug(f"Heartbeat started, sending info to {Config.API_URL}")

# Processing loop
empty_queue = False
queue_disabled = False
worker_disabled = False
while True:
    heartbeat.set_idle()
    time.sleep(5)

    # Check to see if the entire queue is disabled
    r = requests.get(Config.API_URL + '/queue')
    data = Box(json.loads(r.content))
    if data.attributes.disabled:
        if not queue_disabled:
            logger.info("The main server queue is disabled")
            queue_disabled = True
        continue
    queue_disabled = False

    # Check to see if we're 'allowed' to process the queue
    r = requests.get(Config.API_URL + '/workers/' + Config.HOST_UUID)
    data = Box(json.loads(r.content))
    if data.attributes.disabled:
        if not worker_disabled:
            logger.info("The worker is disabled on the main server")
            worker_disabled = True
        continue
    worker_disabled = False

    # Pull a task off the queue
    r = requests.get(Config.API_URL + '/queue/poll')
    if r.status_code == 404:
        if not empty_queue:
            logger.info("There are currently no jobs on the queue")
            empty_queue = True
        continue
    stop_logging = False
    
    data = Box(json.loads(r.content))

    # Update heartbeat
    heartbeat.message.status = "in_progress"
    heartbeat.message.job_id = data.job_id
    logger.info(f"Starting job: {data.job_id}")
    logger.info(f"Job title: {data.job_title}")
    heartbeat.job_id, heartbeat.job_title = data.job_id, data.job_title

    # Start running tasks
    start_time = datetime.now()
    tasks = [i.module for i in data.tasks]
    logger.info(f"Found tasks in job: {', '.join(tasks)}")
    job_failed = True
    job_results_info = Box()
    job_results_info.client_start_time = str(start_time)
    for idx, task in enumerate(data.tasks):
        task = Box(task)
        task_name, task_data = task.module, task.data
        logger.info(f"Starting task: {task_name} [{idx + 1} of {len(data.tasks)}]")
        module_path = f"modules.{task_name}"
        job_results_info.module = task_name
        
        try:
            module = getattr(importlib.import_module(
                module_path), task_name.capitalize())
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
        job_results_info.completed = True
        logger.info(f"Module runtime: {module.get_duration()}")

    job_log_level = "WARNING" if job_failed else "SUCCESS"
    job_results_info.runtime = str(datetime.now() - start_time)
    logger.log(job_log_level, f"Job runtime: {datetime.now() - start_time}")
    requests.patch(Config.API_URL + '/jobs/' + data.job_id + '/completed', json={"failed": job_failed, "info": job_results_info})
