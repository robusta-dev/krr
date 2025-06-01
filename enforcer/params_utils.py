import logging
import os
import re
from typing import Dict, Optional

from pydantic.types import SecretStr

def get_env_replacement(value: str) -> Optional[str]:
    env_values = re.findall(r"{{[ ]*env\.(.*)[ ]*}}", value)
    if env_values:
        env_var_value = os.environ.get(env_values[0].strip(), None)
        if not env_var_value:
            msg = f"ENV var replacement {env_values[0]} does not exist for param: {value}"
            logging.error(msg)
            raise Exception(msg)
        return env_var_value
    return None


def replace_env_vars_values(values: Dict) -> Dict:
    for key, value in values.items():
        if isinstance(value, str):
            env_var_value = get_env_replacement(value)
            if env_var_value:
                values[key] = env_var_value
        elif isinstance(value, SecretStr):
            env_var_value = get_env_replacement(value.get_secret_value())
            if env_var_value:
                values[key] = SecretStr(env_var_value)
        elif isinstance(value, dict):
            env_var_value = replace_env_vars_values(value)
            if env_var_value:
                values[key] = env_var_value

    return values
