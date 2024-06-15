import asyncio
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import requests

import robusta_krr


def get_version() -> str:
    # the version string was patched by a release - return __version__ which will be correct
    if robusta_krr.__version__ != "dev":
        return robusta_krr.__version__
    
    # we are running from an unreleased dev version
    try:
        # Get the latest git tag
        tag = subprocess.check_output(["git", "describe", "--tags"]).decode().strip()

        # Get the current branch name
        branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"]).decode().strip()

        # Check if there are uncommitted changes
        status = subprocess.check_output(["git", "status", "--porcelain"]).decode().strip()
        dirty = "-dirty" if status else ""

        return f"{tag}-{branch}{dirty}"
    
    except Exception:
        return robusta_krr.__version__


# Synchronous function to fetch the latest release version from GitHub API
def fetch_latest_version() -> Optional[str]:
    url = "https://api.github.com/repos/robusta-dev/krr/releases/latest"
    try:
        response = requests.get(url, timeout=0.5)  # 0.5 seconds timeout
        response.raise_for_status()  # Raises an error for bad responses
        data = response.json()
        return data.get("tag_name")  # Returns the tag name of the latest release
    except Exception:
        return None


async def load_latest_version() -> Optional[str]:
    loop = asyncio.get_running_loop()
    # Run the synchronous function in a separate thread
    with ThreadPoolExecutor() as pool:
        return await loop.run_in_executor(pool, fetch_latest_version)
