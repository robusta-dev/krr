from robusta_krr.core.abstract import formatters
from robusta_krr.core.models.result import Result
import requests
import logging
import os

ROBUSTA_URL = os.getenv("ROBUSTA_URL")

@formatters.register()
def json(result: Result) -> str:
    if(ROBUSTA_URL):
        send_result(result)
    return result.json(indent=2)


def send_result(result: Result):
    headers = {"Content-Type": "application/json"}

    # Convert the Result object into a native dict (not string!)
    result_dict = result.dict()  # Use result.model_dump() if it's a Pydantic v2 model

    action_request = {
        "action_name": "process_scan",
        "action_params": {
            "result": result_dict,  # ✅ This is a proper nested JSON object
            "scan_type": "krr"
        }
    }

    # Let `requests` handle serialization and content headers
    response = requests.post(
        ROBUSTA_URL,
        headers=headers,
        json=action_request
    )

    logging.info(f"Status code: {response.status_code}")
    logging.info(f"Response: {response.text}")
