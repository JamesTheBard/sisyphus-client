import importlib
import importlib.util
from typing import List, Union

import requests
from box import Box
from loguru import logger

from app.config import Config
from app.exceptions import InitializationError, NetworkError


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


def validate_modules(data: Union[dict, Box]) -> List[object]:
    """Preprocess all modules, validate per-module data, and return a list of initialized modules to be run.

    Args:
        data (Union[dict, Box]): The job information from the API server.

    Raises:
        InitializationError: When the module cannot be loaded.
        ValidationError: When the data passed to the task module is invalid/malformed.

    Returns:
        List[object]: A list of task modules.
    """
    data = Box(data)
    tasks = list()
    for task in data.tasks:
        logger.info(f"Initializing task module: {task.module}")
        module_path = '.'.join(Config.MODULES[task.module].split('.')[0:-1])
        module_name = Config.MODULES[task.module].split('.')[-1]

        if not importlib.util.find_spec(module_path):
            raise InitializationError(
                f"Could not find client module: {module_path}:{module_name}")
        logger.debug(f"Found module: {task.module} -> {module_path}")

        try:
            module = getattr(importlib.import_module(module_path), module_name)
        except AttributeError as e:
            raise InitializationError(
                f"Could not load client module: {module_path}:{module_name}, module has no attribute '{module_name}'")
        logger.debug(
            f"Found module attribute: {task.module} -> {module_path}:{module_name}")

        module = module(task=task.data)
        module.validate()
        logger.debug(f"Validated module data!")

        tasks.append(module)
        return tasks


def complete_job(data: Union[dict, Box], job_info: Union[dict, Box], failed: bool = False) -> None:
    """Finish the job and move the job information into the appropriate MongoDB container via API.

    Args:
        data (Union[dict, Box]): The job data.
        job_info (Union[dict, Box]): Specific job run information.
        failed (bool, optional): Whether the job failed or not. Defaults to False.

    Raises:
        NetworkError: When the client cannot reach the central API server.
    """
    connect_to_api(
        method="PATCH",
        rest_path=f'/jobs/{data.job_id}/completed',
        fail_message="Could not finalize job in the queue!",
        json={"failed": failed, "info": job_info}
    )
