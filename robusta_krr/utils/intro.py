import requests
import asyncio
from concurrent.futures import ThreadPoolExecutor

from .version import get_version


ONLINE_LINK = 'https://api.robusta.dev/krr/intro'
LOCAL_LINK = './intro.txt'
TIMEOUT = 0.5


# Synchronous function to fetch intro message
def fetch_intro_message() -> str:
    try:
        # Attempt to get the message from the URL
        response = requests.get(ONLINE_LINK, params={"version": get_version()}, timeout=TIMEOUT)
        response.raise_for_status()  # Raises an error for bad responses
        result = response.json()
        return result['message']
    except Exception as e1:
        # If there's any error, fallback to local file
        try:
            with open(LOCAL_LINK, 'r') as file:
                return file.read()
        except Exception as e2:
            return (
                "[red]Failed to load the intro message.\n"
                f"Both from the URL: {e1.__class__.__name__} {e1}\n"
                f"and the local file: {e2.__class__.__name__} {e2}\n"
                "But as that is not critical, KRR will continue to run without the intro message.[/red]"
            )


async def load_intro_message() -> str:
    loop = asyncio.get_running_loop()
    # Use a ThreadPoolExecutor to run the synchronous function in a separate thread
    with ThreadPoolExecutor() as pool:
        return await loop.run_in_executor(pool, fetch_intro_message)


__all__ = ['load_intro_message']
