from .base import BaseFormatter
from .json import JSONFormatter
from .text import TextFormatter
from .yaml import YAMLFormatter

from enum import Enum


class FormatType(str, Enum):
    json = "json"
    yaml = "yaml"
    text = "text"


def get_formatter(format_name: FormatType) -> BaseFormatter:
    match format_name:
        case FormatType.json:
            return JSONFormatter()
        case FormatType.yaml:
            return YAMLFormatter()
        case FormatType.text:
            return TextFormatter()
        case _:
            raise ValueError(f"Unknown formatter: {format_name}")


__all__ = ["BaseFormatter", "JSONFormatter", "TextFormatter", "YAMLFormatter", "get_formatter", "FormatType"]
