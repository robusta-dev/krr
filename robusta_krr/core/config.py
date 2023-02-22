import pydantic as pd

from robusta_krr.core.formatters import FormatType


class Config(pd.BaseSettings):
    quiet: bool = pd.Field(False)
    verbose: bool = pd.Field(False)

    prometheus_url: str | None = pd.Field(None)
    format: FormatType = pd.Field(FormatType.text)
