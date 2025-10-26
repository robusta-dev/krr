from typing import List, Dict
from pydantic import BaseModel


class RobustaConfig(BaseModel):
    sinks_config: List[Dict[str, Dict]]
    global_config: dict

class RobustaToken(BaseModel):
    store_url: str
    api_key: str
    account_id: str
    email: str
    password: str