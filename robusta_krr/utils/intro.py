import requests
import asyncio
from concurrent.futures import ThreadPoolExecutor


ONLINE_LINK = 'https://github.com/robusta-dev/krr/blob/main/intro.txt'
LOCAL_LINK = './intro.txt'
TIMEOUT = 0.5


# Synchronous function to fetch intro message
def fetch_intro_message() -> str:
    try:
        # Attempt to get the message from the URL
        response = requests.get(ONLINE_LINK, timeout=TIMEOUT)
        response.raise_for_status()  # Raises an error for bad responses
        return response.text
    except Exception:
        # If there's any error, fallback to local file
        try:
            with open(LOCAL_LINK, 'r') as file:
                return file.read()
        except Exception as e:
            raise Exception("Failed to load the intro message from both URL and local file.") from e


async def load_intro_message() -> str:
    loop = asyncio.get_running_loop()
    # Use a ThreadPoolExecutor to run the synchronous function in a separate thread
    with ThreadPoolExecutor() as pool:
        return await loop.run_in_executor(pool, fetch_intro_message)


__all__ = ['load_intro_message']
