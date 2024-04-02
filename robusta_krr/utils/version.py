import robusta_krr
import requests
import asyncio
from typing import Optional
from concurrent.futures import ThreadPoolExecutor


def get_version() -> str:
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
