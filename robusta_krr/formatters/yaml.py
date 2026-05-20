"""YAML output formatter."""

import json

import yaml as yaml_module

from robusta_krr.core.abstract import formatters
from robusta_krr.core.models.result import Result


@formatters.register()
def yaml(result: Result) -> str:
    """Format the result as YAML."""
    return yaml_module.dump(json.loads(result.json()), sort_keys=False)
